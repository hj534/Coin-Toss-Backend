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
    print("DB pool created")
 
 
async def close_db_pool():
    if _pool:
        await _pool.close()
 
 
def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool
 
