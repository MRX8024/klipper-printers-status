import os, time, requests
from flask import Flask, render_template, jsonify, request

CONFIG_FILE = './config.txt'
app = Flask(__name__)

def load_config():
    global time_interval, api_urls
    with open(CONFIG_FILE, 'r') as file:
        file = file.readlines()
    for line in file:
        line.strip()
        if line.startswith('TIME='):
            time_interval = int(line.strip().split('=')[1])
        if line.startswith('API_URLS='):
            api_urls = ['http://' + url for url in line.split('=')[1].split(',')]
    print(f"Init urls: {' '.join(api_urls)}")
    print(f"Init time: {time_interval}")

def save_config(time_interval, api_urls):
    with open(CONFIG_FILE, 'w') as file:
        file.write(f'TIME={time_interval}\n')
        file.write(f'API_URLS={",".join([url.replace("http://", "") for url in api_urls])}')

def get_print_progress(api_url):
    data = requests.get(f'{api_url}/printer/objects/query?webhooks&virtual_sdcard&print_stats', timeout=1).json()
    status = data['result']['status']
    if status['print_stats']['state'] == 'printing':
        proc = round(status['virtual_sdcard']['progress'] * 100)
        filename = status['print_stats']['filename']
        return '🟡Printing ' + str(proc) + '%', proc, filename
    elif (status['print_stats']['state'] == 'ready' or
          status['print_stats']['state'] == 'complete' or
          status['print_stats']['state'] == 'standby'):
        return '🟢Printer is ' + status['print_stats']['state'], 'false', ''
    elif status['print_stats']['state'] == 'paused':
        return '🟡Printer is ' + status['print_stats']['state'], 'false', ''
    elif (status['print_stats']['state'] == 'error' or
          status['print_stats']['state'] == 'shutdown'):
        return '🔴' + status['webhooks']['state_message'], 'false', ''
    else:
        return '🔴' + status['webhooks']['state_message'], 'false', ''

def get_info(api_url):
    data = requests.get(f'{api_url}//printer/objects/query?gcode_move&toolhead&extruder&heater_bed', timeout=1).json()
    status = data['result']['status']
    extruder = status['extruder']['temperature']
    heater_bed = status['heater_bed']['temperature']
    return extruder, heater_bed

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    global api_urls
    progress_data = []
    for i, url in enumerate(api_urls):
        try:
            status, progress, filename = get_print_progress(url)
            extruder, heater_bed = get_info(url)
        except requests.RequestException as e:
            status, progress, filename = '🔴Printer is shutdown', 'false', ''
            extruder, heater_bed = 'N/A', 'N/A'
        progress_data.append({
            'id': i + 1,
            'url': url,
            'status': status,
            'progress': progress,
            'filename': filename,
            'extruder': extruder,
            'heater_bed': heater_bed,
        })
    return jsonify(progress_data)

@app.route('/set_interval', methods=['POST'])
def set_interval():
    global time_interval, api_urls
    data = request.json
    time_interval = data.get('interval', 10)
    save_config(time_interval, api_urls)
    return jsonify({'message': f'Interval set to {time_interval} seconds.'})

@app.route('/add_url', methods=['POST'])
def add_url():
    global time_interval, api_urls
    new_url = request.json['url']
    if new_url:
        new_url = 'http://' + new_url.replace('http://', '').split('/')[0]
        if new_url not in api_urls:
            api_urls.append(new_url)
            save_config(time_interval, api_urls)
            return jsonify({'message': f'URL {new_url} added successfully.'})
    return jsonify({'message': 'Invalid URL.'})

@app.route('/delete_url', methods=['POST'])
def delete_url():
    global time_interval, api_urls
    data = request.json
    del_url = data.get('url')
    if del_url:
        del_url = 'http://' + del_url.replace('http://', '')
        if del_url in api_urls:
            api_urls.remove(del_url)
            save_config(time_interval, api_urls)
            return jsonify({'message': f'URL {del_url} removed successfully.'})
    return jsonify({'message': 'URL not found.'})

if __name__ == '__main__':
    load_config()
    app.run(host='0.0.0.0', port=8080, debug=False)
