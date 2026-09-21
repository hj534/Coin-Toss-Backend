import asyncio
import random
from datetime import datetime, time, timedelta, timezone

from services.db import get_pool
from services.websocket_instance import manager
from services.tournament_service import TournamentService
from config.events import TOURNAMENT_STARTED_EVENT, TOURNAMENT_COMPLETED_EVENT

POLL_INTERVAL_SECONDS = 15
SCHEDULER_TIMEZONE = timezone.utc
WEEKLY_TOURNAMENT_NAME = "Best of the Best Coin Flipping Champs Weekly Mini Main Event"
WEEKLY_TOURNAMENT_START_DAY = 5  # Saturday, where Monday is 0.
WEEKLY_TOURNAMENT_START_TIME = time(hour=20, minute=0)
WEEKLY_TOURNAMENT_MAX_PLAYERS = 16
WEEKLY_TOURNAMENT_ENTRY_FEE = 10000
WEEKLY_TOURNAMENT_SETS = 5
WEEKLY_TOURNAMENT_CURRENCY_TYPE = "cash"
WEEKLY_TOURNAMENT_ROUND_TIME_SECONDS = 60
MONTHLY_TOURNAMENT_NAME = "Best of the Best Coin Flipping Champs Monthly Main Event"
MONTHLY_TOURNAMENT_START_TIME = time(hour=13, minute=0)
MONTHLY_TOURNAMENT_MAX_PLAYERS = 20
MONTHLY_TOURNAMENT_ENTRY_FEE = 20000
MONTHLY_TOURNAMENT_SETS = 5
MONTHLY_TOURNAMENT_CURRENCY_TYPE = "cash"
MONTHLY_TOURNAMENT_ROUND_TIME_SECONDS = 60
DAILY_TOURNAMENT_MAX_PLAYERS = 16
DAILY_TOURNAMENT_SETS = 3
DAILY_TOURNAMENT_CURRENCY_TYPE = "cash"
DAILY_TOURNAMENT_ROUND_TIME_SECONDS = 60
DAILY_TOURNAMENT_HOURS = [
    8, 9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 19, 20, 21, 22, 23,
    0, 1, 2, 3, 4, 5, 6, 7,
]
DAILY_TOURNAMENT_FEES = [0, 1000, 2000, 3000]
DAILY_TOURNAMENT_FIRST_PLACE_PRIZES = {
    0: 500,
    1000: 20000,
    2000: 40000,
    3000: 100000,
}
FREE_TOURNAMENT_NAMES = [
    "Lucky Flip Free Cup",
    "Golden Toss Free Sprint",
    "Coin Clash Free Arena",
    "Heads or Tails Free Rush",
    "Flip Frenzy Free Cup",
    "Zero Entry Coin Battle",
    "Daily Free Toss Showdown",
    "Cash Spark Free Challenge",
]
FREE_TOURNAMENT_HOURS = [0, 3, 6, 9, 12, 15, 18, 21]
FREE_TOURNAMENT_MAX_PLAYER_OPTIONS = [4, 8]
FREE_TOURNAMENT_SETS = 3
FREE_TOURNAMENT_ENTRY_FEE = 0
FREE_TOURNAMENT_PRIZE = 500
FREE_TOURNAMENT_CURRENCY_TYPE = "cash"
FREE_TOURNAMENT_ROUND_TIME_SECONDS = 60

service = TournamentService()
_task: asyncio.Task | None = None


def _current_or_next_weekly_window():
    now = datetime.now(SCHEDULER_TIMEZONE)
    days_until_start = (WEEKLY_TOURNAMENT_START_DAY - now.weekday()) % 7
    start_at = now.replace(
        hour=WEEKLY_TOURNAMENT_START_TIME.hour,
        minute=WEEKLY_TOURNAMENT_START_TIME.minute,
        second=0,
        microsecond=0,
    ) + timedelta(days=days_until_start)

    if start_at <= now:
        start_at += timedelta(days=7)

    return start_at, start_at + timedelta(days=7)


def _last_sunday(year: int, month: int):
    if month == 12:
        last_day = datetime(year + 1, 1, 1, tzinfo=SCHEDULER_TIMEZONE) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1, tzinfo=SCHEDULER_TIMEZONE) - timedelta(days=1)

    days_since_sunday = (last_day.weekday() - 6) % 7
    return last_day - timedelta(days=days_since_sunday)


