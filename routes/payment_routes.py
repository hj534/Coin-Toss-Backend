from fastapi import APIRouter, Request, HTTPException
from models.checkout import CheckoutRequest
from services.stripe_service import currency_pack_checkout_session, model_checkout_session, membership_checkout_session, handle_webhook
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
    elif item_type == "membership":
        url, error = membership_checkout_session(data)
    else:
        raise HTTPException(status_code=400, detail="Invalid item type")
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"url": url}

# @router.post("/webhook/")
# async def webhook(request: Request):
#     print("Received webhook request")
#     payload = await request.body()
#     event = stripe.Event.construct_from(json.loads(payload), STRIPE_WEBHOOK_SECRET)
#     handle_webhook(event)
#     return {}



@router.post("/webhook/")
async def webhook(request: Request):
    print("Received webhook request")
    print(f"DEBUG secret len={len(STRIPE_WEBHOOK_SECRET)} value={STRIPE_WEBHOOK_SECRET!r}")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        print(f"Webhook invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        print(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    handle_webhook(event)
    return {}