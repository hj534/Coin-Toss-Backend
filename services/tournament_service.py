from services.db import get_pool
from services.websocket_instance import manager
from config.events import (
    TOURNAMENT_UPDATED_EVENT,
    TOURNAMENT_ROUND_STARTED_EVENT,
    TOURNAMENT_COMPLETED_EVENT,
)
from models.tournament import (
    TournamentCreate,
    TournamentOut,
    ParticipantRegister,
    ParticipantOut,
    TournamentMatchOut,
    MatchResultSubmit,
    BracketMatchOut,
)
from datetime import timedelta


TOURNAMENT_DURATIONS = {
    "free": timedelta(hours=3),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}
class TournamentService:


    
    
    async def get_all_tournaments(self) -> list[TournamentOut]:
        print("Fetching all tournaments from the database")
        pool = get_pool()
        rows = await pool.fetch("SELECT * FROM tournaments ORDER BY id")
        return [TournamentOut(**dict(r)) for r in rows]

    async def create_tournament(self, payload: TournamentCreate) -> TournamentOut:
        pool = get_pool()

        existing = await pool.fetchval(
            """
            SELECT COUNT(*)
            FROM tournaments
            WHERE type = $1
              AND status NOT IN ('completed', 'cancelled')
            """,
            payload.type,
        )

        if existing > 0:
            raise ValueError(
                f"An active '{payload.type}' tournament already exists."
            )

        end_time = payload.start_time + TOURNAMENT_DURATIONS[payload.type]
        row = await pool.fetchrow(
            """
            INSERT INTO tournaments (name, start_time, end_time, max_players, type, sets, entry_fee)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            payload.name,
            payload.start_time,
            end_time,
            payload.max_players,
            payload.type,
            payload.sets,
            payload.entry_fee,
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

                winner_row = await conn.fetchrow(
                    """
                    SELECT id FROM tournament_participants
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

                await conn.execute(
                    """
                    UPDATE tournament_matches
                    SET winner_id = $1, status = 'completed', completed_at = NOW()
                    WHERE id = $2
                    """,
                    winner_id,
                    payload.match_id,
                )

                await conn.execute(
                    "UPDATE tournament_participants SET eliminated = TRUE WHERE id = $1",
                    loser_id,
                )

                # kitne matches hain is round mein total
                matches_in_round = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM tournament_matches
                    WHERE tournament_id = $1 AND round_number = $2
                    """,
                    match["tournament_id"],
                    match["round_number"],
                )

                if matches_in_round == 1:
                    # ye final match tha - champion mil gaya
                    await conn.execute(
                        "UPDATE tournaments SET status = 'completed' WHERE id = $1",
                        match["tournament_id"],
                    )
                    await conn.execute(
                        "INSERT INTO tournament_champions (tournament_id, participant_id) VALUES ($1, $2)",
                        match["tournament_id"],
                        winner_id,
                    )
                    champ = await conn.fetchrow(
                        "SELECT playfab_id FROM tournament_participants WHERE id = $1",
                        winner_id,
                    )
                    tournament_finished_data = (
                        match["tournament_id"],
                        [champ["playfab_id"]],
                    )
                else:
                    # apna 'pair partner' match dhoondo (jo mil kar agla round banayega)
                    partner_match_number = (
                        match["match_number"] + 1
                        if match["match_number"] % 2 == 1
                        else match["match_number"] - 1
                    )

                    partner = await conn.fetchrow(
                        """
                        SELECT winner_id, status
                        FROM tournament_matches
                        WHERE tournament_id = $1 AND round_number = $2 AND match_number = $3
                        FOR UPDATE
                        """,
                        match["tournament_id"],
                        match["round_number"],
                        partner_match_number,
                    )

                    if partner and partner["status"] == "completed":
                        next_round = match["round_number"] + 1
                        next_match_number = (
                            min(match["match_number"], partner_match_number) + 1
                        ) // 2

                        already_exists = await conn.fetchval(
                            """
                            SELECT COUNT(*) FROM tournament_matches
                            WHERE tournament_id = $1 AND round_number = $2 AND match_number = $3
                            """,
                            match["tournament_id"],
                            next_round,
                            next_match_number,
                        )

                        if not already_exists:
                            if match["match_number"] < partner_match_number:
                                player1_id, player2_id = winner_id, partner["winner_id"]
                            else:
                                player1_id, player2_id = partner["winner_id"], winner_id

                            room_name = (
                                f"tournament_{match['tournament_id']}"
                                f"_round_{next_round}_match_{next_match_number}"
                            )

                            await conn.execute(
                                """
                                INSERT INTO tournament_matches
                                    (tournament_id, round_number, match_number,
                                     player1_id, player2_id, scheduled_start_time, fusion_room_name)
                                VALUES ($1, $2, $3, $4, $5, NOW(), $6)
                                """,
                                match["tournament_id"],
                                next_round,
                                next_match_number,
                                player1_id,
                                player2_id,
                                room_name,
                            )

                            participants = await conn.fetch(
                                "SELECT playfab_id FROM tournament_participants WHERE id = ANY($1::int[])",
                                [player1_id, player2_id],
                            )
                            round_finished_data = (
                                match["tournament_id"],
                                [p["playfab_id"] for p in participants],
                            )

        if round_finished_data:
            tournament_id, playfab_ids = round_finished_data
            for pid in playfab_ids:
                await manager.send_event(pid, f"{TOURNAMENT_ROUND_STARTED_EVENT}:{tournament_id}")

        if tournament_finished_data:
            tournament_id, champion_playfab_ids = tournament_finished_data
            for pid in champion_playfab_ids:
                await manager.send_event(pid, f"{TOURNAMENT_COMPLETED_EVENT}:{tournament_id}")
                
                      
    async def _get_tournaments_by_type(self, tournament_type: str) -> list[TournamentOut]:
        pool = get_pool()
        rows = await pool.fetch(
            "SELECT * FROM tournaments WHERE type = $1 ORDER BY id",
            tournament_type,
        )
        return [TournamentOut(**dict(r)) for r in rows]

    async def get_free_tournaments(self) -> list[TournamentOut]:
        return await self._get_tournaments_by_type("free")

    async def get_daily_tournaments(self) -> list[TournamentOut]:
        return await self._get_tournaments_by_type("daily")

    async def get_weekly_tournaments(self) -> list[TournamentOut]:
        return await self._get_tournaments_by_type("weekly")

    async def get_monthly_tournaments(self) -> list[TournamentOut]:
        return await self._get_tournaments_by_type("monthly")
    
    async def get_tournament_bracket(self, tournament_id: int) -> list[BracketMatchOut]:
        pool = get_pool()
        rows = await pool.fetch(
            """
            SELECT
                tm.round_number,
                tm.match_number,
                tm.status,
                p1.display_name AS player1_display_name,
                p2.display_name AS player2_display_name,
                pw.display_name AS winner_display_name
            FROM tournament_matches tm
            LEFT JOIN tournament_participants p1 ON p1.id = tm.player1_id
            LEFT JOIN tournament_participants p2 ON p2.id = tm.player2_id
            LEFT JOIN tournament_participants pw ON pw.id = tm.winner_id
            WHERE tm.tournament_id = $1
            ORDER BY tm.round_number, tm.match_number
            """,
            tournament_id,
        )
        return [BracketMatchOut(**dict(r)) for r in rows]