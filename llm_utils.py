from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from config import GOOGLE_API_KEY

# Initialize the Google LLM (Gemini 2.5 Pro)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-pro",
    google_api_key=GOOGLE_API_KEY,
)

def parse_flight_with_llm(api_response):
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