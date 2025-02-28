from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import socketio
import time
import psutil
import os
from datetime import datetime

app = FastAPI()
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)
templates = Jinja2Templates(directory="game_server/templates")

# Performance metrics
class Metrics:
    def __init__(self):
        self.active_connections = 0
        self.messages_count = 0
        self.last_minute_messages = []
        self.latencies = {}  # sid: [latency_measurements]
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

# Store active users
active_users = {}  # {sid: username}
messages = []  # [{text, username, timestamp, server}]

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@sio.event
async def connect(sid, environ):
    metrics.active_connections += 1
    active_users[sid] = f"Guest_{sid[:4]}"
    await sio.emit('user_joined', {'username': active_users[sid], 'server': 'FastAPI'})
    await broadcast_users()
    await broadcast_metrics()

@sio.event
async def disconnect(sid):
    metrics.active_connections -= 1
    if sid in metrics.latencies:
        del metrics.latencies[sid]
    if sid in active_users:
        del active_users[sid]
    await broadcast_users()
    await broadcast_metrics()

@sio.event
async def chat_message(sid, data):
    metrics.add_message()
    start_time = time.time()
    
    message = {
        'text': data.get('text', ''),
        'username': active_users.get(sid, 'Unknown'),
        'timestamp': time.time(),
        'server': 'FastAPI',
        'processing_time': (time.time() - start_time) * 1000  # ms
    }
    messages.append(message)
    await sio.emit('chat_message', message)
    await broadcast_metrics()

@sio.event
async def set_username(sid, data):
    username = data.get('username')
    if username:
        active_users[sid] = username
        await broadcast_users()

@sio.event
async def ping(sid, data):
    client_timestamp = data.get('timestamp', 0)
    latency = (time.time() - client_timestamp) * 1000  # ms
    metrics.add_latency(sid, latency)
    await sio.emit('pong', {
        'timestamp': client_timestamp,
        'latency': latency
    }, room=sid)
    await broadcast_metrics()

async def broadcast_users():
    await sio.emit('users_update', {
        'users': list(active_users.values()),
        'server': 'FastAPI'
    })

async def broadcast_metrics():
    metrics_data = {
        'active_connections': metrics.active_connections,
        'messages_per_second': metrics.get_messages_per_second(),
        'memory_usage': metrics.get_memory_usage(),
        'cpu_usage': metrics.get_cpu_usage(),
        'server': 'FastAPI'
    }
    await sio.emit('metrics_update', metrics_data)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(socket_app, host='127.0.0.1', port=8000)
