from services.db import get_pool
from services.websocket_instance import manager
import json
import asyncio
from services.db import get_pool
from services.websocket_instance import manager
from config.events import (
    CASH_UPDATED_EVENT,
    POINTS_UPDATED_EVENT,
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
    LeaderboardEntryOut,
    MatchResultResponse,
    ParticipantResultOut,
    PlayerLeaderboardPointsOut,
    PlayerPrizeOut,
    PendingTournamentResultOut,
    ParticipantUnregister,
    UnregisterResponse

)
from datetime import datetime, timedelta, timezone

from services.email_service import send_tournament_winner_email
from services.playfab_service import (
    get_active_membership_id,
    update_playfab_cash,
)

TOURNAMENT_DURATIONS = {
    "free": timedelta(hours=3),
    "daily": timedelta(days=1),
    "weekly": timedelta(days=1),
    "monthly": timedelta(days=1),
    "bimonthly": timedelta(days=1),
}
TOURNAMENT_RANK_REWARDS = {
    0: [
        {"cash": 500, "points": 0},
        {"cash": 400, "points": 0},
        {"cash": 300, "points": 0},
        {"cash": 200, "points": 0},
        {"cash": 100, "points": 0},
        {"cash": 50, "points": 0},
        {"cash": 25, "points": 0},
        {"cash": 20, "points": 0},
        {"cash": 10, "points": 0},
        {"cash": 5, "points": 0},
    ],
    1000: [
        {"cash": 20000, "points": 600},
        {"cash": 15000, "points": 500},
        {"cash": 10000, "points": 400},
        {"cash": 8000, "points": 300},
        {"cash": 5000, "points": 200},
        {"cash": 3000, "points": 100},
        {"cash": 2000, "points": 50},
        {"cash": 1000, "points": 20},
        {"cash": 500, "points": 10},
        {"cash": 300, "points": 5},
    ],
    2000: [
        {"cash": 40000, "points": 1200},
        {"cash": 30000, "points": 1000},
        {"cash": 20000, "points": 800},
        {"cash": 10000, "points": 600},
        {"cash": 5000, "points": 400},
        {"cash": 2000, "points": 200},
        {"cash": 1000, "points": 100},
        {"cash": 800, "points": 50},
        {"cash": 400, "points": 20},
        {"cash": 200, "points": 10},
    ],
    3000: [
        {"cash": 100000, "points": 2400},
        {"cash": 80000, "points": 2000},
        {"cash": 50000, "points": 1600},
        {"cash": 30000, "points": 1200},
        {"cash": 20000, "points": 800},
        {"cash": 10000, "points": 400},
        {"cash": 5000, "points": 200},
        {"cash": 3000, "points": 100},
        {"cash": 2000, "points": 50},
        {"cash": 1000, "points": 25},
    ],
}
SPECIAL_TOURNAMENT_RANK_REWARDS = {
    "weekly": [
        {
            "points": 4000,
            "prizes": [
                {
                    "type": "bracelet",
                    "name": "14k gold Mint Wars monthly Champion bracelet",
                    "value": "1 bracelet",
                },
                {"type": "gift_card", "name": "$500 gift card", "value": "$500"},
            ],
        },
        {"points": 3000, "prizes": [{"type": "gift_card", "name": "$400 gift card", "value": "$400"}]},
        {"points": 2000, "prizes": [{"type": "gift_card", "name": "$200 gift card", "value": "$200"}]},
        {"points": 1000, "prizes": [{"type": "gift_card", "name": "$100 gift card", "value": "$100"}]},
        {"points": 800, "prizes": [{"type": "gift_card", "name": "$50 gift card", "value": "$50"}]},
        {"points": 500, "prizes": [{"type": "gift_card", "name": "$40 gift card", "value": "$40"}]},
        {"points": 200, "prizes": [{"type": "gift_card", "name": "$20 gift card", "value": "$20"}]},
        {"points": 100, "prizes": [{"type": "gift_card", "name": "$10 gift card", "value": "$10"}]},
        {"points": 50, "prizes": [{"type": "gift_card", "name": "$5 gift card", "value": "$5"}]},
        {"points": 20, "prizes": [{"type": "gift_card", "name": "$5 gift card", "value": "$5"}]},
    ],
    "monthly": [
        {
            "points": 8000,
            "prizes": [
                {
                    "type": "bracelet",
                    "name": "14k gold Mint Wars weekly champion bracelet",
                    "value": "1 bracelet",
                },
                {"type": "gift_card", "name": "$1000 gift card", "value": "$1000"},
            ],
        },
        {"points": 7000, "prizes": [{"type": "gift_card", "name": "$800 gift card", "value": "$800"}]},
        {"points": 6000, "prizes": [{"type": "gift_card", "name": "$700 gift card", "value": "$700"}]},
        {"points": 5000, "prizes": [{"type": "gift_card", "name": "$600 gift card", "value": "$600"}]},
        {"points": 4000, "prizes": [{"type": "gift_card", "name": "$400 gift card", "value": "$400"}]},
        {"points": 3000, "prizes": [{"type": "gift_card", "name": "$300 gift card", "value": "$300"}]},
        {"points": 2000, "prizes": [{"type": "gift_card", "name": "$200 gift card", "value": "$200"}]},
        {"points": 1000, "prizes": [{"type": "gift_card", "name": "$100 gift card", "value": "$100"}]},
        {"points": 400, "prizes": [{"type": "gift_card", "name": "$80 gift card", "value": "$80"}]},
        {"points": 200, "prizes": [{"type": "gift_card", "name": "$40 gift card", "value": "$40"}]},
    ],
    "bimonthly": [
        {
            "points": 18000,
            "prizes": [
                {
                    "type": "bracelet",
                    "name": "14k gold Mint Wars Champion bracelet",
                    "value": "1 bracelet",
                },
                {"type": "gift_card", "name": "$2000 gift card", "value": "$2000"},
            ],
        },
        {"points": 15000, "prizes": [{"type": "gift_card", "name": "$1000 gift card", "value": "$1000"}]},
        {"points": 10000, "prizes": [{"type": "gift_card", "name": "$800 gift card", "value": "$800"}]},
        {"points": 8000, "prizes": [{"type": "gift_card", "name": "$900 gift card", "value": "$900"}]},
        {"points": 6000, "prizes": [{"type": "gift_card", "name": "$700 gift card", "value": "$700"}]},
        {"points": 4000, "prizes": [{"type": "gift_card", "name": "$800 gift card", "value": "$800"}]},
        {"points": 3000, "prizes": [{"type": "gift_card", "name": "$500 gift card", "value": "$500"}]},
        {"points": 2000, "prizes": [{"type": "gift_card", "name": "$400 gift card", "value": "$400"}]},
        {"points": 1000, "prizes": [{"type": "gift_card", "name": "$300 gift card", "value": "$300"}]},
        {"points": 800, "prizes": [{"type": "gift_card", "name": "$200 gift card", "value": "$200"}]},
    ],
}


