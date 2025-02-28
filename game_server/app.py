from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from collections import defaultdict
import time
import psutil
import os
from datetime import datetime

app = Flask(__name__)
# Function to load secrets from a file
def load_secrets(file_path):
    secrets = {}
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith("#"):  # Ignore empty lines and comments
                key, value = line.strip().split("=", 1)
                secrets[key] = value
    return secrets

# Load secrets
secrets = load_secrets("secrets.txt")

app.config['SQLALCHEMY_DATABASE_URI'] = secrets.get('DB_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins='*')

# Store active users with their session IDs
active_users = {}  # {session_id: username}
messages = []  # [{text, username, timestamp, server}]

# Performance metrics (same Metrics class as FastAPI version)
class Metrics:
    def __init__(self):
        self.active_connections = 0
        self.messages_count = 0
        self.last_minute_messages = []
        self.latencies = {}
        self.process = psutil.Process(os.getpid())
    
    def add_message(self):
        now = time.time()
        self.messages_count += 1
        self.last_minute_messages.append(now)
        # Clean up messages older than 1 minute
        self.last_minute_messages = [t for t in self.last_minute_messages if now - t <= 60]
    
    def get_messages_per_second(self):
        return len(self.last_minute_messages) / 60 if self.last_minute_messages else 0
    
    def get_memory_usage(self):
        return self.process.memory_info().rss / 1024 / 1024  # MB
    
    def get_cpu_usage(self):
        return self.process.cpu_percent()
    
    def add_latency(self, sid, latency):
        if sid not in self.latencies:
            self.latencies[sid] = []
        self.latencies[sid].append(latency)
        # Keep only last 50 measurements
        self.latencies[sid] = self.latencies[sid][-50:]
    
    def get_average_latency(self, sid):
        if sid in self.latencies and self.latencies[sid]:
            return sum(self.latencies[sid]) / len(self.latencies[sid])
        return 0

metrics = Metrics()

class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    party_id = db.Column(db.Integer, nullable=True)
    current_room_id = db.Column(db.Integer, nullable=True)
    state = db.Column(db.String(20), nullable=False)

class Lobby(db.Model):
    lobby_id = db.Column(db.Integer, primary_key=True)
    lobby_name = db.Column(db.String(50), nullable=False)

class Room(db.Model):
    room_id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(50))
    state = db.Column(db.String(20))  # e.g., 'loading', 'active', 'idle'

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    metrics.active_connections += 1
    print('Client connected')
    sid = request.sid
    active_users[sid] = f"Guest_{sid[:4]}"
    emit('user_joined', {'username': active_users[sid], 'server': 'Flask'})
    broadcast_users()

@socketio.on('disconnect')
def handle_disconnect():
    metrics.active_connections -= 1
    if request.sid in metrics.latencies:
        del metrics.latencies[request.sid]
    sid = request.sid
    if sid in active_users:
        username = active_users[sid]
        del active_users[sid]
        print(f'Client disconnected: {username}')
        broadcast_users()

@socketio.on('join_lobby')
def handle_join_lobby(data):
    session_id = request.sid
    username = data.get('username', '').strip()
    
    # Check if username is empty
    if not username:
        emit('join_error', {'message': 'Username cannot be empty'})
        return
        
    # Check if username is already taken (excluding guests)
    if username in active_users.values() and not username.startswith('Guest_'):
        emit('join_error', {'message': 'Username already taken'})
        return
        
    # Update username for this session
    active_users[session_id] = username
    
    # Notify the user who just joined
    emit('user_joined', {
        'username': username,
        'is_you': True
    })
    
    # Broadcast updated user list to all clients
    broadcast_users()
    print(f'User {username} joined the lobby')

@socketio.on('update_state')
def handle_update_state(data):
    # Handle state update and broadcast to all clients
    emit('state_updated', data, broadcast=True)

@socketio.on('ping')
def handle_ping(data):
    client_timestamp = data.get('timestamp', 0)
    latency = (time.time() - client_timestamp) * 1000
    metrics.add_latency(request.sid, latency)
    emit('pong', {
        'timestamp': client_timestamp,
        'latency': latency
    })

@socketio.on('chat_message')
def handle_message(data):
    metrics.add_message()
    start_time = time.time()
    
    sid = request.sid
    message = {
        'text': data.get('text', ''),
        'username': active_users.get(sid, 'Unknown'),
        'timestamp': time.time(),
        'server': 'Flask'
    }
    messages.append(message)
    socketio.emit('chat_message', message)
    broadcast_metrics()

@socketio.on('set_username')
def handle_set_username(data):
    sid = request.sid
    username = data.get('username')
    if username:
        active_users[sid] = username
        broadcast_users()

def broadcast_users():
    socketio.emit('users_update', {
        'users': list(active_users.values()),
        'server': 'Flask'
    })

def broadcast_metrics():
    metrics_data = {
        'active_connections': metrics.active_connections,
        'messages_per_second': metrics.get_messages_per_second(),
        'memory_usage': metrics.get_memory_usage(),
        'cpu_usage': metrics.get_cpu_usage(),
        'server': 'Flask'
    }
    socketio.emit('metrics_update', metrics_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
