# ===============================
# 1. Imports and Environment Setup
# ===============================
import os
import operator
import requests
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from typing import Annotated, Sequence, TypedDict, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_core.messages import ToolMessage, AIMessage
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from packages import fetch_packages
from datetime import datetime, timedelta
import re

# Load environment variables from .env file
load_dotenv()  # For TripXplo

# Logging setup for TripXplo
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")

# --- Amadeus API credentials ---
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

# --- TripXplo API credentials ---
API_BASE = "https://api.tripxplo.com/v1/api"
TRIPXPLO_EMAIL = os.getenv("TRIPXPLO_EMAIL")
TRIPXPLO_PASSWORD = os.getenv("TRIPXPLO_PASSWORD")

# =================================
# 2. TripXplo API Functions
# =================================

_token_cache = None

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
        # Map to expected format: name, description
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
        logger.info(f"[DEBUG] TripXplo API response for plan search '{plan_name}': {packages}")
        # Case-insensitive, partial match
        plan_name_lower = plan_name.lower()
        for p in packages:
            if p.get("name") and plan_name_lower in p.get("name").lower():
                origin = p.get("origin") or p.get("from")
                dest = p.get("destination") or p.get("to")
                city_code = p.get("city_code") or p.get("cityCode") or p.get("to")
                return origin, dest, city_code, p.get("name"), p.get("_id")
        # If not found, return all available plan names for error reporting
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

# Add function to fetch package by ID
def tripxplo_get_package_by_id(package_id: str):
    token = get_tripxplo_token()
    try:
        # Fetch all packages (or use a search if needed)
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

# =================================
# 3. Utility/API Functions
# =================================

# --- Amadeus API integration ---
def get_amadeus_access_token():
    """Obtain an access token from Amadeus API."""
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": AMADEUS_CLIENT_ID,
        "client_secret": AMADEUS_CLIENT_SECRET
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]

# Add a helper function for EUR to INR conversion
EUR_TO_INR = 99.7  # As of July 2025

def eur_to_inr(eur_str):
    try:
        eur = float(eur_str)
        inr = eur * EUR_TO_INR
        return f"{inr:.2f} INR ({{eur:.2f}} EUR)"
    except Exception:
        return f"- INR (- EUR)"

def search_flights(origin, destination, departure_date):
    """Search for flights using Amadeus API."""
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
            # Convert EUR to INR and show only INR
            try:
                eur = float(price)
                inr = eur * EUR_TO_INR
                price_str = f"{inr:.2f} INR"
            except Exception:
                price_str = "- INR"
            # Get airport names from dictionaries if available
            origin_name = origin
            dest_name = destination
            if "dictionaries" in data and "locations" in data["dictionaries"]:
                locs = data["dictionaries"]["locations"]
                if origin in locs and "cityCode" in locs[origin]:
                    origin_name = locs[origin].get("cityCode", origin)
                if destination in locs and "cityCode" in locs[destination]:
                    dest_name = locs[destination].get("cityCode", destination)
            # Return airport code for now, will update in book_travel for full name
            return f"Flight found: {origin} to {destination} on {departure_date}, price: {price_str}", data.get("dictionaries", {})
        else:
            return "No flights found.", {}
    else:
        return f"Flight search error: {resp.text}", {}

# =================================
# 3A. LLM-powered Parsing Functions
# =================================

