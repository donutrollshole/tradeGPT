from flask import Flask, render_template, request, jsonify, session, redirect
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import threading
import requests
import os
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

users_logged_in = set()
data_thread = None


class User(UserMixin):
    def __init__(self, email):
        self.email = email
        self.id = email


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


@app.route('/')
def index():
    global users_logged_in
    if current_user.is_authenticated:
        users_logged_in.add(current_user.email)
        start_data_thread()
        return render_template('index.html')
    else:
        if len(users_logged_in) == 0:
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
    global users_logged_in
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
                    users_logged_in.add(user_email)
                    return jsonify({'result': 'success'})
                else:
                    return jsonify({'result': 'not_allowed'})
            else:
                return jsonify({'result': 'failure'})
        except:
            return jsonify({'result': 'failure'})
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    global users_logged_in
    if current_user.email in users_logged_in:  # someone could spam the logout button with user already removed
        users_logged_in.remove(current_user.email)
    if len(users_logged_in) == 0:
        stop_data_thread()
    logout_user()
    return redirect("/")


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, ssl_context='adhoc')
