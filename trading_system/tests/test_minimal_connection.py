from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

load_dotenv(override=True)

API_KEY = os.getenv("PAPER_API_KEY_ID")
SECRET_KEY = os.getenv("PAPER_API_SECRET_KEY")

print(f"Loaded API_KEY: {repr(API_KEY)}")   # <--- DEBUG: shows invisible characters
print(f"Loaded SECRET_KEY: {repr(SECRET_KEY)}")

if not API_KEY or not SECRET_KEY:
    raise ValueError("❌ Missing API credentials!")

API_KEY = API_KEY.strip()
SECRET_KEY = SECRET_KEY.strip()

client = TradingClient(API_KEY, SECRET_KEY, paper=True)

try:
    account = client.get_account()
    print("✅ Connected to Alpaca")
    print(f"Account status: {account.status}")
except Exception as e:
    print("❌ Error connecting to Alpaca:", e)
