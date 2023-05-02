from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import threading
import requests
import os
import time
from dotenv import load_dotenv

from main import main
from thread_signal import Signal
from pm_sender import *
from flask_sqlalchemy import SQLAlchemy
from GeoSpatial import GeoSpatial

load_dotenv()  # Load environment variables from .env file
CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
ALLOWED_EMAILS = os.getenv('ALLOWED_EMAILS').split(',')
PSQL_USERNAME = os.getenv('PSQL_USERNAME')
PSQL_PASSWORD = os.getenv('PSQL_PASSWORD')
PSQL_HOST = os.getenv('PSQL_HOST')
PSQL_PORT = os.getenv('PSQL_PORT')
PSQL_DB = os.getenv('PSQL_DB')

app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config['SQLALCHEMY_DATABASE_URI'] = \
    f'postgresql://{PSQL_USERNAME}:{PSQL_PASSWORD}@{PSQL_HOST}:{PSQL_PORT}/{PSQL_DB}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

users_active = set()
data_thread = None
user_last_seen = {}

zipcode = os.getenv("my_local_zip")
pm_msg_prefix = f"""?recipient=${{author}}&subject=hardwareswap&content="""


class User(db.Model, UserMixin):
    id = db.Column(db.String(120), primary_key=True)
    paypal_email = db.Column(db.String(120), nullable=False)
    pm_msg = db.Column(db.String(1000), nullable=False)
    local_zip_code = db.Column(db.Integer(), nullable=False)

    def __init__(self, email):
        self.paypal_email = email
        self.id = email
        self.local_zip_code = 10001
        self.pm_msg = \
            (f"Hey! I would like to purchase the ${{entry.name}} for ${{entry.price}}. If you are good with"
             f"shipping to {self.local_zip_code}, please send a PayPal invoice to {self.paypal_email}. Thanks!")


def check_user_heartbeat():
    global user_last_seen, users_active
    print("Heartbeat Thread Started.")
    while True:
        current_time = time.time()
        to_remove = set()
        for email, last_seen in user_last_seen.items():
            if current_time - last_seen > 240:  # 2 minute
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
        user = db.session.get(User, email)
        if user:
            return user
        else:
            new_user = User(email)
            db.session.add(new_user)
            db.session.commit()
            return new_user
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
        user_last_seen[current_user.id] = time.time()


@app.route('/')
def index():
    global users_active
    if current_user.is_authenticated:
        users_active.add(current_user.id)
        start_data_thread()
        return render_template('index.html', pm_msg=pm_msg_prefix + current_user.pm_msg)
    else:
        if len(users_active) == 0:
            stop_data_thread()
        return render_template('login.html', client_id=CLIENT_ID)


@app.route('/send_pm', methods=['GET', 'POST'])
def send_pm():
    if request.method == 'POST':
        data = request.get_json()

        if not data['recipient'] or not data['subject'] or not data['content']:
            return jsonify(success=False, message='\nAll field is required.'), 400
        try:
            random_send_pm(data['recipient'], data['subject'], data['content'])
            return jsonify(success=True, message='\nPM sent successfully')
        except Exception as e:
            return jsonify(success=False, message=f'\n{e}'), 400
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
                    user = load_user(user_email)
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
    users_active.discard(current_user.id)
    if len(users_active) == 0:
        stop_data_thread()
    logout_user()
    return redirect("/")


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = db.session.get(User, current_user.id)
    if request.method == 'POST':
        user.paypal_email = request.form.get('paypal_email')
        user.local_zip_code = int(request.form.get('local_zip_code'))
        user.pm_msg = request.form.get('pm_msg')

        db.session.commit()
        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)


@app.route('/get_user_data', methods=['GET'])
@login_required
def get_user_data():
    return jsonify(
        {
            "paypal_email": current_user.paypal_email,
            "pm_msg": pm_msg_prefix + current_user.pm_msg,
            "local_zip_code": current_user.local_zip_code
        }
    )


@app.route('/distance', methods=['GET'])
@login_required
def distance():
    try:
        a = int(request.args.get('a', ''))
        b = int(request.args.get('b', ''))
        distance = GeoSpatial(a) - GeoSpatial(b)
        return jsonify(dis=distance.mi)
    except Exception as e:
        return "Bad Request", 400


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create the tables in your database
    # Start the user heartbeat check thread
    heartbeat_thread = threading.Thread(target=check_user_heartbeat, daemon=True)
    heartbeat_thread.start()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True, ssl_context='adhoc')
