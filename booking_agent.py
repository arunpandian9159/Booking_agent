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
        # Debug logging: print the API response for the plan search
        logger.info(f"[DEBUG] TripXplo API response for plan search '{plan_name}': {packages}")
        for p in packages:
            if p.get("name") == plan_name:
                # Try to extract origin, destination, city_code (customize as per TripXplo schema)
                origin = p.get("origin") or p.get("from")
                dest = p.get("destination") or p.get("to")
                city_code = p.get("city_code") or p.get("cityCode") or p.get("to")
                return origin, dest, city_code
        return None, None, None
    except Exception as e:
        logger.error(f"Error fetching plan details: {e}")
        return None, None, None

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
    print(f"[DEBUG] Flight API response: {resp.status_code} {resp.text}")  # Debug print
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
    """Books travel for the customer based on the selected plan and date. Returns a confirmation message with real API data."""
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
    # Fetch plan details from TripXplo
    origin, dest, city_code = tripxplo_get_plan_details(plan)
    if not origin or not dest or not city_code:
        return f"Plan '{plan}' is not available."
    # Use only Amadeus for flight search
    flight_info = ""
    flight_dicts = {}
    flight_api_raw = None
    try:
        if AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET:
            token = get_amadeus_access_token()
            url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": dest,
                "departureDate": dep_date_str,
                "adults": 1,
                "max": 1
            }
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, params=params, headers=headers)
            flight_api_raw = resp.text
            if resp.status_code == 200:
                flight_info = parse_flight_with_llm(resp.text)
            else:
                flight_info = f"Flight search error: {resp.text}"
        else:
            flight_info = "No flight API credentials configured."
    except Exception as e:
        flight_info = f"Flight search error: {str(e)}"
    print(f"[DEBUG] flight_info: {flight_info}")  # Debug print
    # Fetch hotels from TripXplo
    hotel_info = ""
    hotel_api_raw = None
    try:
        # Find the TripXplo plan ID
        token = get_tripxplo_token()
        params = {"limit": 100, "offset": 0, "search": plan}
        response = requests.get(
            f"{API_BASE}/admin/package",
            headers={"Authorization": f"Bearer {token}"},
            params=params
        )
        response.raise_for_status()
        packages = response.json().get("result", {}).get("docs", [])
        plan_id = None
        for p in packages:
            if p.get("name") == plan:
                plan_id = p.get("_id")
                break
        if not plan_id:
            hotel_info = "No hotels found (plan ID not found)."
        else:
            hotels = tripxplo_get_hotels(plan_id)
            if hotels:
                # Use LLM to parse and present hotel info
                hotel_info = parse_hotel_with_llm(str(hotels))
            else:
                hotel_info = "No hotels found."
    except Exception as e:
        hotel_info = f"Hotel search error: {str(e)}"
    print(f"[DEBUG] hotel_info: {hotel_info}")  # Debug print
    # Build structured output
    result = (
        f"Plan: {plan}\n"
        f"Status: ✅ Complete\n"
        f"\n"
        f"✈️ Flight Details (AI Parsed)\n"
        f"{flight_info}\n"
        f"\n"
        f"🏨 Hotel Details (AI Parsed)\n"
        f"{hotel_info}\n"
    )
    return result.strip()

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
    system_message = SystemMessage(content="You are a travel booking agent. When a customer selects a plan, book it for them.")
    human_message = HumanMessage(content=f"Customer {customer} selected plan: {plan} for departure on {date}. Please book it.")
    state = AgentState(messages=[system_message, human_message])
    # Directly call the function with the date argument
    result = book_travel(plan=plan, customer=customer, date=date)
    return {"status": "booking_completed", "result": result}

@app.get("/destinations")
async def get_destinations():
    """Endpoint to get all destinations (extracted from plans)."""
    try:
        plans = await fetch_packages()
        destinations = []
        for p in plans:
            dest = p.get("destination") or p.get("to")
            # If dest is a dict, extract 'name' or 'code'
            if isinstance(dest, dict):
                name = dest.get("name") or dest.get("code")
                if name:
                    destinations.append(name)
            elif isinstance(dest, str):
                destinations.append(dest)
        return JSONResponse({"destinations": destinations})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# =================================
# 7. Main Entrypoint
# =================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 