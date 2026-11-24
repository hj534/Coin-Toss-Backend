import stripe
from config.settings import STRIPE_SECRET_KEY, CHECKOUT_SUCCESS_URL, CHECKOUT_CANCEL_URL
from config.events import CASH_UPDATED_EVENT, COINS_UPDATED_EVENT, COIN_MODEL_UNLOCKED_EVENT, MEMBERSHIP_UPDATED_EVENT
from services.db import get_pool
from services.playfab_service import (
    update_playfab_cash,
    update_playfab_coins,
    unlock_coin_model,
    get_currency_packs,
    get_models,
    get_memberships,
    get_active_membership_id,
    set_active_membership,
)
from services.websocket_instance import manager
import asyncio

stripe.api_key = STRIPE_SECRET_KEY


def _looks_like_placeholder_price(price_id):
    if not price_id:
        return True

    normalized = price_id.strip()
    return (
        not normalized.startswith("price_")
        or "xxxxx" in normalized.lower()
        or normalized.startswith("PASTE_")
    )


def _get_active_price_id_for_product(product_id):
    if not product_id:
        return None

    prices = stripe.Price.list(
        product=product_id,
        active=True,
        limit=10,
    )

    for price in prices.data:
        if price.recurring:
            return price.id

    if prices.data:
        return prices.data[0].id

    return None


def _get(obj, key, default=None):
    """Stripe object se safe tareeqe se value lo."""
    try:
        value = obj[key]
    except (KeyError, AttributeError, TypeError):
        return default
    return default if value is None else value


def _to_dict(obj):
    if obj is None:
        return {}
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


def currency_pack_checkout_session(data):
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
                "item_type": data.item_type
            },
            mode="payment",
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            customer_email=data.email,
        )
        return session.url, None

    except Exception as e:
        return None, str(e)


def model_checkout_session(data):
    models = get_models()
    model = models.get(data.pack_id)
    if not model:
        return None, "Invalid model ID"
    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": data.pack_id
                    },
                    "unit_amount": model["price_cents"],
                },
                "quantity": 1,
            }],
            metadata={
                "email": data.email,
                "model_id": data.pack_id,
                "playfab_id": data.playfab_id,
                "item_type": data.item_type
            },
            mode="payment",
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            customer_email=data.email,
        )
        return session.url, None
    except Exception as e:
        return None, str(e)


def membership_checkout_session(data):
    memberships = get_memberships()
    membership = memberships.get(data.pack_id)

    if not membership:
        return None, "Invalid membership ID"

    active_membership_id = get_active_membership_id(data.playfab_id)
    if active_membership_id == data.pack_id:
        return None, "This membership is already active"

    try:
        stripe_price_id = membership.get("stripe_price_id")
        if _looks_like_placeholder_price(stripe_price_id):
            stripe_price_id = _get_active_price_id_for_product(
                membership.get("stripe_product_id")
            )

        if not stripe_price_id:
            return None, "Stripe price ID is missing for this membership"

        session = stripe.checkout.Session.create(
            line_items=[{
                "price": stripe_price_id,
                "quantity": 1,
            }],
            metadata={
                "email": data.email,
                "membership_id": data.pack_id,
                "playfab_id": data.playfab_id,
                "item_type": data.item_type
            },
            # Renewal (invoice.paid) par player pehchanne ke liye subscription par bhi metadata
            subscription_data={
                "metadata": {
                    "membership_id": data.pack_id,
                    "playfab_id": data.playfab_id,
                }
            },
            mode="subscription",
            success_url=CHECKOUT_SUCCESS_URL,
            cancel_url=CHECKOUT_CANCEL_URL,
            customer_email=data.email,
        )
        return session.url, None
    except Exception as e:
        return None, str(e)


