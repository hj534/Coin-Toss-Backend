from services.db import get_pool
from services.websocket_instance import manager
from config.events import TOURNAMENT_UPDATED_EVENT
from models.tournament import (
    TournamentCreate,
    TournamentOut,
    ParticipantRegister,
    ParticipantOut,
)


class TournamentService:

    async def get_all_tournaments(self) -> list[TournamentOut]:
        print("Fetching all tournaments from the database")
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
        print("REGISTER: started", payload)

        pool = get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():

                tournament = await conn.fetchrow(
                    """
                    SELECT id, max_players, current_players
                    FROM tournaments
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    payload.tournament_id,
                )

                print("REGISTER: tournament fetched", tournament)

                if not tournament:
                    raise ValueError("Tournament not found")

                if tournament["current_players"] >= tournament["max_players"]:
                    raise ValueError("Tournament is full")

                row = await conn.fetchrow(
                    """
                    INSERT INTO tournament_participants
                        (tournament_id, playfab_id, display_name)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    payload.tournament_id,
                    payload.playfab_id,
                    payload.display_name,
                )


                await conn.execute(
                    """
                    UPDATE tournaments
                    SET current_players = current_players + 1
                    WHERE id = $1
                    """,
                    payload.tournament_id,
                )


        await manager.broadcast_event(
            f"{TOURNAMENT_UPDATED_EVENT}:{payload.tournament_id}"
        )


        return ParticipantOut(**dict(row))
    
    
    
    async def get_tournament_participants(self, tournament_id: int) -> list[ParticipantOut]:
     pool = get_pool()

     rows = await pool.fetch(
        """
        SELECT *
        FROM tournament_participants
        WHERE tournament_id = $1
        ORDER BY id
        """,
        tournament_id,
     )

     return [ParticipantOut(**dict(row)) for row in rows]
