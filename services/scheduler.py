import asyncio
from services.db import get_pool
from services.websocket_instance import manager
from config.events import TOURNAMENT_UPDATED_EVENT
from services.tournament_service import TournamentService

POLL_INTERVAL_SECONDS = 15

service = TournamentService()
_task: asyncio.Task | None = None


async def _check_due_tournaments():
    pool = get_pool()

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
                    # broadcast happens after the transaction commits, below
                else:
                    print(
                        f"Tournament {row['id']} reached start_time but only "
                        f"{row['current_players']}/{row['max_players']} players "
                        f"registered — leaving as-is for now."
                    )

    # Broadcast for any tournaments that just started (outside the transaction,
    # same pattern as register_participant)
    for row in due:
        if row["current_players"] == row["max_players"]:
            await manager.broadcast_event(f"{TOURNAMENT_UPDATED_EVENT}:{row['id']}")


async def _loop():
    while True:
        try:
            print("Running scheduler tick")
            await _check_due_tournaments()
        except Exception as e:
            # never let one bad tick kill the whole background loop
            print(f"Scheduler tick failed: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_scheduler():
    global _task
    _task = asyncio.create_task(_loop())


def stop_scheduler():
    if _task:
        _task.cancel()