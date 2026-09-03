from fastapi import APIRouter, HTTPException
from models.tournament import TournamentCreate, TournamentOut, ParticipantRegister, ParticipantOut, TournamentMatchOut
from models.tournament import MatchResultSubmit
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


@router.get("/get_participants_of_tournament/{tournament_id}/", response_model=list[ParticipantOut])
async def get_tournament_participants(tournament_id: int):
    return await service.get_tournament_participants(tournament_id)


@router.get(
    "/get_my_tournament_match/{tournament_id}/{playfab_id}/",
    response_model=TournamentMatchOut,
)
async def get_my_tournament_match(tournament_id: int, playfab_id: str):
    match = await service.get_my_tournament_match(tournament_id, playfab_id)
    if not match:
        raise HTTPException(
            status_code=404,
            detail="No pending or in-progress tournament match found for this player",
        )
    return match

@router.post("/submit_match_result/")
async def submit_match_result(self, payload: MatchResultSubmit):
    return await service.submit_match_result(payload)