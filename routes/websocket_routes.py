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
        

@router.get("/get_free_tournaments/", response_model=list[TournamentOut])
async def get_free_tournaments():
    return await service.get_free_tournaments()

@router.get("/get_daily_tournaments/", response_model=list[TournamentOut])
async def get_daily_tournaments():
    return await service.get_daily_tournaments()

@router.get("/get_weekly_tournaments/", response_model=list[TournamentOut])
async def get_weekly_tournaments():
    return await service.get_weekly_tournaments()

@router.get("/get_monthly_tournaments/", response_model=list[TournamentOut])
async def get_monthly_tournaments():
    return await service.get_monthly_tournaments()