def _add_month(year: int, month: int):
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _monthly_start_for(year: int, month: int):
    last_sunday = _last_sunday(year, month)
    return last_sunday.replace(
        hour=MONTHLY_TOURNAMENT_START_TIME.hour,
        minute=MONTHLY_TOURNAMENT_START_TIME.minute,
        second=0,
        microsecond=0,
    )


def _current_or_next_monthly_window():
    now = datetime.now(SCHEDULER_TIMEZONE)
    start_at = _monthly_start_for(now.year, now.month)

    if start_at <= now:
        next_year, next_month = _add_month(now.year, now.month)
        start_at = _monthly_start_for(next_year, next_month)

    end_year, end_month = _add_month(start_at.year, start_at.month)
    return start_at, _monthly_start_for(end_year, end_month)


def _current_or_next_daily_window(hour: int):
    now = datetime.now(SCHEDULER_TIMEZONE)
    start_at = now.replace(hour=hour, minute=0, second=0, microsecond=0)

    if start_at <= now:
        start_at += timedelta(days=1)

    return start_at, start_at + timedelta(days=1)


def _current_or_next_free_window(hour: int):
    now = datetime.now(SCHEDULER_TIMEZONE)
    start_at = now.replace(hour=hour, minute=0, second=0, microsecond=0)

    if start_at <= now:
        start_at += timedelta(days=1)

    return start_at, start_at + timedelta(hours=3)


async def _ensure_weekly_tournament():
    pool = get_pool()
    start_at, end_at = _current_or_next_weekly_window()

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT id, start_time
                FROM tournaments
                WHERE type = 'weekly'
                  AND status NOT IN ('completed', 'cancelled')
                ORDER BY start_time DESC
                LIMIT 1
                FOR UPDATE
                """
            )

            if existing:
                return

            row = await conn.fetchrow(
                """
                INSERT INTO tournaments
                    (name, start_time, end_time, max_players, type, sets,
                     entry_fee, currency_type, round_time_seconds, prize)
                VALUES ($1, $2, $3, $4, 'weekly', $5, $6, $7, $8, $9)
                RETURNING id
                """,
                WEEKLY_TOURNAMENT_NAME,
                start_at,
                end_at,
                WEEKLY_TOURNAMENT_MAX_PLAYERS,
                WEEKLY_TOURNAMENT_SETS,
                WEEKLY_TOURNAMENT_ENTRY_FEE,
                WEEKLY_TOURNAMENT_CURRENCY_TYPE,
                WEEKLY_TOURNAMENT_ROUND_TIME_SECONDS,
                WEEKLY_TOURNAMENT_ENTRY_FEE * 2,
            )

            print(
                "Created weekly tournament "
                f"{row['id']} from {start_at.isoformat()} to {end_at.isoformat()}"
            )


async def _ensure_monthly_tournament():
    pool = get_pool()
    start_at, end_at = _current_or_next_monthly_window()

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT id, start_time
                FROM tournaments
                WHERE type = 'monthly'
                  AND status NOT IN ('completed', 'cancelled')
                ORDER BY start_time DESC
                LIMIT 1
                FOR UPDATE
                """
            )

            if existing:
                return

            row = await conn.fetchrow(
                """
                INSERT INTO tournaments
                    (name, start_time, end_time, max_players, type, sets,
                     entry_fee, currency_type, round_time_seconds, prize)
                VALUES ($1, $2, $3, $4, 'monthly', $5, $6, $7, $8, $9)
                RETURNING id
                """,
                MONTHLY_TOURNAMENT_NAME,
                start_at,
                end_at,
                MONTHLY_TOURNAMENT_MAX_PLAYERS,
                MONTHLY_TOURNAMENT_SETS,
                MONTHLY_TOURNAMENT_ENTRY_FEE,
                MONTHLY_TOURNAMENT_CURRENCY_TYPE,
                MONTHLY_TOURNAMENT_ROUND_TIME_SECONDS,
                MONTHLY_TOURNAMENT_ENTRY_FEE * 2,
            )

            print(
                "Created monthly tournament "
                f"{row['id']} from {start_at.isoformat()} to {end_at.isoformat()}"
            )


