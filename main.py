import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.payment_routes import router as payment_router
from routes.websocket_routes import router as websocket_router
from routes.stripe_redirects import router as stripe_redirects_router
from routes.tournament_routes import router as tournament_routes_router
from routes.tournament_routes import service as tournament_service

from services.db import init_db_pool, close_db_pool
from services.scheduler import start_scheduler, stop_scheduler

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or ["http://localhost:5500"] for stricter security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(payment_router)
app.include_router(websocket_router)
app.include_router(stripe_redirects_router)
app.include_router(tournament_routes_router)

leaderboard_settlement_task: asyncio.Task | None = None


@app.get("/")
def root():
    return {"Hello": "World "}


@app.on_event("startup")
async def on_startup():
    global leaderboard_settlement_task
    await init_db_pool()
    start_scheduler()
    # DB pool ban jane ke baad weekly/monthly leaderboard rewards ka loop
    leaderboard_settlement_task = asyncio.create_task(
        tournament_service.leaderboard_settlement_loop()
    )


@app.on_event("shutdown")
async def on_shutdown():
    if leaderboard_settlement_task is not None:
        leaderboard_settlement_task.cancel()
    stop_scheduler()
    await close_db_pool()


@app.get("/user")
def get_user(name):
    return {"name": name}