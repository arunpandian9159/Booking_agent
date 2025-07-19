from tripxplo_api import tripxplo_get_package_by_id, tripxplo_get_destination_by_id, tripxplo_get_hotels, fetch_all_hotels
from amadeus_api import get_amadeus_access_token
from utils import city_to_iata, extract_city_from_package_name, EUR_TO_INR
from config import AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET
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
    hotel_id_name_map, room_id_to_hotel_name = build_hotel_id_name_map_from_package(package)
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
        hotels = extract_hotels_from_package(package)
        if not hotels:
            hotels = tripxplo_get_hotels(plan)
        # Debug: Log the hotel data received
        logger.info(f"Hotels from tripxplo_get_hotels: {hotels}")
        # Fetch all hotels for fallback price lookup
        all_hotels = fetch_all_hotels()
        logger.info(f"All hotels from fetch_all_hotels: {all_hotels}")
        def get_price(h):
            for k in ["price", "minPrice", "amount"]:
                v = h.get(k)
                try:
                    return float(v)
                except Exception:
                    continue
            return float("inf")
        hotels_sorted = sorted(hotels, key=get_price) if hotels else []
        rows = []
        for h in hotels_sorted:
            hotel_name = h.get("name") or h.get("hotel") or h.get("hotelName") or ""
            hotel_id = h.get("hotelId")
            if not hotel_name and hotel_id:
                hotel_name = hotel_id_name_map.get(hotel_id, "")
            if not hotel_name:
                room_id = h.get("_id")
                if room_id:
                    hotel_name = room_id_to_hotel_name.get(room_id, "")
            meal_plan = h.get("mealPlan", "")
            nights = h.get("noOfNight", "")
            # Try to extract room price, adult price, child price from hotelRoomDetails if available
            room_price = adult_price = child_price = ""
            room_details = h.get("hotelRoomDetails", [])
            if room_details and isinstance(room_details, list):
                first_room = room_details[0]
                room_price = first_room.get("price", "")
                adult_price = first_room.get("adultPrice", "")
                child_price = first_room.get("childPrice", "")
            else:
                room_price = h.get("price", "")
                adult_price = h.get("adultPrice", "")
                child_price = h.get("childPrice", "")
            # Fallback: if any price is empty, try to get from fetch_all_hotels
            if (not room_price or not adult_price or not child_price):
                # Try to match by hotelId first, then by name
                fallback_hotel = None
                if hotel_id:
                    fallback_hotel = next((fh for fh in all_hotels if str(fh.get("hotelId")) == str(hotel_id)), None)
                if not fallback_hotel and hotel_name:
                    fallback_hotel = next((fh for fh in all_hotels if (fh.get("name") or fh.get("hotelName")) == hotel_name), None)
                if fallback_hotel:
                    if not room_price:
                        room_price = fallback_hotel.get("price", "")
                    if not adult_price:
                        adult_price = fallback_hotel.get("adultPrice", "")
                    if not child_price:
                        child_price = fallback_hotel.get("childPrice", "")
            rows.append(f"| {hotel_name} | {meal_plan} | {nights} | {room_price} | {adult_price} | {child_price} |")
        if rows:
            hotel_info = (
                "| Hotel Name | Meal Plan | Nights | Room Price | Adult Price | Child Price |\n"
                "|-----------|-----------|--------|------------|------------|------------|\n" +
                "\n".join(rows)
            )
        else:
            hotel_info = "No hotels found."
    except Exception as e:
        hotel_info = f"Hotel search error: {str(e)}"
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

def build_hotel_id_name_map_from_package(package):
    hotel_map = {}
    room_id_to_hotel_name = {}
    for key in ["hotels", "hotelList", "hotel", "hotelOptions", "availableHotels"]:
        hotels = package.get(key)
        if hotels and isinstance(hotels, list):
            for h in hotels:
                hotel_id = h.get("hotelId") or h.get("_id")
                hotel_name = h.get("hotelName") or h.get("name")
                if hotel_id and hotel_name:
                    hotel_map[hotel_id] = hotel_name
                for room in h.get("hotelRoomDetails", []):
                    room_id = room.get("_id")
                    if room_id and hotel_name:
                        room_id_to_hotel_name[room_id] = hotel_name
                    for meal in room.get("mealPlan", []):
                        meal_id = meal.get("_id")
                        if meal_id and hotel_name:
                            room_id_to_hotel_name[meal_id] = hotel_name
    return hotel_map, room_id_to_hotel_name 