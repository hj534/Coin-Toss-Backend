from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.payment_routes import router as payment_router
from routes.websocket_routes import router as websocket_router
from routes.stripe_redirects import router as stripe_redirects_router

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

@app.get("/")
def root():
    return{"Hello": "World "}