async def grant_membership_monthly_cash(playfab_id, membership_id, grant_key):
    """
    Membership ka monthly_play_cash player ko do.
    grant_key (Stripe invoice id) ek hi baar chalta hai, isliye retry par double cash nahi milta.
    """
    try:
        membership = get_memberships().get(membership_id) or {}
        amount = int(membership.get("monthly_play_cash", 0) or 0)

        if amount <= 0:
            return

        pool = get_pool()
        inserted = await pool.fetchval(
            """
            INSERT INTO membership_cash_grants (grant_key, playfab_id, membership_id, amount)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (grant_key) DO NOTHING
            RETURNING grant_key
            """,
            grant_key,
            playfab_id,
            membership_id,
            amount,
        )

        if not inserted:
            print(f"Membership cash already granted for {grant_key}")
            return

        try:
            success = update_playfab_cash(playfab_id, amount)
        except Exception as e:
            print(f"Membership cash PlayFab error for {playfab_id}: {e}")
            success = False

        if success:
            await manager.send_event(playfab_id, CASH_UPDATED_EVENT)
            print(f"Membership cash granted: {amount} to {playfab_id} ({membership_id}, {grant_key})")
        else:
            # Cash nahi gaya: record hata do taake dobara try ho sake
            await pool.execute(
                "DELETE FROM membership_cash_grants WHERE grant_key = $1",
                grant_key,
            )
            print(f"Failed to grant membership cash to {playfab_id} ({grant_key})")

    except Exception as e:
        print(f"grant_membership_monthly_cash error: {e}")


def _get_subscription_metadata(invoice):
    parent = _get(invoice, "parent", {})
    details = _get(parent, "subscription_details", {})

    metadata = _get(details, "metadata")
    if metadata:
        return _to_dict(metadata)

    subscription_id = _get(invoice, "subscription") or _get(details, "subscription")
    if not subscription_id:
        return {}

    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        return _to_dict(_get(subscription, "metadata"))
    except Exception as e:
        print(f"Could not load subscription metadata: {e}")
        return {}


def _handle_invoice_paid(invoice):
    invoice_id = _get(invoice, "id")
    amount_paid = _get(invoice, "amount_paid", 0)

    # Zero-amount invoice par cash nahi
    if not invoice_id or amount_paid <= 0:
        return

    metadata = _get_subscription_metadata(invoice)
    playfab_id = metadata.get("playfab_id")
    membership_id = metadata.get("membership_id")

    if not playfab_id or not membership_id:
        print(f"invoice.paid {invoice_id}: playfab_id/membership_id metadata missing, cash skipped")
        return

    asyncio.create_task(
        grant_membership_monthly_cash(playfab_id, membership_id, f"invoice:{invoice_id}")
    )


def handle_webhook(event):

    # Har mahine ki renewal
    if event["type"] == "invoice.paid":
        _handle_invoice_paid(event["data"]["object"])
        return

    if event["type"] != "checkout.session.completed":
        return

    session = event["data"]["object"]
    metadata = session["metadata"].to_dict()
    item_type = metadata.get("item_type")

    if item_type == "currency":
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

    elif item_type == "model":
        model_id = metadata.get("model_id")
        playfab_id = metadata.get("playfab_id")
        if playfab_id:
            success = unlock_coin_model(playfab_id, model_id)
            if success:
                asyncio.create_task(manager.send_event(playfab_id, COIN_MODEL_UNLOCKED_EVENT))

    elif item_type == "membership":
        membership_id = metadata.get("membership_id")
        playfab_id = metadata.get("playfab_id")
        if playfab_id and membership_id:
            success = set_active_membership(playfab_id, membership_id)
            if success:
                asyncio.create_task(manager.send_event(playfab_id, MEMBERSHIP_UPDATED_EVENT))

                # Pehli payment ka monthly cash (invoice id wahi hai jo invoice.paid mein aati hai,
                # is liye dono raaston se milne par bhi cash sirf ek baar jata hai)
                if _get(session, "payment_status") == "paid":
                    invoice_id = _get(session, "invoice")
                    grant_key = (
                        f"invoice:{invoice_id}" if invoice_id else f"session:{_get(session, 'id')}"
                    )
                    asyncio.create_task(
                        grant_membership_monthly_cash(playfab_id, membership_id, grant_key)
                    )

    else:
        print("Unhandled Stripe session with unknown purpose.")