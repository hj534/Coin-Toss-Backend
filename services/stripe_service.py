import stripe
from config.settings import STRIPE_SECRET_KEY, CHECKOUT_SUCCESS_URL, CHECKOUT_CANCEL_URL
from config.events import CASH_UPDATED_EVENT, COINS_UPDATED_EVENT
from services.playfab_service import update_playfab_cash, update_playfab_coins, get_currency_packs
from services.websocket_instance import manager
import asyncio

stripe.api_key = STRIPE_SECRET_KEY

def create_checkout_session(data):
    currency_packs = get_currency_packs()
    pack = currency_packs.get(data.pack_id)

    if not pack:
        return None, "Invalid pack ID"

    try:
        currency_type = pack.get("type", "cash")  # Default to cash for backward compatibility
        amount = pack.get("amount", 0)

        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"{amount} Play {currency_type.capitalize()}"
                    },
                    "unit_amount": pack["price_cents"],
                },
                "quantity": 1,
            }],
            metadata={
                "email": data.email,
                "pack_id": data.pack_id,
                "type": currency_type,
                "amount": str(amount),
                "playfab_id": data.playfab_id,
            },
            mode="payment",
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            customer_email=data.email,
        )
        return session.url, None

    except Exception as e:
        return None, str(e)



def handle_webhook(event):

    if event["type"] != "checkout.session.completed":
        return

    session = event["data"]["object"]
    metadata = session["metadata"]
    currency_type = metadata["type"]
    amount = int(metadata["amount"])
    playfab_id = metadata.get("playfab_id")

    if playfab_id:
        if currency_type == "cash":
            success = update_playfab_cash(playfab_id, amount)
            if success:
                asyncio.create_task(manager.send_event(playfab_id, CASH_UPDATED_EVENT))
        elif currency_type == "coin":
            success = update_playfab_coins(playfab_id, amount)
            if success:
                asyncio.create_task(manager.send_event(playfab_id, COINS_UPDATED_EVENT))
