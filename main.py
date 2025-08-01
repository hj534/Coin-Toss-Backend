from fastapi import FastAPI
from routes.payment_routes import router as payment_router
from routes.websocket_routes import router as websocket_router
from routes.stripe_redirects import router as stripe_redirects_router

app = FastAPI()
app.include_router(payment_router)
app.include_router(websocket_router)
app.include_router(stripe_redirects_router)

@app.get("/")
def root():
    return{"Hello": "World "}