from flask import Flask, render_template, request, jsonify, session, redirect
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import threading
import requests
import os
import time
from dotenv import load_dotenv

from main import main
from thread_signal import Signal

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.urandom(24)
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
ALLOWED_EMAILS = os.getenv('ALLOWED_EMAILS').split(',')

socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

users_active = set()
data_thread = None
user_last_seen = {}


class User(UserMixin):
    def __init__(self, email):
        self.email = email
        self.id = email


def check_user_heartbeat():
    global user_last_seen, users_active
    print("Heartbeat Thread Started.")
    while True:
        current_time = time.time()
        to_remove = set()
        for email, last_seen in user_last_seen.items():
            if current_time - last_seen > 60:  # 1 minute
                to_remove.add(email)

        for email in to_remove:
            print(f" {email} is no longer active.")
            user_last_seen.pop(email)
            users_active.discard(email)
            if len(users_active) == 0:
                stop_data_thread()
        time.sleep(10)


def start_data_thread():
    global data_thread
    if not data_thread:
        Signal.should_run = True
        data_thread = threading.Thread(target=main, args=(socketio,), daemon=True)
        data_thread.start()


def stop_data_thread():
    global data_thread
    if data_thread:
        Signal.should_run = False
        data_thread.join()
        data_thread = None


def load_user(email):
    if email in ALLOWED_EMAILS:
        return User(email)
    return None


@login_manager.user_loader
def user_loader(email):
    return load_user(email)


@login_manager.unauthorized_handler
def unauthorized():
    return "You must be logged in to access this content.", 403


@socketio.on('heartbeat')
def handle_heartbeat():
    global user_last_seen
    if current_user.is_authenticated:
        start_data_thread()
        user_last_seen[current_user.email] = time.time()


@app.route('/')
def index():
    global users_active
    if current_user.is_authenticated:
        users_active.add(current_user.email)
        start_data_thread()
        return render_template('index.html')
    else:
        if len(users_active) == 0:
            stop_data_thread()
        return render_template('login.html', client_id=CLIENT_ID)


@app.route('/send_pm', methods=['GET'])
@login_required
def send_pm():
    recipient = request.args.get('recipient', '')
    subject = request.args.get('subject', '')
    content = request.args.get('content', '')

    return render_template('send_pm.html', recipient=recipient, subject=subject, content=content)


@app.route('/login', methods=['GET', 'POST'])
def login():
    global users_active
    if request.method == 'POST':
        token = request.json['auth_code']
        try:
            idinfo = requests.get(f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={token}")
            idinfo = idinfo.json()
            if idinfo["aud"] == CLIENT_ID:
                user_email = idinfo['email']
                if user_email in ALLOWED_EMAILS:
                    user = User(user_email)
                    login_user(user)
                    users_active.add(user_email)
                    user_last_seen[user_email] = time.time()
                    return jsonify({'result': 'success'})
                else:
                    return jsonify({'result': 'not_allowed'})
            else:
                return jsonify({'result': 'failure'})
        except:
            return jsonify({'result': 'failure'})
    return render_template('login.html')


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    global users_active
    users_active.discard(current_user.email)
    if len(users_active) == 0:
        stop_data_thread()
    logout_user()
    return redirect("/")


if __name__ == '__main__':
    # Start the user heartbeat check thread
    heartbeat_thread = threading.Thread(target=check_user_heartbeat, daemon=True)
    heartbeat_thread.start()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, ssl_context='adhoc')
