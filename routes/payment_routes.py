from fastapi import APIRouter, Request, HTTPException
from models.checkout import CheckoutRequest
from services.stripe_service import create_checkout_session, handle_webhook
import json
import stripe
from config.settings import STRIPE_WEBHOOK_SECRET

router = APIRouter()

@router.post("/checkout/")
async def checkout(data: CheckoutRequest):
    url, error = create_checkout_session(data)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"url": url}

@router.post("/webhook/")
async def webhook(request: Request):
    payload = await request.body()
    event = stripe.Event.construct_from(json.loads(payload), STRIPE_WEBHOOK_SECRET)
    handle_webhook(event)
    return {}
