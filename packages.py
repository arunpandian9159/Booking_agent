import httpx
from auth import get_access_token
from typing import Any

PACKAGE_URL = "https://api.tripxplo.com/v1/api/admin/package"

async def fetch_packages(search: str = "", limit: int = 100, offset: int = 0):
    token = await get_access_token()

    params: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
    }
    if search:
        params["search"] = search

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(PACKAGE_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {}).get("docs", []) 