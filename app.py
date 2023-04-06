from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading

from main import main

app = Flask(__name__)
socketio = SocketIO(app)


# Simulate checking for new data
def check_data():
    main(socketio)


# Start the data checking thread
data_thread = threading.Thread(target=check_data, daemon=True)
data_thread.start()


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
