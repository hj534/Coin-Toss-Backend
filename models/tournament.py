from pydantic import BaseModel
from datetime import datetime


class TournamentCreate(BaseModel):
    name: str
    start_time: datetime
    max_players: int = 4


class TournamentOut(BaseModel):
    id: int
    name: str
    status: str
    max_players: int
    current_players: int
    start_time: datetime
    created_at: datetime


class ParticipantRegister(BaseModel):
    tournament_id: int
    playfab_id: str
    display_name: str | None = None


class ParticipantOut(BaseModel):
    id: int
    tournament_id: int
    playfab_id: str
    display_name: str | None
    registered_at: datetime
    eliminated: bool
    final_position: int | None
    
class ParticipantListOut(BaseModel):
    tournament_id: int
    participants: list[ParticipantOut]