from services.db import get_pool
from models.tournament import (
    TournamentCreate,
    TournamentOut,
    ParticipantRegister,
    ParticipantOut,
)


class TournamentService:

    async def get_all_tournaments(self) -> list[TournamentOut]:
        pool = get_pool()
        rows = await pool.fetch("SELECT * FROM tournaments ORDER BY id")
        return [TournamentOut(**dict(r)) for r in rows]

    async def create_tournament(self, payload: TournamentCreate) -> TournamentOut:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO tournaments (name, start_time, max_players)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            payload.name,
            payload.start_time,
            payload.max_players,
        )
        return TournamentOut(**dict(row))

    async def register_participant(self, payload: ParticipantRegister) -> ParticipantOut:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            INSERT INTO tournament_participants (tournament_id, playfab_id, display_name)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            payload.tournament_id,
            payload.playfab_id,
            payload.display_name,
        )
        return ParticipantOut(**dict(row))