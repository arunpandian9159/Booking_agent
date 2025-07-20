from tripxplo_api import tripxplo_get_package_by_id, tripxplo_get_destination_by_id, tripxplo_get_hotels, fetch_all_hotels, fetch_hotels_by_destination
from amadeus_api import get_amadeus_access_token
from utils import city_to_iata, extract_city_from_package_name, EUR_TO_INR
from config import AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET
from hotel_mapper import get_hotel_mapper, map_hotels_by_destination_and_package
import logging
from datetime import datetime, timedelta
import requests

logger = logging.getLogger(__name__)

def book_travel(plan: str, customer: str, date: str = "") -> str:
    if not date:
        dep_date = datetime.now().date() + timedelta(days=14)
    else:
        try:
            dep_date = datetime.strptime(date, "%Y-%m-%d").date()
        except Exception:
            dep_date = datetime.now().date() + timedelta(days=14)
    ret_date = dep_date + timedelta(days=7)
    dep_date_str = dep_date.isoformat()
    ret_date_str = ret_date.isoformat()
    package = tripxplo_get_package_by_id(plan)
    if not package:
        return f"Package with ID '{plan}' not found."
    plan_actual_name = package.get("packageName") or package.get("name") or plan
    dest = None
    destination_data = package.get("destination") or package.get("to") or package.get("city_code") or package.get("cityCode")
    if isinstance(destination_data, list) and destination_data:
        dest_obj = destination_data[0]
        destination_id = dest_obj.get("destinationId")
        city_name = ""
        if destination_id:
            dest_details = tripxplo_get_destination_by_id(destination_id)
            city_name = dest_details.get("name") or dest_details.get("city") or ""
        if not city_name:
            city_name = extract_city_from_package_name(plan_actual_name, package)
        dest = city_to_iata(city_name)
    elif isinstance(destination_data, str) and len(destination_data) == 3:
        dest = destination_data
    if not dest:
        return f"Destination code not found or invalid in package. Package: {plan_actual_name}. Raw destination data: {destination_data}"
    origin = "MAA"
    flight_info = ""
    try:
        if AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET:
            token = get_amadeus_access_token()
            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": dest,
                "departureDate": dep_date_str,
                "adults": 1,
                "max": 5
            }
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                offers = data.get("data", [])
                offers_sorted = sorted(offers, key=lambda o: float(o["price"]["total"]))
                rows = []
                for offer in offers_sorted:
                    price = offer["price"]["total"]
                    try:
                        inr = float(price) * EUR_TO_INR
                        price_inr = f"{inr:.2f} INR"
                    except Exception:
                        price_inr = "- INR"
                    carrier = offer["itineraries"][0]["segments"][0]["carrierCode"] if offer["itineraries"] and offer["itineraries"][0]["segments"] else ""
                    dep = offer["itineraries"][0]["segments"][0]["departure"]["at"] if offer["itineraries"] and offer["itineraries"][0]["segments"] else ""
                    arr = offer["itineraries"][0]["segments"][0]["arrival"]["at"] if offer["itineraries"] and offer["itineraries"][0]["segments"] else ""
                    rows.append(f"| {origin} | {dest} | {dep} | {arr} | {carrier} | {price_inr} |")
                if rows:
                    flight_info = (
                        "| From | To | Departure | Arrival | Carrier | Price |\n"
                        "|------|----|-----------|--------|---------|-------|\n" +
                        "\n".join(rows)
                    )
                else:
                    flight_info = "No flights found."
            else:
                flight_info = f"Flight search error: {resp.text}"
        else:
            flight_info = "No flight API credentials configured."
    except Exception as e:
        flight_info = f"Flight search error: {str(e)}"
    hotel_info = ""
    try:
        # Extract destination ID from package data
        destination_id = extract_destination_id_from_package(package)
        logger.info(f"Extracted destination ID for hotel matching: {destination_id}")
        
        # Use the new hotel mapper to get hotels by destination
        destination_hotels = []
        if destination_id:
            # Get hotel mapper instance
            mapper = get_hotel_mapper()
            
            # Get all hotels for this destination
            destination_hotels = mapper.get_hotels_by_destination(destination_id)
            logger.info(f"Found {len(destination_hotels)} hotels for destination ID: {destination_id}")
            
            # Get summary for additional info
            summary = mapper.get_hotel_summary_by_destination(destination_id)
            logger.info(f"Destination summary: {summary['total_hotels']} hotels, "
                       f"price range: {summary['price_range']['min']}-{summary['price_range']['max']}, "
                       f"packages: {summary['available_packages']}")
        else:
            logger.warning("No destination ID found, falling back to package hotels")
        
        # Fallback to package hotels if no destination-based hotels found
        if not destination_hotels:
            hotels = extract_hotels_from_package(package)
            if not hotels:
                hotels = tripxplo_get_hotels(plan)
            destination_hotels = hotels
        
        # Process hotels and create display rows
        rows = []
        for hotel in destination_hotels:
            hotel_name = hotel.get("hotelName", "")
            review = hotel.get("review", "")
            view_point = hotel.get("viewPoint", "")
            
            # Process each room and meal plan
            for room in hotel.get("rooms", []):
                room_type = room.get("roomType", "")
                
                for meal in room.get("mealPlans", []):
                    meal_plan = meal.get("mealPlan", "")
                    room_price = meal.get("roomPrice", "")
                    adult_price = meal.get("adultPrice", "")
                    child_price = meal.get("childPrice", "")
                    season_type = meal.get("seasonType", "")
                    
                    # Format prices
                    if room_price:
                        room_price = f"₹{room_price}"
                    else:
                        room_price = "Price not available"
                    
                    if adult_price:
                        adult_price = f"₹{adult_price}"
                    else:
                        adult_price = "Price not available"
                    
                    if child_price:
                        child_price = f"₹{child_price}"
                    else:
                        child_price = "Price not available"
                    
                    # Create display row
                    display_name = f"{hotel_name} ({room_type})"
                    if review:
                        display_name += f" ⭐{review}"
                    
                    rows.append(f"| {display_name} | {meal_plan.upper()} | {season_type} | {room_price} | {adult_price} | {child_price} |")
        
        # Sort by room price (extract numeric value for sorting)
        def extract_price(row):
            try:
                price_part = row.split("|")[4].strip()  # Room price column
                if "₹" in price_part:
                    return float(price_part.replace("₹", "").replace(",", ""))
                return float("inf")
            except:
                return float("inf")
        
        rows.sort(key=extract_price)
        
        if rows:
            hotel_info = (
                "| Hotel Name (Room Type) | Meal Plan | Season | Room Price | Adult Price | Child Price |\n"
                "|----------------------|-----------|--------|------------|------------|------------|\n" +
                "\n".join(rows)
            )
        else:
            hotel_info = "No hotels found for this destination."
    except Exception as e:
        hotel_info = f"Hotel search error: {str(e)}"
        logger.error(f"Error in hotel processing: {e}")
    result = (
        f"Package: {plan_actual_name}\n"
        f"Status: ✅ Complete\n"
        f"\n"
        f"✈️ Flight Details (Chennai to {dest})\n"
        f"{flight_info}\n"
        f"\n"
        f"🏨 Hotel Details\n"
        f"{hotel_info}\n"
    )
    return result.strip()

