from fastapi import APIRouter
from services.db import get_pool

router = APIRouter()


@router.get("/db-check")
async def db_list():
    pool = get_pool()

    rows = await pool.fetch("SELECT * FROM tournaments")

    return {
        "tournaments": [dict(r) for r in rows]
    }