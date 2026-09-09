import asyncio
from services.db import get_pool
from services.websocket_instance import manager
from config.events import TOURNAMENT_STARTED_EVENT
from services.tournament_service import TournamentService
from config.events import TOURNAMENT_STARTED_EVENT, TOURNAMENT_COMPLETED_EVENT

POLL_INTERVAL_SECONDS = 15

service = TournamentService()
_task: asyncio.Task | None = None


async def _check_due_tournaments():
    pool = get_pool()
    started_tournaments: list[tuple[int, list[str]]] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            due = await conn.fetch(
                """
                SELECT id, max_players, current_players
                FROM tournaments
                WHERE status = 'registration'
                  AND start_time <= NOW()
                FOR UPDATE
                """
            )

            for row in due:
                if row["current_players"] == row["max_players"]:
                    await service._generate_round_1(conn, row["id"])
                    participants = await conn.fetch(
                        """
                        SELECT playfab_id
                        FROM tournament_participants
                        WHERE tournament_id = $1
                        ORDER BY registered_at, id
                        """,
                        row["id"],
                    )
                    started_tournaments.append(
                        (row["id"], [participant["playfab_id"] for participant in participants])
                    )
                    # notifications happen after the transaction commits, below
                else:
                    print(
                        f"Tournament {row['id']} reached start_time but only "
                        f"{row['current_players']}/{row['max_players']} players "
                        f"registered — leaving as-is for now."
                    )

    # Notify participants for any tournaments that just started after commit.
    for tournament_id, playfab_ids in started_tournaments:
        for playfab_id in playfab_ids:
            await manager.send_event(
                playfab_id,
                f"{TOURNAMENT_STARTED_EVENT}:{tournament_id}",
            )


async def _loop():
    while True:
        try:
            print("Running scheduler tick")
            await _check_due_tournaments()
            await _check_expired_tournaments()
        except Exception as e:
            print(f"Scheduler tick failed: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_scheduler():
    global _task
    _task = asyncio.create_task(_loop())


def stop_scheduler():
    if _task:
        _task.cancel()


async def _check_expired_tournaments():
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            expired = await conn.fetch(
                """
                SELECT id, name
                FROM tournaments
                WHERE end_time <= NOW()
                  AND status NOT IN ('completed', 'cancelled')
                FOR UPDATE
                """
            )

            for tournament in expired:
                tournament_id = tournament["id"]

                any_match_exists = await conn.fetchval(
                    "SELECT COUNT(*) FROM tournament_matches WHERE tournament_id = $1",
                    tournament_id,
                )

                if not any_match_exists:
                    await conn.execute(
                        "UPDATE tournaments SET status = 'cancelled' WHERE id = $1",
                        tournament_id,
                    )
                    print(f"Tournament {tournament_id} expired with no matches — cancelled.")
                    continue

                # sabse zyada matches jeetne wale (non-eliminated) players dhoondo
                leaders = await conn.fetch(
                    """
                    WITH win_counts AS (
                        SELECT p.id AS participant_id, p.playfab_id, COUNT(tm.id) AS wins
                        FROM tournament_participants p
                        LEFT JOIN tournament_matches tm
                            ON tm.winner_id = p.id AND tm.tournament_id = $1
                        WHERE p.tournament_id = $1 AND p.eliminated = FALSE
                        GROUP BY p.id, p.playfab_id
                    ),
                    max_wins AS (
                        SELECT COALESCE(MAX(wins), 0) AS max_wins FROM win_counts
                    )
                    SELECT wc.participant_id, wc.playfab_id
                    FROM win_counts wc, max_wins mw
                    WHERE wc.wins = mw.max_wins
                    """,
                    tournament_id,
                )

                for leader in leaders:
                    await conn.execute(
                        "INSERT INTO tournament_champions (tournament_id, participant_id) VALUES ($1, $2)",
                        tournament_id,
                        leader["participant_id"],
                    )

                await conn.execute(
                    "UPDATE tournaments SET status = 'completed' WHERE id = $1",
                    tournament_id,
                )

                print(
                    f"Tournament {tournament_id} ({tournament['name']}) expired — "
                    f"declared {len(leaders)} winner(s) based on most wins."
                )

                for leader in leaders:
                    await manager.send_event(
                        leader["playfab_id"],
                        f"{TOURNAMENT_COMPLETED_EVENT}:{tournament_id}",
                    )
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            expired = await conn.fetch(
                """
                SELECT id, name
                FROM tournaments
                WHERE end_time <= NOW()
                  AND status NOT IN ('completed', 'cancelled')
                FOR UPDATE
                """
            )

            for tournament in expired:
                tournament_id = tournament["id"]

                max_round = await conn.fetchval(
                    "SELECT MAX(round_number) FROM tournament_matches WHERE tournament_id = $1",
                    tournament_id,
                )

                if max_round is None:
                    # koi match kabhi bana hi nahi (players poore nahi hue the)
                    await conn.execute(
                        "UPDATE tournaments SET status = 'cancelled' WHERE id = $1",
                        tournament_id,
                    )
                    print(f"Tournament {tournament_id} expired with no matches — cancelled.")
                    continue

                # sabse aagay wale (deepest round tak pahunche, abhi tak eliminate nahi hue)
                leaders = await conn.fetch(
                    """
                    SELECT DISTINCT p.id, p.playfab_id
                    FROM tournament_matches tm
                    JOIN tournament_participants p
                        ON p.id IN (tm.player1_id, tm.player2_id)
                    WHERE tm.tournament_id = $1
                      AND tm.round_number = $2
                      AND p.eliminated = FALSE
                    """,
                    tournament_id,
                    max_round,
                )

                for leader in leaders:
                    await conn.execute(
                        "INSERT INTO tournament_champions (tournament_id, participant_id) VALUES ($1, $2)",
                        tournament_id,
                        leader["id"],
                    )

                await conn.execute(
                    "UPDATE tournaments SET status = 'completed' WHERE id = $1",
                    tournament_id,
                )

                print(
                    f"Tournament {tournament_id} ({tournament['name']}) expired — "
                    f"declared {len(leaders)} joint winner(s)."
                )

                for leader in leaders:
                    await manager.send_event(
                        leader["playfab_id"],
                        f"{TOURNAMENT_COMPLETED_EVENT}:{tournament_id}",
                    )