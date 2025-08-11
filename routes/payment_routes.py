from fastapi import APIRouter, Request, HTTPException
from models.checkout import CheckoutRequest
from services.stripe_service import currency_pack_checkout_session, model_checkout_session, handle_webhook
import json
import stripe
from config.settings import STRIPE_WEBHOOK_SECRET

router = APIRouter()

@router.post("/checkout/")
async def checkout(data: CheckoutRequest):
    item_type = data.item_type
    if item_type == "currency":
        url, error = currency_pack_checkout_session(data)
    elif item_type == "model":
        url, error = model_checkout_session(data)
    else:
        raise HTTPException(status_code=400, detail="Invalid item type")
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"url": url}

@router.post("/webhook/")
async def webhook(request: Request):
    print("Received webhook request")
    payload = await request.body()
    event = stripe.Event.construct_from(json.loads(payload), STRIPE_WEBHOOK_SECRET)
    handle_webhook(event)
    return {}
