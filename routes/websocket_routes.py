from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.websocket_instance import manager  # singleton
router = APIRouter()

@router.websocket("/ws/{playfab_id}")
async def websocket_endpoint(websocket: WebSocket, playfab_id: str):
    await manager.connect(websocket, playfab_id)
    try:
        while True:
            await websocket.receive_text()  # Optional, keep-alive or ping
    except WebSocketDisconnect:
        manager.disconnect(playfab_id)