async def _ensure_daily_tournaments():
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for index, hour in enumerate(DAILY_TOURNAMENT_HOURS, start=1):
                name = f"Best of the Best Coin Flipping Champs {index}"
                entry_fee = DAILY_TOURNAMENT_FEES[(index - 1) % len(DAILY_TOURNAMENT_FEES)]
                start_at, end_at = _current_or_next_daily_window(hour)

                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM tournaments
                    WHERE name = $1
                      AND type = 'daily'
                      AND start_time = $2
                    LIMIT 1
                    FOR UPDATE
                    """,
                    name,
                    start_at,
                )

                if existing:
                    continue

                row = await conn.fetchrow(
                    """
                    INSERT INTO tournaments
                        (name, start_time, end_time, max_players, type, sets,
                         entry_fee, currency_type, round_time_seconds, prize)
                    VALUES ($1, $2, $3, $4, 'daily', $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    name,
                    start_at,
                    end_at,
                    DAILY_TOURNAMENT_MAX_PLAYERS,
                    DAILY_TOURNAMENT_SETS,
                    entry_fee,
                    DAILY_TOURNAMENT_CURRENCY_TYPE,
                    DAILY_TOURNAMENT_ROUND_TIME_SECONDS,
                    DAILY_TOURNAMENT_FIRST_PLACE_PRIZES[entry_fee],
                )

                print(
                    "Created daily tournament "
                    f"{row['id']} ({name}) from {start_at.isoformat()} "
                    f"to {end_at.isoformat()}"
                )


async def _ensure_free_tournaments():
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            for index, hour in enumerate(FREE_TOURNAMENT_HOURS):
                name = FREE_TOURNAMENT_NAMES[index]
                start_at, end_at = _current_or_next_free_window(hour)

                existing = await conn.fetchrow(
                    """
                    SELECT id
                    FROM tournaments
                    WHERE name = $1
                      AND type = 'free'
                      AND start_time = $2
                    LIMIT 1
                    FOR UPDATE
                    """,
                    name,
                    start_at,
                )

                if existing:
                    continue

                max_players = random.choice(FREE_TOURNAMENT_MAX_PLAYER_OPTIONS)
                row = await conn.fetchrow(
                    """
                    INSERT INTO tournaments
                        (name, start_time, end_time, max_players, type, sets,
                         entry_fee, currency_type, round_time_seconds, prize)
                    VALUES ($1, $2, $3, $4, 'free', $5, $6, $7, $8, $9)
                    RETURNING id
                    """,
                    name,
                    start_at,
                    end_at,
                    max_players,
                    FREE_TOURNAMENT_SETS,
                    FREE_TOURNAMENT_ENTRY_FEE,
                    FREE_TOURNAMENT_CURRENCY_TYPE,
                    FREE_TOURNAMENT_ROUND_TIME_SECONDS,
                    FREE_TOURNAMENT_PRIZE,
                )

                print(
                    "Created free tournament "
                    f"{row['id']} ({name}) from {start_at.isoformat()} "
                    f"to {end_at.isoformat()} with max_players={max_players}"
                )


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
            await _check_expired_tournaments()
            await _ensure_free_tournaments()
            await _ensure_daily_tournaments()
            await _ensure_weekly_tournament()
            await _ensure_monthly_tournament()
            await _check_due_tournaments()
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
    completed_tournament_rewards: list[list[tuple[str, int, int, int]]] = []

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
                    SELECT wc.participant_id, wc.playfab_id, mw.max_wins
                    FROM win_counts wc, max_wins mw
                    WHERE wc.wins = mw.max_wins
                    """,
                    tournament_id,
                )

                # agar kisi ne bhi ek bhi match nahi jeeta, koi winner nahi - cancel karo
                if not leaders or leaders[0]["max_wins"] == 0:
                    await conn.execute(
                        "UPDATE tournaments SET status = 'cancelled' WHERE id = $1",
                        tournament_id,
                    )
                    print(f"Tournament {tournament_id} expired with zero wins for everyone — cancelled.")
                    continue

                for leader in leaders:
                    await conn.execute(
                        "INSERT INTO tournament_champions (tournament_id, participant_id) VALUES ($1, $2)",
                        tournament_id,
                        leader["participant_id"],
                    )

                tournament_rewards = await service._get_tournament_reward_recipients(
                    conn,
                    tournament_id,
                )
                if tournament_rewards:
                    completed_tournament_rewards.append(tournament_rewards)

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

    for rewards in completed_tournament_rewards:
        await service._award_tournament_rewards(rewards)
