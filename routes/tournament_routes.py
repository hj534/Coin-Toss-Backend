from fastapi import APIRouter
from models.tournament import TournamentCreate, TournamentOut, ParticipantRegister, ParticipantOut
from services.tournament_service import TournamentService

router = APIRouter()
service = TournamentService()


@router.get("/get_tournaments/", response_model=list[TournamentOut])
async def list_tournaments():
    return await service.get_all_tournaments()


@router.post("/create_tournament/", response_model=TournamentOut)
async def create_tournament(payload: TournamentCreate):
    return await service.create_tournament(payload)


@router.post("/register_participant_in_tournament/", response_model=ParticipantOut)
async def register_participant(payload: ParticipantRegister):
    return await service.register_participant(payload)