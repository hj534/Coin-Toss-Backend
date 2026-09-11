from pydantic import BaseModel
from datetime import datetime
from pydantic import BaseModel, field_validator
 
class TournamentCreate(BaseModel):
    name: str
    max_players: int
    start_time: datetime
    type: str
    sets: int
    entry_fee: int

    @field_validator("max_players")
    @classmethod
    def validate_max_players(cls, value: int) -> int:
        allowed_values = {4, 8, 16, 32, 64}
        if value not in allowed_values:
            raise ValueError(f"max_players must be one of {sorted(allowed_values)}")
        return value

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed_types = {"free", "daily", "weekly", "monthly"}
        if value not in allowed_types:
            raise ValueError(f"type must be one of {sorted(allowed_types)}")
        return value

    @field_validator("sets")
    @classmethod
    def validate_sets(cls, value: int) -> int:
        if value < 1 or value % 2 == 0:
            raise ValueError("sets must be a positive odd number (e.g. 1, 3, 5, 7)")
        return value

    @field_validator("entry_fee")
    @classmethod
    def validate_entry_fee(cls, value: int) -> int:
        if value < 0:
            raise ValueError("entry_fee cannot be negative")
        return value


class TournamentOut(BaseModel):
    id: int
    name: str
    status: str
    type: str
    sets: int
    entry_fee: int
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
    scheduled_start_time: datetime
    fusion_room_name: str
    sets: int
    entry_fee: int
    opponent_playfab_id: str
    opponent_display_name: str
    
class ParticipantListOut(BaseModel):
    tournament_id: int
    participants: list[ParticipantOut]
    
class MatchResultSubmit(BaseModel):
    match_id: int
    winner_playfab_id: str

class BracketMatchOut(BaseModel):
    round_number: int
    match_number: int
    status: str
    player1_display_name: str | None = None
    player2_display_name: str | None = None
    winner_display_name: str | None = None