def extract_hotels_from_package(package):
    hotels = package.get("hotel")
    if hotels and isinstance(hotels, list):
        return hotels
    for key in ["hotels", "hotelOptions", "availableHotels"]:
        hotels = package.get(key)
        if hotels and isinstance(hotels, list):
            return hotels
    return []

def extract_destination_id_from_package(package):
    """
    Extract destination ID from package data, handling various data structures.
    Returns the first valid destination ID found.
    """
    destination_data = package.get("destination") or package.get("to") or package.get("city_code") or package.get("cityCode")
    
    if not destination_data:
        return None
    
    # Handle list of destinations
    if isinstance(destination_data, list):
        for dest_obj in destination_data:
            if isinstance(dest_obj, dict):
                destination_id = dest_obj.get("destinationId")
                if destination_id and isinstance(destination_id, str) and len(destination_id) >= 8:
                    return destination_id
            elif isinstance(dest_obj, str) and len(dest_obj) >= 8:
                return dest_obj
    
    # Handle single destination object
    elif isinstance(destination_data, dict):
        destination_id = destination_data.get("destinationId")
        if destination_id and isinstance(destination_id, str) and len(destination_id) >= 8:
            return destination_id
    
    # Handle string destination
    elif isinstance(destination_data, str) and len(destination_data) >= 8:
        return destination_data
    
    return None

 