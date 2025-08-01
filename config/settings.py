import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

PLAYFAB_TITLE_ID = os.getenv("PLAYFAB_TITLE_ID")
PLAYFAB_SECRET_KEY = os.getenv("PLAYFAB_SECRET_KEY")

BASE_URL = os.getenv("BASE_URL")
CHECKOUT_SUCCESS_URL = os.getenv("CHECKOUT_SUCCESS_URL")
CHECKOUT_CANCEL_URL = os.getenv("CHECKOUT_CANCEL_URL")

