from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, playfab_id: str):
        await websocket.accept()
        self.active_connections[playfab_id] = websocket
        print(f"WebSocket connected for PlayFab ID: {playfab_id}")

    def disconnect(self, playfab_id: str):
        self.active_connections.pop(playfab_id, None)
        print(f"WebSocket disconnected for PlayFab ID: {playfab_id}")

    async def send_event(self, playfab_id: str, event: str):
        websocket = self.active_connections.get(playfab_id)
        if websocket:
            await websocket.send_text(event)

    async def broadcast_event(self, event: str):
      print(f"Broadcasting {event} to all connected websockets")
      for websocket in self.active_connections.values():
        await websocket.send_text(event)

