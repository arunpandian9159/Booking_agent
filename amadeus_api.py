from config import AMADEUS_CLIENT_ID, AMADEUS_CLIENT_SECRET, EUR_TO_INR
import requests

def get_amadeus_access_token():
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

def search_flights(origin, destination, departure_date):
    token = get_amadeus_access_token()
    url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": 1,
        "max": 1
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data"):
            offer = data["data"][0]
            price = offer["price"]["total"]
            try:
                eur = float(price)
                inr = eur * EUR_TO_INR
                price_str = f"{inr:.2f} INR"
            except Exception:
                price_str = "- INR"
            origin_name = origin
            dest_name = destination
            if "dictionaries" in data and "locations" in data["dictionaries"]:
                locs = data["dictionaries"]["locations"]
                if origin in locs and "cityCode" in locs[origin]:
                    origin_name = locs[origin].get("cityCode", origin)
                if destination in locs and "cityCode" in locs[destination]:
                    dest_name = locs[destination].get("cityCode", destination)
            return f"Flight found: {origin} to {destination} on {departure_date}, price: {price_str}", data.get("dictionaries", {})
        else:
            return "No flights found.", {}
    else:
        return f"Flight search error: {resp.text}", {} 