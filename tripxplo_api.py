from config import API_BASE, TRIPXPLO_EMAIL, TRIPXPLO_PASSWORD, logger
import requests

_token_cache = None
_hotel_id_to_name_cache = None

def get_tripxplo_token():
    global _token_cache
    if _token_cache:
        logger.info("Using cached token")
        return _token_cache
    logger.info("Fetching new token from TripXplo API")
    try:
        response = requests.put(
            f"{API_BASE}/admin/auth/login",
            json={"email": TRIPXPLO_EMAIL, "password": TRIPXPLO_PASSWORD}
        )
        response.raise_for_status()
        _token_cache = response.json().get("accessToken")
        if not _token_cache:
            raise ValueError("No accessToken in login response")
        logger.info(f"✅ Logged in successfully. JWT Token:\n{_token_cache}\n")
        return _token_cache
    except Exception as e:
        logger.error(f"Token fetch error: {e}")
        _token_cache = None
        raise

def tripxplo_get_plans(search: str = ""):
    token = get_tripxplo_token()
    params = {"limit": str(100), "offset": str(0)}
    if search:
        params["search"] = str(search)
    try:
        response = requests.get(
            f"{API_BASE}/admin/package",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        response.raise_for_status()
        packages = response.json().get("result", {}).get("docs", [])
        logger.info(f"Fetched {len(packages)} packages with search='{search}'")
        return [{"name": p.get("name"), "description": p.get("description")} for p in packages]
    except Exception as e:
        logger.error(f"Error fetching packages: {e}")
        return []

def tripxplo_get_plan_details(plan_name: str):
    token = get_tripxplo_token()
    params = {"limit": 100, "offset": 0, "search": plan_name}
    try:
        response = requests.get(
            f"{API_BASE}/admin/package",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        response.raise_for_status()
        packages = response.json().get("result", {}).get("docs", [])
        plan_name_lower = plan_name.lower()
        for p in packages:
            if p.get("name") and plan_name_lower in p.get("name").lower():
                origin = p.get("origin") or p.get("from")
                dest = p.get("destination") or p.get("to")
                city_code = p.get("city_code") or p.get("cityCode") or p.get("to")
                return origin, dest, city_code, p.get("name"), p.get("_id")
        available = [p.get("name") for p in packages if p.get("name")]
        return None, None, None, available, None
    except Exception as e:
        logger.error(f"Error fetching plan details: {e}")
        return None, None, None, [], None

def tripxplo_get_hotels(plan_id: str):
    token = get_tripxplo_token()
    try:
        response = requests.get(
            f"{API_BASE}/admin/package/{plan_id}/available/get",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        hotels = response.json().get("result", [])
        logger.info(f"Fetched {len(hotels)} hotels for package {plan_id}")
        return hotels
    except Exception as e:
        logger.error(f"Error fetching hotels: {e}")
        return []

def tripxplo_get_package_by_id(package_id: str):
    token = get_tripxplo_token()
    try:
        params = {"limit": 1000, "offset": 0}
        response = requests.get(
            f"{API_BASE}/admin/package",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        response.raise_for_status()
        packages = response.json().get("result", {}).get("docs", [])
        for p in packages:
            if str(p.get("_id")) == str(package_id):
                return p
        return None
    except Exception as e:
        logger.error(f"Error fetching package by ID (via list): {e}")
        return None

def tripxplo_get_destination_by_id(destination_id: str):
    token = get_tripxplo_token()
    if not destination_id or not isinstance(destination_id, str) or len(destination_id) < 8:
        logger.warning(f"Destination ID is missing or invalid: {destination_id}")
        return {}
    try:
        response = requests.get(
            f"{API_BASE}/admin/destination/{destination_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("result", {})
    except Exception as e:
        return {}

def tripxplo_get_hotel_by_id(hotel_id: str):
    token = get_tripxplo_token()
    if not hotel_id or not isinstance(hotel_id, str) or len(hotel_id) < 8:
        logger.warning(f"Hotel ID is missing or invalid: {hotel_id}")
        return {}
    try:
        logger.info(f"Fetching hotel by ID: {hotel_id}")
        response = requests.get(
            f"{API_BASE}/admin/hotel/{hotel_id}/getOne",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("result", {})
    except Exception as e:
        logger.error(f"Error fetching hotel by ID {hotel_id}: {e}")
        return {}

def get_hotel_id_to_name_mapping():
    global _hotel_id_to_name_cache
    if _hotel_id_to_name_cache is not None:
        return _hotel_id_to_name_cache
    hotels = fetch_all_hotels()
    mapping = {}
    for hotel in hotels:
        hid = hotel.get("hotelId")
        name = hotel.get("name")
        if hid and name:
            mapping[hid] = name
    _hotel_id_to_name_cache = mapping
    logger.info(f"Loaded hotel hotelId to name mapping for {len(mapping)} hotels (from fetch_all_hotels).")
    return mapping

def fetch_all_hotels():
    """
    Fetch all hotel details from the TripXplo API and return as a list of hotel objects.
    """
    token = get_tripxplo_token()
    try:
        params = {"limit": 1000, "offset": 0}
        response = requests.get(
            f"{API_BASE}/admin/hotel",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"Fetched all hotels: {len(data.get('result', []))} found.")
        return data.get("result", [])
    except Exception as e:
        logger.error(f"Error fetching all hotels: {e}")
        return [] 