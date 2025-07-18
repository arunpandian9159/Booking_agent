import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TRIPXPLO_EMAIL = os.getenv("TRIPXPLO_EMAIL")
TRIPXPLO_PASSWORD = os.getenv("TRIPXPLO_PASSWORD")

LOGIN_URL = "https://api.tripxplo.com/v1/api/admin/auth/login"

_cached_token = None
_token_expiry = 0

async def get_access_token():
    global _cached_token, _token_expiry

    import time
    current_time = time.time()
    if _cached_token and current_time < _token_expiry:
        return _cached_token

    async with httpx.AsyncClient() as client:
        response = await client.put(
            LOGIN_URL,
            json={"email": TRIPXPLO_EMAIL, "password": TRIPXPLO_PASSWORD},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        data = response.json()
        _cached_token = data.get("accessToken")
        _token_expiry = current_time + 3600  # 1 hour cache
        if not _cached_token:
            raise Exception("No access token received from login.")
        return _cached_token 