import asyncpg
from config.settings import DATABASE_URL
 
_pool: asyncpg.Pool | None = None
 
 
async def init_db_pool():
    global _pool
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    print("DB pool created")
 
 
async def close_db_pool():
    if _pool:
        await _pool.close()
 
 
def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool
 