def parse_flight_with_llm(api_response):
    """Use the LLM to extract and format all relevant flight details from the API response."""
    prompt = f"""
    The following is a flight API response (JSON or text):
    {api_response}
    Extract and present all relevant details in a markdown table with columns: Route, Departure, Arrival, Duration, Aircraft, Carrier, Fare, Seats left, Checked bags, Last ticketing date. If any field is missing, leave it blank. Show all available details.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        return result.content if hasattr(result, 'content') else str(result)
    except Exception as e:
        return f"[LLM parse error: {e}]"

def parse_hotel_with_llm(api_response):
    """Use the LLM to extract and format all relevant hotel details from the API response."""
    prompt = f"""
    The following is a hotel API response (JSON or text):
    {api_response}
    Extract and present all relevant hotel options in a markdown table with columns: Hotel (City), Best 7-night price, Room, Refundability, Notes. If any field is missing, leave it blank. Show all available details.
    """
    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        return result.content if hasattr(result, 'content') else str(result)
    except Exception as e:
        return f"[LLM parse error: {e}]"

# =================================
# 4. Business Logic
# =================================

class AgentState(TypedDict):
    """State for the LangGraph agent, containing a sequence of messages."""
    messages: Annotated[Sequence[BaseMessage], operator.add]

# Remove @tool decorator
def book_travel(plan: str, customer: str, date: str = "") -> str:
    """
    Books travel for the customer based on the selected package ID and date.
    - plan: should be the TripXplo package ID
    - Fetch package by ID, extract destination, use for flight search
    - Fetch hotels for that package
    """
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
    # Fetch package by ID
    package = tripxplo_get_package_by_id(plan)
    logger.info(f"[DEBUG] Package data: {package}")
    if not package:
        return f"Package with ID '{plan}' not found."
    plan_actual_name = package.get("packageName") or package.get("name") or plan
    # Extract destination code for Amadeus
    dest = None
    # If destination is a list, pick the first and look for a 3-letter code
    destination_data = package.get("destination") or package.get("to") or package.get("city_code") or package.get("cityCode")
    if isinstance(destination_data, list) and destination_data:
        dest_obj = destination_data[0]
        destination_id = dest_obj.get("destinationId")
        city_name = ""
        if destination_id:
            dest_details = tripxplo_get_destination_by_id(destination_id)
            city_name = dest_details.get("name") or dest_details.get("city") or ""
        if not city_name:
            # Fallback: extract city from package name or destinationName
            city_name = extract_city_from_package_name(plan_actual_name, package)
        dest = city_to_iata(city_name)
    elif isinstance(destination_data, str) and len(destination_data) == 3:
        dest = destination_data
    if not dest:
        return f"Destination code not found or invalid in package. Package: {plan_actual_name}. Raw destination data: {destination_data}"
    origin = "MAA"  # Always use Chennai as origin
    # --- Amadeus flight search ---
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
    # --- TripXplo hotel search ---
    hotel_info = ""
    try:
        hotels = extract_hotels_from_package(package)
        if not hotels:
            hotels = tripxplo_get_hotels(plan)
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
            if not hotel_name:
                hotel_id = h.get("hotelId")
                if not hotel_id:
                    logger.warning(f"HotelId is missing. Full hotel object: {h}")
                logger.info(f"Hotel name missing, will try to fetch by hotelId: {hotel_id}")
                if hotel_id and isinstance(hotel_id, str) and len(hotel_id) >= 8:
                    hotel_details = tripxplo_get_hotel_by_id(hotel_id)
                    hotel_name = hotel_details.get("name", "")
                else:
                    logger.warning(f"hotelId is missing or invalid, skipping fetch: {hotel_id}")
                    # Fallback: try to get hotel name from _id mapping
                    room_id = h.get("_id")
                    if room_id:
                        hotel_map = get_hotel_id_to_name_mapping()
                        hotel_name = hotel_map.get(room_id, "")
                        if hotel_name:
                            logger.info(f"Found hotel name from _id mapping: {hotel_name}")
                        else:
                            logger.warning(f"No hotel name found in mapping for _id: {room_id}")
            meal_plan = h.get("mealPlan", "")
            nights = h.get("noOfNight", "")
            rows.append(f"| {hotel_name} | {meal_plan} | {nights} |")
        if rows:
            hotel_info = (
                "| Hotel Name | Meal Plan | Nights |\n"
                "|-----------|-----------|--------|\n" +
                "\n".join(rows)
            )
        else:
            hotel_info = "No hotels found."
    except Exception as e:
        hotel_info = f"Hotel search error: {str(e)}"
    # Build structured output
    result = (
        f"Package: {plan_actual_name}\n"
        f"Status: ✅ Complete\n"
        f"\n"
        f"✈️ Flight Details (sorted by price, Chennai to {dest})\n"
        f"{flight_info}\n"
        f"\n"
        f"🏨 Hotel Details (sorted by price)\n"
        f"{hotel_info}\n"
    )
    return result.strip()

def extract_hotels_from_package(package):
    # Prefer the 'hotel' field if present and is a list
    hotels = package.get("hotel")
    if hotels and isinstance(hotels, list):
        return hotels
    # Fallback to previous logic
    for key in ["hotels", "hotelOptions", "availableHotels"]:
        hotels = package.get(key)
        if hotels and isinstance(hotels, list):
            return hotels
    return []

# =================================
# 5. LangGraph/LLM Setup
# =================================

# Initialize the Google LLM (Gemini 2.5 Pro) using Generative AI API
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",  # Use Gemini 2.5 Pro
    google_api_key=GOOGLE_API_KEY,
)
tools = [book_travel]
llm_with_tools = llm.bind_tools(tools)

def invoke_llm(state: AgentState):
    """Node: LLM with tools. Invokes the LLM with the current state messages."""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def call_tool(state: AgentState):
    """Node: Call booking tool if needed."""
    outputs = []
    last_message = state["messages"][-1]
    # Only AIMessage has 'tool_calls'
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", []):
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "book_travel":
                result = book_travel.invoke(tool_call["args"])
                outputs.append(
                    ToolMessage(
                        content=result,
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                    )
                )
    return {"messages": outputs}

def should_continue(state: AgentState):
    """Edge logic: decide if we need to call the tool or finish."""
    messages = state["messages"]
    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", []):
        return "action"
    return "END"

# Build the LangGraph workflow
def build_workflow():
    """Build and compile the LangGraph workflow for the agent."""
    workflow = StateGraph(AgentState)
    workflow.add_node("LLM", invoke_llm)
    workflow.add_node("action", call_tool)
    workflow.set_entry_point("LLM")
    workflow.add_conditional_edges(
        "LLM",
        should_continue,
        {"action": "action", "END": END}
    )
    workflow.add_edge("action", "LLM")
    return workflow.compile()
app_graph = build_workflow()

# =================================
# 6. FastAPI App and Endpoints
# =================================

app = FastAPI()

# Mount static files (e.g., frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    """Serve the main index.html file."""
    return FileResponse("static/index.html")

@app.get("/plans")
async def get_plans():
    """Endpoint to get all travel plans (TripXplo, async)."""
    try:
        plans = await fetch_packages()
        plans = [{"name": p.get("name"), "description": p.get("description")} for p in plans]
        return JSONResponse({"plans": plans})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/add_plan")
def add_plan(plan: dict):
    """Endpoint to add a new travel plan (not supported in TripXplo demo)."""
    return {"status": "error", "message": "Adding plans is not supported via TripXplo API."}

@app.post("/select_plan")
async def select_plan(request: Request):
    """Endpoint to select and book a travel plan for a customer (TripXplo for plan/hotel, Amadeus for flight)."""
    data = await request.json()
    plan = data.get("plan") or ""
    customer = data.get("customer") or ""
    date = data.get("date") or ""
    if not plan:
        return JSONResponse({"error": "Plan is required."}, status_code=400)
    system_message = SystemMessage(content="You are a travel booking agent. When a customer selects a plan, book it for them.")
    human_message = HumanMessage(content=f"Customer {customer} selected plan: {plan} for departure on {date}. Please book it.")
    state = AgentState(messages=[system_message, human_message])
    # Directly call the function with the date argument
    result = book_travel(plan=plan, customer=customer, date=date)
    return {"status": "booking_completed", "result": result}

@app.post("/book")
async def book(request: Request):
    """Endpoint to book a travel plan for a customer (alias for /select_plan)."""
    data = await request.json()
    plan = data.get("plan") or ""
    customer = data.get("customer") or ""
    date = data.get("date") or ""
    if not plan:
        return JSONResponse({"error": "Plan is required."}, status_code=400)
    system_message = SystemMessage(content="You are a travel booking agent. When a customer selects a plan, book it for them.")
    human_message = HumanMessage(content=f"Customer {customer} selected plan: {plan} for departure on {date}. Please book it.")
    state = AgentState(messages=[system_message, human_message])
    result = book_travel(plan=plan, customer=customer, date=date)
    return {"status": "booking_completed", "result": result}

@app.get("/destinations")
async def get_destinations():
    """Endpoint to get all destinations (extracted from plans)."""
    try:
        plans = await fetch_packages()
        destinations = set()
        for p in plans:
            # Use 'destinationName' which is a comma-separated string of names
            dest_names = p.get("destinationName")
            if dest_names:
                for name in dest_names.split(","):
                    name = name.strip()
                    if name:
                        destinations.add(name)
        return JSONResponse({"destinations": sorted(destinations)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/packages")
async def get_packages(destination: str = ""):
    """Endpoint to get all packages for a given destination (by destinationName)."""
    try:
        packages = await fetch_packages()
        filtered = []
        for p in packages:
            dest_names = p.get("destinationName", "")
            if dest_names:
                dest_list = [d.strip() for d in dest_names.split(",") if d.strip()]
                if destination in dest_list:
                    filtered.append({
                        "id": p.get("_id"),
                        "name": p.get("packageName")
                    })
        if filtered:
            pass  # Removed debug print
        return JSONResponse({"packages": filtered})
    except Exception as e:
        print(f"[ERROR] /packages exception: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# =================================
# 7. Main Entrypoint
# =================================

# Add a static mapping for city name to IATA code
CITY_TO_IATA = {
    "Kodaikanal": "MAA",  # Nearest major airport (Madurai or Coimbatore are closer, but Chennai is a larger hub)
    "Kullu": "KUU",      # Bhuntar Airport
    "Kumarakom": "COK",  # Cochin International Airport (nearest major airport)
    "Kuta": "DPS",       # Denpasar, Bali Airport
    "Manali": "KUU",     # Bhuntar Airport (for Kullu, nearest to Manali)
    "Meghalaya": "SHL",  # Shillong Airport (for Meghalaya)
    "Munnar": "COK",     # Cochin International Airport (nearest major airport)
    "Mysore": "MYQ",
    "Neil Island": "IXZ", # Port Blair Airport (for Andaman & Nicobar Islands)
    "Ooty": "CJB",       # Coimbatore International Airport (nearest major airport)
    "Pahalgam": "SXR",   # Srinagar International Airport (nearest major airport)
    "Port Blair": "IXZ",
    "Seminyak": "DPS",   # Denpasar, Bali Airport
    "Shillong": "SHL",
    "Shimla": "SLV",     # Shimla Airport
    "Sikkim": "PYG",     # Pakyong Airport (for Sikkim)
    "Siliguri": "IXB",   # Bagdogra International Airport (nearest major airport)
    "Srinagar": "SXR",
    "Ubud": "DPS",       # Denpasar, Bali Airport
    "Varkala": "TRV",    # Thiruvananthapuram International Airport (nearest major airport)
    "Agra": "AGR",
    "Alleppey": "COK",   # Cochin International Airport (nearest major airport)
    "Andaman": "IXZ",    # Port Blair Airport
    "Bali": "DPS",
    "Chandigarh": "IXC",
    "Cherrapunjee": "SHL", # Shillong Airport (nearest major airport)
    "Coimbatore": "CJB",
    "Coonoor": "CJB",    # Coimbatore International Airport (nearest major airport)
    "Coorg": "IXM",      # Madurai Airport (nearest major airport, though Mangalore or Kannur are also options)
    "Darjeeling": "IXB", # Bagdogra International Airport (nearest major airport)
    "Delhi": "DEL",
    "Dwaki": "SHL",      # Shillong Airport (nearest major airport)
    "Gangtok": "PYG",    # Pakyong Airport (for Sikkim, nearest to Gangtok)
    "Goa": "GOX",        # Manohar International Airport, Mopa, Goa (or Dabolim Airport GOI)
    "Havelock": "IXZ",   # Port Blair Airport (for Andaman & Nicobar Islands)
    "Himachal": "KUU",   # Multiple airports, Bhuntar is a common one for tourist areas
    "Kashmir": "SXR",    # Srinagar International Airport (major airport in Kashmir)
    "Kasol": "KUU",      # Bhuntar Airport (nearest to Kasol)
    "Kaziranga": "JRH",  # Jorhat Airport (nearest to Kaziranga)
    "Kochi": "COK",
    "Wayanad": "CCJ",    # Calicut International Airport (nearest major airport)
    "Kerala": "COK",     # Multiple airports, Cochin is a major hub
    "Bangkok": "BKK",
    "Singapore": "SIN"
    # Add more as needed
}

def city_to_iata(city_name: str) -> str:
    """Convert city name to IATA code using static mapping."""
    return CITY_TO_IATA.get(city_name.strip().title(), "")

def extract_city_from_package_name(package_name: str, package: dict = {}) -> str:
    # Try to match known city names in the package name
    for city in CITY_TO_IATA.keys():
        if city.lower() in package_name.lower():
            return city
    # Try destinationName field if available
    dest_names = package.get("destinationName", "")
    for city in CITY_TO_IATA.keys():
        if city.lower() in dest_names.lower():
            return city
    # Fallback: regex for 'in <City>'
    match = re.search(r'in ([A-Za-z ]+)', package_name)
    if match:
        return match.group(1).strip()
    return ""

# Add function to fetch destination details by ID

def tripxplo_get_destination_by_id(destination_id: str):
    token = get_tripxplo_token()
    if not destination_id or not isinstance(destination_id, str) or len(destination_id) < 8:
        logger.warning(f"Destination ID is missing or invalid: {destination_id}")
        return {}
    try:
        logger.info(f"Fetching destination by ID: {destination_id}")
        response = requests.get(
            f"{API_BASE}/admin/destination/{destination_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("result", {})
    except Exception as e:
        logger.error(f"Error fetching destination by ID {destination_id}: {e}")
        return {}

# Add function to fetch hotel by ID

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

# --- Hotel name mapping by _id ---
_hotel_id_to_name_cache = None

def get_hotel_id_to_name_mapping():
    global _hotel_id_to_name_cache
    if _hotel_id_to_name_cache is not None:
        return _hotel_id_to_name_cache
    token = get_tripxplo_token()
    try:
        response = requests.get(
            f"{API_BASE}/admin/hotel",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        hotels = response.json().get("result", [])
        mapping = {}
        for hotel in hotels:
            hid = hotel.get("_id")
            name = hotel.get("name")
            if hid and name:
                mapping[hid] = name
        _hotel_id_to_name_cache = mapping
        logger.info(f"Loaded hotel _id to name mapping for {len(mapping)} hotels.")
        return mapping
    except Exception as e:
        logger.error(f"Error fetching all hotels for mapping: {e}")
        return {}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
    