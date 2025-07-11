import os
from dotenv import load_dotenv
from typing import Annotated, Literal, cast
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro", google_api_key=os.getenv("GOOGLE_API_KEY"))

class BookingClassifier(BaseModel):
    booking_type: Literal["flight", "cab", "train", "sleeper_bus", "unknown"] = Field(
        ...,
        description="Classify the booking type: flight, cab, train, sleeper_bus, or unknown."
    )

class State(TypedDict):
    messages: Annotated[list, add_messages]
    booking_type: str | None
    confirmation: str | None

def classify_booking(state: State):
    last_message = state["messages"][-1]
    classifier_llm = llm.with_structured_output(BookingClassifier)
    result = classifier_llm.invoke([
        {
            "role": "system",
            "content": """Classify the user message as one of the following booking types:
            - 'flight': if the user wants to book a flight/plane/air ticket
            - 'cab': if the user wants to book a cab/taxi/ride
            - 'train': if the user wants to book a train ticket
            - 'sleeper_bus': if the user wants to book a sleeper bus
            - 'unknown': if none of the above
            """
        },
        {"role": "user", "content": last_message.content}
    ])
    result = cast(BookingClassifier, result)
    return {"booking_type": result.booking_type}

def router(state: State):
    booking_type = state.get("booking_type", "unknown")
    if booking_type == "flight":
        return {"next": "flight_agent"}
    elif booking_type == "cab":
        return {"next": "cab_agent"}
    elif booking_type == "train":
        return {"next": "train_agent"}
    elif booking_type == "sleeper_bus":
        return {"next": "sleeper_bus_agent"}
    else:
        return {"next": "unknown_agent"}

def flight_agent(state: State):
    last_message = state["messages"][-1]
    # Simulate booking
    confirmation = "Flight booked! Confirmation: FLIGHT123"
    return {"confirmation": confirmation, "messages": state["messages"] + [{"role": "assistant", "content": confirmation}]}

def cab_agent(state: State):
    last_message = state["messages"][-1]
    confirmation = "Cab booked! Confirmation: CAB456"
    return {"confirmation": confirmation, "messages": state["messages"] + [{"role": "assistant", "content": confirmation}]}

def train_agent(state: State):
    last_message = state["messages"][-1]
    confirmation = "Train ticket booked! Confirmation: TRAIN789"
    return {"confirmation": confirmation, "messages": state["messages"] + [{"role": "assistant", "content": confirmation}]}

def sleeper_bus_agent(state: State):
    last_message = state["messages"][-1]
    confirmation = "Sleeper bus booked! Confirmation: BUS321"
    return {"confirmation": confirmation, "messages": state["messages"] + [{"role": "assistant", "content": confirmation}]}

def unknown_agent(state: State):
    last_message = state["messages"][-1]
    confirmation = "Sorry, I could not determine the booking type. Please specify if you want a flight, cab, train, or sleeper bus."
    return {"confirmation": confirmation, "messages": state["messages"] + [{"role": "assistant", "content": confirmation}]}

graph_builder = StateGraph(State)
graph_builder.add_node("classifier", classify_booking)
graph_builder.add_node("router", router)
graph_builder.add_node("flight_agent", flight_agent)
graph_builder.add_node("cab_agent", cab_agent)
graph_builder.add_node("train_agent", train_agent)
graph_builder.add_node("sleeper_bus_agent", sleeper_bus_agent)
graph_builder.add_node("unknown_agent", unknown_agent)

graph_builder.add_edge(START, "classifier")
graph_builder.add_edge("classifier", "router")
graph_builder.add_conditional_edges(
    "router",
    lambda state: state.get("next"),
    {
        "flight_agent": "flight_agent",
        "cab_agent": "cab_agent",
        "train_agent": "train_agent",
        "sleeper_bus_agent": "sleeper_bus_agent",
        "unknown_agent": "unknown_agent"
    }
)
graph_builder.add_edge("flight_agent", END)
graph_builder.add_edge("cab_agent", END)
graph_builder.add_edge("train_agent", END)
graph_builder.add_edge("sleeper_bus_agent", END)
graph_builder.add_edge("unknown_agent", END)

graph = graph_builder.compile()

def run_travel_booking_chatbot():
    state = {"messages": [], "booking_type": None, "confirmation": None}
    while True:
        user_input = input("Message: ")
        if user_input.lower() == "exit":
            print("Bye")
            break
        state["messages"] = state.get("messages", []) + [
            {"role": "user", "content": user_input}
        ]
        update = graph.invoke(cast(State, state))
        state.update(update)
        if state.get("messages") and len(state["messages"]) > 0:
            last_message = state["messages"][-1]
            # last_message may be a HumanMessage or dict; handle both
            content = last_message.content if hasattr(last_message, "content") else last_message.get("content")
            print(f"Assistant: {content}")

if __name__ == "__main__":
    run_travel_booking_chatbot() 