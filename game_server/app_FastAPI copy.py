from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

app = FastAPI()

# Store active users and their rooms
active_users: Dict[str, str] = {}  # {session_id: room_id}
rooms: Dict[str, List[str]] = {}  # {room_id: [session_id, session_id]}


class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        session_id = str(id(websocket))  # Unique identifier
        active_users[session_id] = room_id

        if room_id not in rooms:
            rooms[room_id] = []
        rooms[room_id].append(session_id)

        self.active_connections.append(websocket)
        await self.broadcast_lobby(room_id)

    async def disconnect(self, websocket: WebSocket):
        session_id = str(id(websocket))
        room_id = active_users.pop(session_id, None)

        if room_id and session_id in rooms.get(room_id, []):
            rooms[room_id].remove(session_id)
            if not rooms[room_id]:  # Remove empty room
                del rooms[room_id]

        self.active_connections.remove(websocket)
        await self.broadcast_lobby(room_id)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def broadcast_lobby(self, room_id: str):
        if room_id in rooms:
            message = {"room_id": room_id, "users": rooms[room_id]}
            for connection in self.active_connections:
                await connection.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """Handles WebSocket connections for a specific room."""
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = f"Room {room_id}: {data}"
            await manager.broadcast(message)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
