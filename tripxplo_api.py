from config import API_BASE, TRIPXPLO_EMAIL, TRIPXPLO_PASSWORD, logger
import requests

_token_cache = None
_hotel_id_to_name_cache = None

def get_tripxplo_token():
    global _token_cache
    if _token_cache:
        return _token_cache
    try:
        response = requests.put(
            f"{API_BASE}/admin/auth/login",
            json={"email": TRIPXPLO_EMAIL, "password": TRIPXPLO_PASSWORD}
        )
        response.raise_for_status()
        _token_cache = response.json().get("accessToken")
        if not _token_cache:
            raise ValueError("No accessToken in login response")
        return _token_cache
    except Exception as e:
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
        return [{"name": p.get("name"), "description": p.get("description")} for p in packages]
    except Exception as e:
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
        return hotels
    except Exception as e:
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
        return None

def tripxplo_get_destination_by_id(destination_id: str):
    token = get_tripxplo_token()
    if not destination_id or not isinstance(destination_id, str) or len(destination_id) < 8:
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
        return {}
    try:
        response = requests.get(
            f"{API_BASE}/admin/hotel/{hotel_id}/getOne",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("result", {})
    except Exception as e:
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
        return data.get("result", [])
    except Exception as e:
        return []

def fetch_hotels_by_destination(destination_id: str):
    """
    First fetch all hotels, then match hotel names and prices using destination ID.
    This function will be used for destination-based hotel matching.
    """
    if not destination_id or not isinstance(destination_id, str) or len(destination_id) < 8:
        logger.warning(f"Invalid destination ID: {destination_id}")
        return []
    
    try:
        # Step 1: Fetch all hotels
        logger.info(f"Fetching all hotels to match with destination ID: {destination_id}")
        all_hotels = fetch_all_hotels()
        logger.info(f"Fetched {len(all_hotels)} total hotels from API")
        
        # Step 2: Match hotels by destination ID
        destination_hotels = []
        for hotel in all_hotels:
            hotel_destination = hotel.get("destination")
            hotel_name = hotel.get("name") or hotel.get("hotelName") or ""
            hotel_price = hotel.get("price") or hotel.get("minPrice") or hotel.get("amount") or ""
            
            # Check if hotel belongs to the specified destination
            is_destination_match = False
            if isinstance(hotel_destination, list) and hotel_destination:
                for dest in hotel_destination:
                    if dest.get("destinationId") == destination_id:
                        is_destination_match = True
                        break
            elif isinstance(hotel_destination, dict) and hotel_destination.get("destinationId") == destination_id:
                is_destination_match = True
            elif isinstance(hotel_destination, str) and hotel_destination == destination_id:
                is_destination_match = True
            
            # If destination matches, add hotel with name and price
            if is_destination_match:
                # Ensure hotel has name and price information
                if hotel_name and hotel_price:
                    destination_hotels.append({
                        "name": hotel_name,
                        "price": hotel_price,
                        "adultPrice": hotel.get("adultPrice", ""),
                        "childPrice": hotel.get("childPrice", ""),
                        "mealPlan": hotel.get("mealPlan", ""),
                        "noOfNight": hotel.get("noOfNight", ""),
                        "hotelId": hotel.get("hotelId", ""),
                        "_id": hotel.get("_id", ""),
                        "destination": hotel_destination
                    })
                    logger.debug(f"Matched hotel: {hotel_name} - Price: {hotel_price}")
        
        logger.info(f"Successfully matched {len(destination_hotels)} hotels for destination ID {destination_id}")
        return destination_hotels
        
    except Exception as e:
        logger.error(f"Error matching hotels by destination {destination_id}: {e}")
        return [] 