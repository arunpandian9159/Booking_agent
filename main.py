from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from business_logic import book_travel
from packages import fetch_packages
from langchain_core.messages import SystemMessage, HumanMessage
import logging

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")

@app.get("/plans")
async def get_plans():
    try:
        plans = await fetch_packages()
        plans = [{"name": p.get("name"), "description": p.get("description")} for p in plans]
        return JSONResponse({"plans": plans})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/add_plan")
def add_plan(plan: dict):
    return {"status": "error", "message": "Adding plans is not supported via TripXplo API."}

@app.post("/select_plan")
async def select_plan(request: Request):
    data = await request.json()
    plan = data.get("plan") or ""
    customer = data.get("customer") or ""
    date = data.get("date") or ""
    if not plan:
        return JSONResponse({"error": "Plan is required."}, status_code=400)
    system_message = SystemMessage(content="You are a travel booking agent. When a customer selects a plan, book it for them.")
    human_message = HumanMessage(content=f"Customer {customer} selected plan: {plan} for departure on {date}. Please book it.")
    result = book_travel(plan=plan, customer=customer, date=date)
    return {"status": "booking_completed", "result": result}

@app.post("/book")
async def book(request: Request):
    data = await request.json()
    plan = data.get("plan") or ""
    customer = data.get("customer") or ""
    date = data.get("date") or ""
    if not plan:
        return JSONResponse({"error": "Plan is required."}, status_code=400)
    system_message = SystemMessage(content="You are a travel booking agent. When a customer selects a plan, book it for them.")
    human_message = HumanMessage(content=f"Customer {customer} selected plan: {plan} for departure on {date}. Please book it.")
    result = book_travel(plan=plan, customer=customer, date=date)
    return {"status": "booking_completed", "result": result}

@app.get("/destinations")
async def get_destinations():
    try:
        plans = await fetch_packages()
        destinations = set()
        for p in plans:
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
        return JSONResponse({"packages": filtered})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 