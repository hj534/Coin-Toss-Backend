from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/stripe_success/", response_class=HTMLResponse)
async def stripe_success():
    return """
    <html>
        <head><title>Payment Successful</title></head>
        <body style="text-align:center; font-family:sans-serif; margin-top:50px;">
            <h1>✅ Payment Successful!</h1>
            <p>Your purchase was successful. You can now return to the game.</p>
        </body>
    </html>
    """

@router.get("/cancel/", response_class=HTMLResponse)
async def stripe_cancel():
    return """
    <html>
        <head><title>Payment Cancelled</title></head>
        <body style="text-align:center; font-family:sans-serif; margin-top:50px;">
            <h1>❌ Payment Cancelled</h1>
            <p>You canceled the payment. No changes have been made.</p>
        </body>
    </html>
    """
