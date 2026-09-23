import asyncpg
from config.settings import DATABASE_URL
 
_pool: asyncpg.Pool | None = None
 
 
async def init_db_pool():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_leaderboard (
                playfab_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                points INTEGER NOT NULL DEFAULT 0,
                active_membership_id TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS player_prizes (
                id SERIAL PRIMARY KEY,
                playfab_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                tournament_id INTEGER NOT NULL,
                tournament_name TEXT NOT NULL,
                rank INTEGER NOT NULL,
                prize_type TEXT NOT NULL,
                prize_name TEXT NOT NULL,
                prize_value TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'earned',
                earned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                delivered_at TIMESTAMPTZ,
                admin_notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        prize_foreign_keys = await conn.fetch(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'player_prizes'::regclass
              AND contype = 'f'
            """
        )
        for row in prize_foreign_keys:
            constraint_name = row["conname"].replace('"', '""')
            await conn.execute(
                f'ALTER TABLE player_prizes DROP CONSTRAINT IF EXISTS "{constraint_name}"'
            )
        await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_player_prizes_reward
            ON player_prizes (
                playfab_id,
                tournament_id,
                rank,
                prize_type,
                prize_name
            )
            """
        )
    print("DB pool created")
 
 
async def close_db_pool():
    if _pool:
        await _pool.close()
 
 
def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool
 
