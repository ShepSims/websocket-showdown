# WebSocket Server Comparison: Flask vs FastAPI

A real-time comparison of WebSocket implementations using Flask-SocketIO and FastAPI with python-socketio.

## Features

- Split-screen view of both servers
- Real-time chat functionality
- Performance metrics
- User management
- Latency monitoring

## Setup

1. Clone the repository:
```bash
git clone https://github.com/shepsims/python-socketio-comparison.git
cd python-socketio-comparison
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Servers

1. Start the Flask server (default port 5000):
```bash
python game_server/app.py
```

2. Start the FastAPI server (default port 8000):
```bash
python -m uvicorn game_server.app_FastAPI:socket_app --reload --port 8000
```

3. Open your browser and visit:
   - Flask: http://localhost:5000
   - FastAPI: http://localhost:8000

## Features Comparison

| Feature | Flask-SocketIO | FastAPI + python-socketio |
|---------|---------------|------------------------|
| WebSocket Support | Built-in | Via python-socketio |
| Performance | Good | Excellent |
| Ease of Setup | Simple | Moderate |
| Async Support | Optional | Built-in |

## Performance Metrics

The application tracks and displays:
- Active connections
- Messages per second
- Latency
- Memory usage
- CPU usage

## Contributing

Feel free to submit issues and enhancement requests!

## License

[MIT](LICENSE) 