class TournamentService:


    async def get_tournament_by_id(self, tournament_id: int) -> TournamentOut | None:
        pool = get_pool()
        row = await pool.fetchrow(
            "SELECT * FROM tournaments WHERE id = $1",
            tournament_id,
        )
        return TournamentOut(**dict(row)) if row else None
    
    async def get_all_tournaments(self) -> list[TournamentOut]:
        print("Fetching all tournaments from the database")
        pool = get_pool()
        rows = await pool.fetch("SELECT * FROM tournaments ORDER BY id")
        return [TournamentOut(**dict(r)) for r in rows]

    async def create_tournament(self, payload: TournamentCreate) -> TournamentOut:
        pool = get_pool()

        end_time = payload.start_time + TOURNAMENT_DURATIONS[payload.type]
        prize = payload.entry_fee * 2

        row = await pool.fetchrow(
            """
            INSERT INTO tournaments
                (name, start_time, end_time, max_players, type, sets,
                 entry_fee, currency_type, round_time_seconds, prize)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            payload.name,
            payload.start_time,
            end_time,
            payload.max_players,
            payload.type,
            payload.sets,
            payload.entry_fee,
            payload.currency_type,
            payload.round_time_seconds,
            prize,
        )
        return TournamentOut(**dict(row))

    async def register_participant(self, payload: ParticipantRegister) -> ParticipantOut:
        print("REGISTER: started", payload)

        pool = get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():

                already_active = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM tournament_participants tp
                    JOIN tournaments t ON t.id = tp.tournament_id
                    WHERE tp.playfab_id = $1
                      AND t.status NOT IN ('completed', 'cancelled')
                    """,
                    payload.playfab_id,
                )

                if already_active > 0:
                    raise ValueError(
                        "You are already registered in an active tournament. "
                        "Finish or wait for it to end before joining another."
                    )

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
                        (tournament_id, playfab_id, display_name, email)
                    VALUES ($1, $2, $3, $4)
                    RETURNING *
                    """,
                    payload.tournament_id,
                    payload.playfab_id,
                    payload.display_name,
                    payload.email,
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
    
    
    async def unregister_participant(
        self, payload: ParticipantUnregister
    ) -> UnregisterResponse:
        pool = get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():
                # register_participant ki tarah same row lock, taake
                # register/unregister/scheduler aapas mein race na karein
                tournament = await conn.fetchrow(
                    """
                    SELECT id, status, start_time
                    FROM tournaments
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    payload.tournament_id,
                )

                if not tournament:
                    raise ValueError("Tournament not found")

                if tournament["status"] != "registration":
                    raise ValueError(
                        "Tournament has already started. You can no longer unregister."
                    )

                start_time = tournament["start_time"]
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) >= start_time:
                    raise ValueError(
                        "Tournament is about to start. You can no longer unregister."
                    )

                deleted = await conn.fetchrow(
                    """
                    DELETE FROM tournament_participants
                    WHERE tournament_id = $1
                      AND playfab_id = $2
                    RETURNING id
                    """,
                    payload.tournament_id,
                    payload.playfab_id,
                )

                if not deleted:
                    raise ValueError("You are not registered in this tournament")

                # +1/-1 ki jagah actual count se sync, taake count kabhi galat na ho
                current_players = await conn.fetchval(
                    """
                    UPDATE tournaments
                    SET current_players = (
                        SELECT COUNT(*)
                        FROM tournament_participants
                        WHERE tournament_id = $1
                    )
                    WHERE id = $1
                    RETURNING current_players
                    """,
                    payload.tournament_id,
                )

        await manager.broadcast_event(
            f"{TOURNAMENT_UPDATED_EVENT}:{payload.tournament_id}"
        )

        return UnregisterResponse(
            success=True,
            tournament_id=payload.tournament_id,
            playfab_id=payload.playfab_id,
            current_players=current_players,
        )
    
    
    
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
                t.sets,
                t.entry_fee,
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
            JOIN tournaments AS t
                ON t.id = tournament_match.tournament_id
            WHERE tournament_match.tournament_id = $1
              AND (player1.playfab_id = $2 OR player2.playfab_id = $2)
              AND tournament_match.status IN ('pending', 'in_progress')
            ORDER BY tournament_match.round_number DESC, tournament_match.match_number
            LIMIT 1
            """,
            tournament_id,
            playfab_id,
        )

        if row:
            return TournamentMatchOut(**dict(row))

        waiting = await pool.fetchrow(
            """
            SELECT
                t.id AS tournament_id,
                t.status AS tournament_status,
                t.start_time,
                t.sets,
                t.entry_fee
            FROM tournaments AS t
            JOIN tournament_participants AS participant
                ON participant.tournament_id = t.id
            WHERE t.id = $1
              AND participant.playfab_id = $2
              AND t.status = 'registration'
            LIMIT 1
            """,
            tournament_id,
            playfab_id,
        )

        if not waiting:
            return None

        start_time = waiting["start_time"]
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        seconds_until_start = max(0, int((start_time - now).total_seconds()))
        status = (
            "waiting_for_tournament_start"
            if seconds_until_start > 0
            else "waiting_for_players"
        )

        return TournamentMatchOut(
            tournament_id=waiting["tournament_id"],
            status=status,
            sets=waiting["sets"],
            entry_fee=waiting["entry_fee"],
            tournament_start_time=start_time,
            seconds_until_start=seconds_until_start,
        )

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

    async def _get_tournament_reward_recipients(
        self,
        conn,
        tournament_id: int,
    ) -> list[dict]:
        tournament = await conn.fetchrow(
            "SELECT id, name, type, entry_fee FROM tournaments WHERE id = $1",
            tournament_id,
        )

        if not tournament:
            return []

        if tournament["type"] in {"free", "daily"}:
            reward_table = TOURNAMENT_RANK_REWARDS.get(tournament["entry_fee"])
        else:
            reward_table = SPECIAL_TOURNAMENT_RANK_REWARDS.get(tournament["type"])

        if not reward_table:
            return []
        
        rows = await conn.fetch(
            """
            WITH ranked_players AS (
                SELECT
                    participant.id,
                    participant.playfab_id,
                    participant.display_name,
                    participant.registered_at,
                    participant.eliminated,
                    COUNT(match.id) AS wins,
                    EXISTS (
                        SELECT 1
                        FROM tournament_champions champion
                        WHERE champion.tournament_id = participant.tournament_id
                          AND champion.participant_id = participant.id
                    ) AS is_champion
                FROM tournament_participants participant
                LEFT JOIN tournament_matches match
                    ON match.tournament_id = participant.tournament_id
                   AND match.winner_id = participant.id
                WHERE participant.tournament_id = $1
                GROUP BY
                    participant.id,
                    participant.playfab_id,
                    participant.display_name,
                    participant.registered_at,
                    participant.eliminated
            )
            SELECT playfab_id, display_name, wins
            FROM ranked_players
            ORDER BY is_champion DESC, wins DESC, eliminated ASC, registered_at ASC, id ASC
            LIMIT $2
            """,
            tournament_id,
            len(reward_table),
        )

        return [
            {
                "playfab_id": row["playfab_id"],
                "display_name": row["display_name"],
                "cash": reward_table[index].get("cash", 0),
                "points": reward_table[index].get("points", 0),
                "prizes": reward_table[index].get("prizes", []),
                "rank": index + 1,
                "tournament_id": tournament["id"],
                "tournament_name": tournament["name"],
            }
            for index, row in enumerate(rows)
        ]

    async def _award_tournament_rewards(
        self,
        rewards: list[dict],
    ):
        pool = get_pool()
        async with pool.acquire() as conn:
            for reward in rewards:
                playfab_id = reward["playfab_id"]
                display_name = reward["display_name"] or playfab_id
                points_reward = reward["points"]
                active_membership_id = get_active_membership_id(playfab_id)
                await conn.execute(
                    """
                    INSERT INTO player_leaderboard
                        (playfab_id, display_name, points, active_membership_id, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (playfab_id) DO UPDATE
                    SET
                        display_name = EXCLUDED.display_name,
                        points = player_leaderboard.points + EXCLUDED.points,
                        active_membership_id = EXCLUDED.active_membership_id,
                        updated_at = NOW()
                    """,
                    playfab_id,
                    display_name,
                    max(points_reward, 0),
                    active_membership_id or "",
                )

                # naya hissa - ek dafa dikhane wala pending result save karo
                await conn.execute(
                    """
                    INSERT INTO pending_tournament_results
                        (playfab_id, tournament_id, tournament_name, rank, cash, points, prizes)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (playfab_id) DO UPDATE
                    SET
                        tournament_id = EXCLUDED.tournament_id,
                        tournament_name = EXCLUDED.tournament_name,
                        rank = EXCLUDED.rank,
                        cash = EXCLUDED.cash,
                        points = EXCLUDED.points,
                        prizes = EXCLUDED.prizes,
                        created_at = NOW()
                    """,
                    playfab_id,
                    reward["tournament_id"],
                    reward["tournament_name"],
                    reward["rank"],
                    reward["cash"],
                    points_reward,
                    json.dumps(reward["prizes"]),
                )

                for prize in reward["prizes"]:
                    await conn.execute(
                        """
                        INSERT INTO player_prizes
                            (
                                playfab_id,
                                display_name,
                                tournament_id,
                                tournament_name,
                                rank,
                                prize_type,
                                prize_name,
                                prize_value
                            )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (
                            playfab_id,
                            tournament_id,
                            rank,
                            prize_type,
                            prize_name
                        ) DO NOTHING
                        """,
                        playfab_id,
                        display_name,
                        reward["tournament_id"],
                        reward["tournament_name"],
                        reward["rank"],
                        prize["type"],
                        prize["name"],
                        prize.get("value", ""),
                    )

        for reward in rewards:
            playfab_id = reward["playfab_id"]
            cash_reward = reward["cash"]
            points_reward = reward["points"]
            rank = reward["rank"]
            cash_success = True

            if cash_reward > 0:
                cash_success = update_playfab_cash(playfab_id, cash_reward)

            if cash_success and cash_reward > 0:
                await manager.send_event(playfab_id, CASH_UPDATED_EVENT)

            if points_reward > 0:
                await manager.send_event(playfab_id, POINTS_UPDATED_EVENT)

            if cash_success:
                print(
                    f"Tournament rank {rank} reward paid: "
                    f"{cash_reward} cash and {points_reward} leaderboard points to {playfab_id}"
                )
            else:
                print(
                    f"Failed to fully pay tournament rank {rank} cash reward "
                    f"({cash_reward} cash) to {playfab_id}"
                )            
                    
    async def submit_match_result(self, payload: MatchResultSubmit) -> MatchResultResponse:
        pool = get_pool()
        round_finished_data = None
        tournament_finished_data = None
        tournament_info = None
        champ_email = None
        tournament_rewards: list[dict] = []

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

                    # naya hissa - email aur tournament details fetch karo
                    tournament_info = await conn.fetchrow(
                        "SELECT name, prize, currency_type FROM tournaments WHERE id = $1",
                        match["tournament_id"],
                    )
                    champ_email = await conn.fetchrow(
                        "SELECT email FROM tournament_participants WHERE id = $1",
                        winner_id,
                    )
                    tournament_rewards = await self._get_tournament_reward_recipients(
                        conn,
                        match["tournament_id"],
                    )

                    tournament_finished_data = (
                        match["tournament_id"],
                        [champ["playfab_id"]],
                    )
                else:
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

        # transaction ke bahar - notifications
        if round_finished_data:
            tournament_id, playfab_ids = round_finished_data
            for pid in playfab_ids:
                await manager.send_event(pid, f"{TOURNAMENT_ROUND_STARTED_EVENT}:{tournament_id}")

        if tournament_finished_data:
            tournament_id, champion_playfab_ids = tournament_finished_data

            # naya hissa - email bhejna
            if champ_email and champ_email["email"]:
                send_tournament_winner_email(
                    champ_email["email"],
                    tournament_info["name"],
                    tournament_info["prize"],
                    tournament_info["currency_type"],
                )

            if tournament_rewards:
                await self._award_tournament_rewards(tournament_rewards)

            for pid in champion_playfab_ids:
                await manager.send_event(pid, f"{TOURNAMENT_COMPLETED_EVENT}:{tournament_id}")

            return MatchResultResponse(
                tournament_completed=True,
                winner_playfab_ids=champion_playfab_ids,
                prize=tournament_info["prize"],
                currency_type=tournament_info["currency_type"],
            )

        return MatchResultResponse(tournament_completed=False)            
    async def _get_tournaments_by_type(self, tournament_type: str) -> list[TournamentOut]:
        pool = get_pool()
        rows = await pool.fetch(
            """
            SELECT * FROM tournaments
            WHERE type = $1
              AND status NOT IN ('completed', 'cancelled')
            ORDER BY id
            """,
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

    async def get_bimonthly_tournaments(self) -> list[TournamentOut]:
        return await self._get_tournaments_by_type("bimonthly")
    
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
    
    async def get_my_active_tournament(self, playfab_id: str) -> TournamentOut | None:
        pool = get_pool()
        row = await pool.fetchrow(
            """
            SELECT t.*
            FROM tournaments t
            JOIN tournament_participants tp ON tp.tournament_id = t.id
            WHERE tp.playfab_id = $1
              AND t.status NOT IN ('completed', 'cancelled')
            ORDER BY tp.registered_at DESC
            LIMIT 1
            """,
            playfab_id,
        )
        return TournamentOut(**dict(row)) if row else None
    
    
        _period_tables_ready = False

    async def _ensure_period_tables(self):
        if TournamentService._period_tables_ready:
            return
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS period_leaderboard (
                    period_type TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    playfab_id TEXT NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (period_type, period_key, playfab_id)
                );

                CREATE TABLE IF NOT EXISTS leaderboard_period_rewards (
                    id SERIAL PRIMARY KEY,
                    period_type TEXT NOT NULL,
                    period_key TEXT NOT NULL,
                    playfab_id TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    rank INTEGER NOT NULL,
                    points INTEGER NOT NULL DEFAULT 0,
                    cash INTEGER NOT NULL DEFAULT 0,
                    prizes JSONB NOT NULL DEFAULT '[]'::jsonb,
                    cash_paid BOOLEAN NOT NULL DEFAULT FALSE,
                    seen BOOLEAN NOT NULL DEFAULT FALSE,
                    awarded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (period_type, period_key, playfab_id)
                );
                """
            )
        TournamentService._period_tables_ready = True

    async def _add_period_points(self, conn, playfab_id: str, points: int):
        """Weekly + monthly points. Fail ho to sirf log, tournament flow na ruke."""
        if points <= 0:
            return
        try:
            await self._ensure_period_tables()
            now = datetime.now(timezone.utc)
            for period_type in LEADERBOARD_PERIODS:
                await conn.execute(
                    """
                    INSERT INTO period_leaderboard
                        (period_type, period_key, playfab_id, points, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (period_type, period_key, playfab_id) DO UPDATE
                    SET points = period_leaderboard.points + EXCLUDED.points,
                        updated_at = NOW()
                    """,
                    period_type,
                    _period_key(period_type, now),
                    playfab_id,
                    points,
                )
        except Exception as e:
            print(f"Failed to add weekly/monthly points for {playfab_id}: {e}")

    def _validate_period_type(self, period_type: str):
        if period_type not in LEADERBOARD_PERIODS:
            raise ValueError(f"period_type must be one of {list(LEADERBOARD_PERIODS)}")

    async def get_period_leaderboard(
        self, period_type: str, limit: int = 50
    ) -> list[LeaderboardEntryOut]:
        self._validate_period_type(period_type)
        await self._ensure_period_tables()
        key = _period_key(period_type, datetime.now(timezone.utc))

        pool = get_pool()
        rows = await pool.fetch(
            """
            SELECT pl.playfab_id, pl.display_name, p.points AS wins, p.points
            FROM period_leaderboard p
            JOIN player_leaderboard pl ON pl.playfab_id = p.playfab_id
            WHERE p.period_type = $1
              AND p.period_key = $2
              AND p.points > 0
              AND pl.active_membership_id <> ''
            ORDER BY p.points DESC, p.updated_at ASC
            LIMIT $3
            """,
            period_type,
            key,
            limit,
        )
        return [LeaderboardEntryOut(**dict(row)) for row in rows]

    async def get_leaderboard_period_info(self, period_type: str) -> LeaderboardPeriodInfoOut:
        self._validate_period_type(period_type)
        now = datetime.now(timezone.utc)
        start, end = _period_bounds(period_type, now)
        return LeaderboardPeriodInfoOut(
            period_type=period_type,
            period_key=_period_key(period_type, now),
            starts_at=start,
            ends_at=end,
            seconds_until_reset=max(0, int((end - now).total_seconds())),
        )

    async def settle_leaderboard_period(self, period_type: str, period_key: str):
        """Khatam ho chuke period ke top players ko reward do. Dobara chalane se double reward nahi milta."""
        await self._ensure_period_tables()
        reward_table = LEADERBOARD_REWARD_TABLES[period_type]
        pool = get_pool()

        async with pool.acquire() as conn:
            winners = await conn.fetch(
                """
                SELECT p.playfab_id, pl.display_name, p.points
                FROM period_leaderboard p
                JOIN player_leaderboard pl ON pl.playfab_id = p.playfab_id
                WHERE p.period_type = $1
                  AND p.period_key = $2
                  AND p.points > 0
                  AND pl.active_membership_id <> ''
                ORDER BY p.points DESC, p.updated_at ASC
                LIMIT $3
                """,
                period_type,
                period_key,
                len(reward_table),
            )

            for index, row in enumerate(winners):
                reward = reward_table[index]
                cash = reward.get("cash", 0)
                await conn.execute(
                    """
                    INSERT INTO leaderboard_period_rewards
                        (period_type, period_key, playfab_id, display_name,
                         rank, points, cash, prizes, cash_paid)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)
                    ON CONFLICT (period_type, period_key, playfab_id) DO NOTHING
                    """,
                    period_type,
                    period_key,
                    row["playfab_id"],
                    row["display_name"] or row["playfab_id"],
                    index + 1,
                    row["points"],
                    cash,
                    json.dumps(reward.get("prizes", [])),
                    cash <= 0,
                )

            # Jin ka cash baqi hai (naye + pichli dafa fail hue), unhein pay karo
            unpaid = await conn.fetch(
                """
                SELECT id, playfab_id, cash, rank
                FROM leaderboard_period_rewards
                WHERE period_type = $1 AND period_key = $2 AND cash_paid = FALSE
                """,
                period_type,
                period_key,
            )

            for reward in unpaid:
                # Pehle claim karo (do instance hon to bhi double payment na ho)
                claimed = await conn.fetchval(
                    """
                    UPDATE leaderboard_period_rewards
                    SET cash_paid = TRUE
                    WHERE id = $1 AND cash_paid = FALSE
                    RETURNING id
                    """,
                    reward["id"],
                )
                if not claimed:
                    continue

                success = update_playfab_cash(reward["playfab_id"], reward["cash"])
                if success:
                    await manager.send_event(reward["playfab_id"], CASH_UPDATED_EVENT)
                    print(
                        f"{period_type} leaderboard {period_key} rank {reward['rank']}: "
                        f"paid {reward['cash']} cash to {reward['playfab_id']}"
                    )
                else:
                    await conn.execute(
                        "UPDATE leaderboard_period_rewards SET cash_paid = FALSE WHERE id = $1",
                        reward["id"],
                    )
                    print(
                        f"Failed to pay {period_type} leaderboard cash "
                        f"to {reward['playfab_id']}, will retry"
                    )

    async def settle_finished_leaderboard_periods(self):
        now = datetime.now(timezone.utc)
        for period_type in LEADERBOARD_PERIODS:
            start, _ = _period_bounds(period_type, now)
            # Pichle 2 mukammal periods (server band raha ho to catch-up ho jaye)
            for _ in range(2):
                previous_start, _ = _period_bounds(period_type, start - timedelta(seconds=1))
                await self.settle_leaderboard_period(
                    period_type, _period_key(period_type, previous_start)
                )
                start = previous_start

    async def leaderboard_settlement_loop(self, interval_seconds: int = 300):
        while True:
            try:
                await self.settle_finished_leaderboard_periods()
            except Exception as e:
                print(f"Leaderboard settlement error: {e}")
            await asyncio.sleep(interval_seconds)

    async def get_pending_leaderboard_rewards(
        self, playfab_id: str
    ) -> list[PeriodLeaderboardRewardOut]:
        """Player ko ek dafa dikhane ke liye; dikhane ke baad seen=TRUE ho jata hai."""
        await self._ensure_period_tables()
        pool = get_pool()
        rows = await pool.fetch(
            """
            UPDATE leaderboard_period_rewards
            SET seen = TRUE
            WHERE playfab_id = $1 AND seen = FALSE AND cash_paid = TRUE
            RETURNING period_type, period_key, rank, points, cash, prizes, awarded_at
            """,
            playfab_id,
        )

        result = []
        for row in sorted(rows, key=lambda r: r["awarded_at"]):
            data = dict(row)
            prizes = data["prizes"]
            data["prizes"] = json.loads(prizes) if isinstance(prizes, str) else prizes
            result.append(PeriodLeaderboardRewardOut(**data))
        return result
    
    
    
    
    
    async def get_leaderboard(
        self,
        limit: int = 50,
        playfab_id: str | None = None,
        display_name: str | None = None,
    ) -> list[LeaderboardEntryOut]:
        pool = get_pool()
        async with pool.acquire() as conn:
            known_players = await conn.fetch(
                """
                WITH known_players AS (
                    SELECT
                        tp.playfab_id,
                        MAX(tp.display_name) AS display_name
                    FROM tournament_participants tp
                    GROUP BY tp.playfab_id

                    UNION ALL

                    SELECT
                        $1::text AS playfab_id,
                        $2::text AS display_name
                    WHERE $1 IS NOT NULL AND $1 <> ''
                )
                SELECT
                    playfab_id,
                    COALESCE(MAX(NULLIF(display_name, '')), playfab_id) AS display_name
                FROM known_players
                WHERE playfab_id IS NOT NULL AND playfab_id <> ''
                GROUP BY playfab_id
                """,
                playfab_id,
                display_name,
            )

            for row in known_players:
                active_membership_id = get_active_membership_id(row["playfab_id"])
                await conn.execute(
                    """
                    INSERT INTO player_leaderboard
                        (playfab_id, display_name, points, active_membership_id, updated_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (playfab_id) DO UPDATE
                    SET
                        display_name = EXCLUDED.display_name,
                        active_membership_id = EXCLUDED.active_membership_id,
                        updated_at = NOW()
                    """,
                    row["playfab_id"],
                    row["display_name"],
                    0,
                    active_membership_id or "",
                )

            rows = await conn.fetch(
                """
                SELECT playfab_id, display_name, points AS wins, points
                FROM player_leaderboard
                WHERE active_membership_id <> ''
                ORDER BY points DESC, updated_at ASC
                LIMIT $1
                """,
                limit,
            )

        return [LeaderboardEntryOut(**dict(row)) for row in rows]

    async def get_player_leaderboard_points(
        self,
        playfab_id: str,
        display_name: str | None = None,
    ) -> PlayerLeaderboardPointsOut:
        active_membership_id = get_active_membership_id(playfab_id)
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO player_leaderboard
                    (playfab_id, display_name, points, active_membership_id, updated_at)
                VALUES ($1, $2, 0, $3, NOW())
                ON CONFLICT (playfab_id) DO UPDATE
                SET
                    display_name = COALESCE(NULLIF(EXCLUDED.display_name, ''), player_leaderboard.display_name),
                    active_membership_id = EXCLUDED.active_membership_id,
                    updated_at = NOW()
                RETURNING playfab_id, points
                """,
                playfab_id,
                display_name or playfab_id,
                active_membership_id or "",
            )

        return PlayerLeaderboardPointsOut(
            playfab_id=row["playfab_id"],
            points=row["points"],
            leaderboard_eligible=bool(active_membership_id),
        )
    
    async def get_tournament_results(self, tournament_id: int) -> list[ParticipantResultOut]:
        pool = get_pool()
        rows = await pool.fetch(
            """
            SELECT
                tp.playfab_id,
                tp.display_name,
                tp.eliminated,
                EXISTS (
                    SELECT 1 FROM tournament_champions tc
                    WHERE tc.tournament_id = $1 AND tc.participant_id = tp.id
                ) AS is_champion
            FROM tournament_participants tp
            WHERE tp.tournament_id = $1
            ORDER BY is_champion DESC, tp.eliminated ASC, tp.display_name
            """,
            tournament_id,
        )
        return [ParticipantResultOut(**dict(r)) for r in rows]

    async def get_player_prizes(self, playfab_id: str) -> list[PlayerPrizeOut]:
        pool = get_pool()
        rows = await pool.fetch(
            """
            SELECT
                id,
                playfab_id,
                display_name,
                tournament_id,
                tournament_name,
                rank,
                prize_type,
                prize_name,
                prize_value,
                status,
                earned_at,
                delivered_at,
                admin_notes
            FROM player_prizes
            WHERE playfab_id = $1
            ORDER BY earned_at DESC, id DESC
            """,
            playfab_id,
        )
        return [PlayerPrizeOut(**dict(row)) for row in rows]
    
    async def get_and_clear_pending_result(
        self, playfab_id: str
    ) -> PendingTournamentResultOut | None:
        pool = get_pool()
        row = await pool.fetchrow(
            "DELETE FROM pending_tournament_results WHERE playfab_id = $1 RETURNING *",
            playfab_id,
        )
        if not row:
            return None

        data = dict(row)
        prizes = data["prizes"]
        data["prizes"] = json.loads(prizes) if isinstance(prizes, str) else prizes
        return PendingTournamentResultOut(**data)
    
    
    async def get_prize_breakdown(self, tournament_id: int) -> list[dict]:
        pool = get_pool()
        tournament = await pool.fetchrow(
            "SELECT id, type, entry_fee FROM tournaments WHERE id = $1",
            tournament_id,
        )

        if not tournament:
            return []

        if tournament["type"] in {"free", "daily"}:
            reward_table = TOURNAMENT_RANK_REWARDS.get(tournament["entry_fee"], [])
        else:
            reward_table = SPECIAL_TOURNAMENT_RANK_REWARDS.get(tournament["type"], [])

        return [
            {
                "rank": index + 1,
                "cash": entry.get("cash", 0),
                "points": entry.get("points", 0),
                "prizes": entry.get("prizes", []),
            }
            for index, entry in enumerate(reward_table)
        ]
        
        
        
LEADERBOARD_PERIODS = ("weekly", "monthly")

WEEKLY_LEADERBOARD_REWARDS = [
    {"cash": 5000, "prizes": []},
    {"cash": 3000, "prizes": []},
    {"cash": 2000, "prizes": []},
    {"cash": 1000, "prizes": []},
    {"cash": 500, "prizes": []},
]

MONTHLY_LEADERBOARD_REWARDS = [
    {"cash": 20000, "prizes": [{"type": "gift_card", "name": "$100 gift card", "value": "$100"}]},
    {"cash": 10000, "prizes": []},
    {"cash": 5000, "prizes": []},
    {"cash": 3000, "prizes": []},
    {"cash": 2000, "prizes": []},
]

LEADERBOARD_REWARD_TABLES = {
    "weekly": WEEKLY_LEADERBOARD_REWARDS,
    "monthly": MONTHLY_LEADERBOARD_REWARDS,
}


def _period_bounds(period_type: str, moment: datetime) -> tuple[datetime, datetime]:
    """UTC mein period ki start/end. Weekly = Monday se, monthly = 1 tareekh se."""
    moment = moment.astimezone(timezone.utc)
    if period_type == "weekly":
        start = (moment - timedelta(days=moment.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start, start + timedelta(days=7)

    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _period_key(period_type: str, moment: datetime) -> str:
    moment = moment.astimezone(timezone.utc)
    if period_type == "weekly":
        iso = moment.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return f"{moment.year}-{moment.month:02d}"