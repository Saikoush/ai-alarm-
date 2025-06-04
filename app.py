import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import threading
import time
import pyttsx3
import pygame

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

alarm_data = {
    'alarm_time': None,
    'method': 'tts',
    'custom_audio_path': None,
    'snooze_minutes': 5,
    'alarm_thread': None,
    'alarm_active': False
}

def alarm_thread_func(alarm_time, method, custom_audio_path, snooze_minutes):
    alarm_data['alarm_active'] = True
    while alarm_data['alarm_active']:
        now = datetime.now()
        if now >= alarm_time:
            if method == 'tts':
                engine = pyttsx3.init()
                engine.say("Wake up! It's alarm time!")
                engine.runAndWait()
            elif method == 'beep':
                try:
                    pygame.mixer.init()
                    beep_path = os.path.join('beepsound', 'beep.wav')  # Your beep file path
                    beep_sound = pygame.mixer.Sound(beep_path)
                    beep_sound.play()
                    time.sleep(5)  # Play for 5 seconds
                except Exception as e:
                    print(f"Pygame error: {e}")
            elif method == 'custom' and custom_audio_path:
                try:
                    pygame.mixer.init()
                    pygame.mixer.music.load(custom_audio_path)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(1)
                except Exception as e:
                    print(f"Pygame error: {e}")

            alarm_data['alarm_active'] = False
            break
        time.sleep(1)

@app.route('/')
def index():
    return render_template('index.html')  # Your HTML file should be named index.html

@app.route('/set_alarm', methods=['POST'])
def set_alarm():
    alarm_time_str = request.form.get('alarm_time')
    method = request.form.get('method')
    snooze_minutes = request.form.get('snooze_minutes')

    if not alarm_time_str or not method or not snooze_minutes:
        return jsonify({'status': 'error', 'message': 'Missing required fields'})

    try:
        snooze_minutes = int(snooze_minutes)
        if snooze_minutes < 1 or snooze_minutes > 60:
            raise ValueError
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid snooze minutes'})

    # Parse alarm time string to datetime object (today or tomorrow)
    now = datetime.now()
    alarm_time = datetime.strptime(alarm_time_str, '%H:%M')
    alarm_time = alarm_time.replace(year=now.year, month=now.month, day=now.day)
    if alarm_time <= now:
        alarm_time += timedelta(days=1)

    custom_audio_path = None
    if method == 'custom':
        if 'custom_audio' not in request.files:
            return jsonify({'status': 'error', 'message': 'No audio file uploaded for custom method'})
        file = request.files['custom_audio']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'No selected file'})
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            custom_audio_path = filepath
        else:
            return jsonify({'status': 'error', 'message': 'Invalid file type'})

    # If an alarm thread is running, stop it
    if alarm_data['alarm_thread'] and alarm_data['alarm_thread'].is_alive():
        alarm_data['alarm_active'] = False
        alarm_data['alarm_thread'].join()

    # Start new alarm thread
    alarm_thread = threading.Thread(target=alarm_thread_func, args=(alarm_time, method, custom_audio_path, snooze_minutes))
    alarm_thread.daemon = True
    alarm_thread.start()

    # Update alarm data
    alarm_data['alarm_time'] = alarm_time
    alarm_data['method'] = method
    alarm_data['custom_audio_path'] = custom_audio_path
    alarm_data['snooze_minutes'] = snooze_minutes
    alarm_data['alarm_thread'] = alarm_thread

    return jsonify({'status': 'success', 'message': f'Alarm set for {alarm_time.strftime("%H:%M")}'})

@app.route('/snooze', methods=['POST'])
def snooze():
    if not alarm_data['alarm_time']:
        return jsonify({'status': 'error', 'message': 'No active alarm to snooze'})

    if alarm_data['alarm_thread'] and alarm_data['alarm_thread'].is_alive():
        alarm_data['alarm_active'] = False
        alarm_data['alarm_thread'].join()

    new_alarm_time = datetime.now() + timedelta(minutes=alarm_data['snooze_minutes'])

    alarm_thread = threading.Thread(target=alarm_thread_func, args=(
        new_alarm_time,
        alarm_data['method'],
        alarm_data['custom_audio_path'],
        alarm_data['snooze_minutes']
    ))
    alarm_thread.daemon = True
    alarm_thread.start()

    alarm_data['alarm_time'] = new_alarm_time
    alarm_data['alarm_thread'] = alarm_thread
    alarm_data['alarm_active'] = True

    return jsonify({'status': 'success', 'message': f'Alarm snoozed to {new_alarm_time.strftime("%H:%M")}'})

if __name__ == '__main__':
    app.run(debug=True)
