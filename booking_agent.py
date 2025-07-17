# ===============================
# 1. Imports and Environment Setup
# ===============================
import os
import operator
import requests
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
from supabase import create_client, Client
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")

# --- Amadeus API credentials ---
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# =================================
# 2. API Client Initialization
# =================================

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            return f"Flight found: {origin} to {destination} on {departure_date}, price: {price} EUR"
        else:
            return "No flights found."
    else:
        return f"Flight search error: {resp.text}"

def get_hotel_ids_for_city(city_code):
    """Get hotel IDs for a given city code using Amadeus API."""
    token = get_amadeus_access_token()
    url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-city"
    params = {"cityCode": city_code}
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data"):
            # Return a list of hotelIds (limit to 5 for demo)
            return [hotel["hotelId"] for hotel in data["data"][:5]]
    return []

def search_hotels(city_code, checkin_date, checkout_date):
    """Search for hotels using Amadeus API."""
    token = get_amadeus_access_token()
    hotel_ids = get_hotel_ids_for_city(city_code)
    if not hotel_ids:
        return "No hotels found (could not retrieve hotel IDs)."
    url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    params = {
        "hotelIds": ",".join(hotel_ids),
        "checkInDate": checkin_date,
        "checkOutDate": checkout_date,
        "adults": 1,
        "roomQuantity": 1,
        "bestRateOnly": True,
        "view": "FULL"
    }
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        if data.get("data"):
            hotel = data["data"][0]
            name = hotel["hotel"]["name"]
            price = hotel["offers"][0]["price"]["total"]
            return f"Hotel found: {name}, price: {price} EUR"
        else:
            return "No hotels found."
    else:
        return f"Hotel search error: {resp.text}"

# --- Supabase plan functions ---
def supabase_get_plans():
    """Retrieve all travel plans from Supabase."""
    if not supabase:
        return []
    res = supabase.table("plans").select("name, description").execute()
    return res.data if res.data else []

def supabase_add_plan(plan: dict):
    """Add a new travel plan to Supabase."""
    if not supabase:
        return {"status": "error", "message": "Supabase not configured."}
    try:
        res = supabase.table("plans").insert(plan).execute()
        if res.data:
            return {"status": "success"}
        else:
            return {"status": "error", "message": str(res)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def supabase_get_plan_details(plan_name):
    """Get details (origin, destination, city_code) for a specific plan from Supabase."""
    if not supabase:
        return None, None, None
    res = supabase.table("plans").select("origin, destination, city_code").eq("name", plan_name).limit(1).execute()
    if res.data and len(res.data) > 0:
        row = res.data[0]
        return row["origin"], row["destination"], row["city_code"]
    return None, None, None

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
    origin, dest, city_code = supabase_get_plan_details(plan)
    if not origin or not dest or not city_code:
        return f"Plan '{plan}' is not available."
    # Use only Amadeus for flight search
    flight_info = ""
    try:
        if AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET:
            flight_info = search_flights(origin, dest, dep_date_str)
        else:
            flight_info = "No flight API credentials configured."
    except Exception as e:
        flight_info = f"Flight search error: {str(e)}"
    hotel_info = search_hotels(city_code, dep_date_str, ret_date_str) if AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET else "Hotel search not available (Amadeus credentials required)."

    # Parse flight_info
    flight_status = "❌ Not Booked"
    flight_from = origin
    flight_to = dest
    flight_date = dep_date_str
    flight_price = "-"
    flight_status_line = ""
    if flight_info.startswith("Flight found:"):
        # Example: Flight found: LAX to HND on 2025-07-31, price: 404.18 EUR
        try:
            parts = flight_info.split(": ")[1]
            route, rest = parts.split(" on ")
            from_to = route.split(" to ")
            flight_from = from_to[0].strip()
            flight_to = from_to[1].strip().split(",")[0]
            date_part, price_part = rest.split(", price: ")
            flight_date = date_part.strip()
            flight_price = price_part.strip()
            flight_status = "✅ Booked Successfully"
        except Exception:
            pass
    elif flight_info.startswith("No flights found") or "error" in flight_info.lower():
        flight_status = "❌ Not Booked"
        flight_status_line = f"Reason: {flight_info}"
    else:
        flight_status = "❌ Not Booked"
        flight_status_line = f"Reason: {flight_info}"

    # Parse hotel_info
    hotel_status = "❌ Not Booked"
    hotel_name = "-"
    hotel_price = "-"
    hotel_status_line = ""
    if hotel_info.startswith("Hotel found:"):
        # Example: Hotel found: Best Western Gaillon Opera, price: 1324.45 EUR
        try:
            parts = hotel_info.split(": ")[1]
            name, price = parts.split(", price: ")
            hotel_name = name.strip()
            hotel_price = price.strip()
            hotel_status = "✅ Booked Successfully"
        except Exception:
            pass
    elif hotel_info.startswith("No hotels found") or "error" in hotel_info.lower():
        hotel_status = "❌ Not Booked"
        hotel_status_line = f"Reason: {hotel_info}"
    else:
        hotel_status = "❌ Not Booked"
        hotel_status_line = f"Reason: {hotel_info}"

    # Build structured output
    result = f"""
                Plan: {plan}
                Status: ✅ Complete

                ✈️ Flight Details
                From: {flight_from}
                To: {flight_to}
                Date: {flight_date}
                Price: {flight_price}
                Status: {flight_status}
                {flight_status_line}

                🏨 Hotel Details
                Status: {hotel_status}
                """
    if hotel_status == "✅ Booked Successfully":
        result += f"Name: {hotel_name}\nPrice: {hotel_price}\n"
    else:
        result += f"{hotel_status_line}\n"
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
def get_plans():
    """Endpoint to get all travel plans."""
    plans = supabase_get_plans()
    return JSONResponse({"plans": plans})

@app.post("/add_plan")
def add_plan(plan: dict):
    """Endpoint to add a new travel plan."""
    return supabase_add_plan(plan)

@app.post("/select_plan")
async def select_plan(request: Request):
    """Endpoint to select and book a travel plan for a customer."""
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

# =================================
# 7. Main Entrypoint
# =================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 