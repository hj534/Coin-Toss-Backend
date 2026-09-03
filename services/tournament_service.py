from services.db import get_pool
from services.websocket_instance import manager
from config.events import TOURNAMENT_UPDATED_EVENT
from models.tournament import (
    TournamentCreate,
    TournamentOut,
    ParticipantRegister,
    ParticipantOut,
    TournamentMatchOut,
    MatchResultSubmit,
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

    async def get_my_tournament_match(
        self,
        tournament_id: int,
        playfab_id: str,
    ) -> TournamentMatchOut | None:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            SELECT
                tournament_match.id,
                tournament_match.tournament_id,
                tournament_match.round_number,
                tournament_match.match_number,
                tournament_match.status,
                tournament_match.scheduled_start_time,
                tournament_match.fusion_room_name,
                CASE
                    WHEN player1.playfab_id = $2 THEN player2.playfab_id
                    ELSE player1.playfab_id
                END AS opponent_playfab_id,
                CASE
                    WHEN player1.playfab_id = $2 THEN player2.display_name
                    ELSE player1.display_name
                END AS opponent_display_name
            FROM tournament_matches AS tournament_match
            JOIN tournament_participants AS player1
                ON player1.id = tournament_match.player1_id
            JOIN tournament_participants AS player2
                ON player2.id = tournament_match.player2_id
            WHERE tournament_match.tournament_id = $1
              AND (player1.playfab_id = $2 OR player2.playfab_id = $2)
              AND tournament_match.status IN ('pending', 'in_progress')
            ORDER BY tournament_match.round_number DESC, tournament_match.match_number
            LIMIT 1
            """,
            tournament_id,
            playfab_id,
        )

        return TournamentMatchOut(**dict(row)) if row else None

    async def _generate_round_1(self, conn, tournament_id: int):
        participants = await conn.fetch(
            """
            SELECT id
            FROM tournament_participants
            WHERE tournament_id = $1
              AND eliminated = FALSE
            ORDER BY registered_at, id
            """,
            tournament_id,
        )

        participant_count = len(participants)
        if participant_count < 2 or participant_count % 2 != 0:
            raise ValueError(
                f"Round 1 requires an even number of at least two participants; "
                f"found {participant_count} for tournament {tournament_id}"
            )

        existing_matches = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM tournament_matches
            WHERE tournament_id = $1
              AND round_number = 1
            """,
            tournament_id,
        )

        if existing_matches:
            raise ValueError(
                f"Round 1 matches already exist for tournament {tournament_id}"
            )

        matchups = [
            (match_number, participants[index]["id"], participants[index + 1]["id"])
            for match_number, index in enumerate(range(0, participant_count, 2), start=1)
        ]

        for match_number, player1_id, player2_id in matchups:
            fusion_room_name = (
                f"tournament_{tournament_id}_round_1_match_{match_number}"
            )

            await conn.execute(
                """
                INSERT INTO tournament_matches
                    (
                        tournament_id,
                        round_number,
                        match_number,
                        player1_id,
                        player2_id,
                        scheduled_start_time,
                        fusion_room_name
                    )
                VALUES ($1, 1, $2, $3, $4, NOW(), $5)
                """,
                tournament_id,
                match_number,
                player1_id,
                player2_id,
                fusion_room_name,
            )

        await conn.execute(
            """
            UPDATE tournaments
            SET status = 'started'
            WHERE id = $1
            """,
            tournament_id,
        )


async def submit_match_result(self, payload: MatchResultSubmit):
    pool = get_pool()
    round_finished_data = None
    tournament_finished_data = None

    async with pool.acquire() as conn:
        async with conn.transaction():
            match = await conn.fetchrow(
                """
                SELECT id, tournament_id, round_number, match_number,
                       player1_id, player2_id, status
                FROM tournament_matches
                WHERE id = $1
                FOR UPDATE
                """,
                payload.match_id,
            )

            if not match:
                raise ValueError("Match not found")

            if match["status"] == "completed":
                raise ValueError("Match already has a result")

            # winner ka playfab_id se uski participant id nikalo
            winner_row = await conn.fetchrow(
                """
                SELECT id, playfab_id
                FROM tournament_participants
                WHERE id = ANY($1::int[]) AND playfab_id = $2
                """,
                [match["player1_id"], match["player2_id"]],
                payload.winner_playfab_id,
            )

            if not winner_row:
                raise ValueError("Winner must be one of the two match players")

            winner_id = winner_row["id"]
            loser_id = (
                match["player2_id"]
                if winner_id == match["player1_id"]
                else match["player1_id"]
            )

            # match complete mark karo
            await conn.execute(
                """
                UPDATE tournament_matches
                SET winner_id = $1, status = 'completed', completed_at = NOW()
                WHERE id = $2
                """,
                winner_id,
                payload.match_id,
            )

            # loser ko eliminate karo
            await conn.execute(
                """
                UPDATE tournament_participants
                SET eliminated = TRUE
                WHERE id = $1
                """,
                loser_id,
            )

            # check karo poora round complete hua ya nahi
            pending_in_round = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM tournament_matches
                WHERE tournament_id = $1 AND round_number = $2
                  AND status != 'completed'
                """,
                match["tournament_id"],
                match["round_number"],
            )

            if pending_in_round == 0:
                # round ke saare winners nikalo, unke match_number ke order mein
                winners = await conn.fetch(
                    """
                    SELECT tm.winner_id
                    FROM tournament_matches tm
                    WHERE tm.tournament_id = $1 AND tm.round_number = $2
                    ORDER BY tm.match_number
                    """,
                    match["tournament_id"],
                    match["round_number"],
                )
                winner_ids = [w["winner_id"] for w in winners]

                if len(winner_ids) == 1:
                    # tournament khatam - champion mil gaya
                    await conn.execute(
                        "UPDATE tournaments SET status = 'completed' WHERE id = $1",
                        match["tournament_id"],
                    )
                    champ = await conn.fetchrow(
                        "SELECT playfab_id FROM tournament_participants WHERE id = $1",
                        winner_ids[0],
                    )
                    tournament_finished_data = (
                        match["tournament_id"],
                        champ["playfab_id"],
                    )
                else:
                    # agla round generate karo
                    next_round = match["round_number"] + 1
                    for i, mnum in enumerate(range(0, len(winner_ids), 2), start=1):
                        room_name = f"tournament_{match['tournament_id']}_round_{next_round}_match_{i}"
                        await conn.execute(
                            """
                            INSERT INTO tournament_matches
                                (tournament_id, round_number, match_number,
                                 player1_id, player2_id, scheduled_start_time, fusion_room_name)
                            VALUES ($1, $2, $3, $4, $5, NOW(), $6)
                            """,
                            match["tournament_id"],
                            next_round,
                            i,
                            winner_ids[mnum],
                            winner_ids[mnum + 1],
                            room_name,
                        )

                    participants = await conn.fetch(
                        "SELECT playfab_id FROM tournament_participants WHERE id = ANY($1::int[])",
                        winner_ids,
                    )
                    round_finished_data = (
                        match["tournament_id"],
                        [p["playfab_id"] for p in participants],
                    )

    # transaction ke bahar - notifications
    if round_finished_data:
        tournament_id, playfab_ids = round_finished_data
        for pid in playfab_ids:
            await manager.send_event(pid, f"{TOURNAMENT_ROUND_STARTED_EVENT}:{tournament_id}")

    if tournament_finished_data:
        tournament_id, champion_playfab_id = tournament_finished_data
        await manager.send_event(champion_playfab_id, f"{TOURNAMENT_COMPLETED_EVENT}:{tournament_id}")