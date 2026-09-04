from pydantic import BaseModel
from datetime import datetime
from pydantic import BaseModel, field_validator
 

class TournamentCreate(BaseModel):
    name: str
    max_players: int
    start_time: datetime

    @field_validator("max_players")
    @classmethod
    def validate_max_players(cls, value: int) -> int:
        allowed_values = {4, 8, 16, 32, 64}
        if value not in allowed_values:
            raise ValueError(
                f"max_players must be one of {sorted(allowed_values)}"
            )
        return value


class TournamentOut(BaseModel):
    id: int
    name: str
    status: str
    type: str
    max_players: int
    current_players: int
    start_time: datetime
    end_time: datetime
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


class TournamentMatchOut(BaseModel):
    id: int
    tournament_id: int
    round_number: int
    match_number: int
    status: str
    scheduled_start_time: datetime | None
    fusion_room_name: str | None
    opponent_playfab_id: str
    opponent_display_name: str | None
    
class ParticipantListOut(BaseModel):
    tournament_id: int
    participants: list[ParticipantOut]
    
class MatchResultSubmit(BaseModel):
    match_id: int
    winner_playfab_id: str
