import asyncio
from services.db import get_pool
from services.websocket_instance import manager
from config.events import TOURNAMENT_STARTED_EVENT
from services.tournament_service import TournamentService

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

    expired = await pool.fetch(
        """
        UPDATE tournaments
        SET status = 'cancelled'
        WHERE end_time <= NOW()
          AND status NOT IN ('completed', 'cancelled')
        RETURNING id, name
        """
    )

    for tournament in expired:
        print(
            f"Tournament {tournament['id']} ({tournament['name']}) "
            f"expired — auto-cancelled."
        )