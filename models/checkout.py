from pydantic import BaseModel

class CheckoutRequest(BaseModel):
    pack_id: str
    email: str
    playfab_id: str
    item_type: str = "currency"  # Default to currency, can be overridden