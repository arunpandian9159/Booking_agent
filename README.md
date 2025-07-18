# Booking Agent

A modular FastAPI-based travel booking agent that integrates with TripXplo and Amadeus APIs, and uses Google Gemini LLM for advanced parsing and recommendations.

## Features
- Search and view travel packages (TripXplo)
- Book travel plans (flights, hotels)
- Fetch destinations and packages by destination
- Currency conversion (EUR to INR)
- LLM-powered parsing for flight and hotel data
- Modular, maintainable codebase

## Project Structure
```
Booking_agent/
├── amadeus_api.py         # Amadeus API integration (token, flight search)
├── auth.py                # Authentication helpers (if needed)
├── business_logic.py      # Core business logic (booking, hotel extraction)
├── config.py              # Environment variables, constants, logging
├── llm_utils.py           # LLM setup and parsing helpers
├── main.py                # FastAPI app and endpoints
├── packages.py            # Package fetching helpers
├── requirements.txt       # Python dependencies
├── render.yaml            # Deployment config (Render.com)
├── static/
│   └── index.html         # Frontend (if any)
├── tripxplo_api.py        # TripXplo API integration
├── utils.py               # Utility functions (currency, city mapping)
└── README.md              # This file
```

## Setup
1. **Clone the repository**
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set environment variables**
   - Create a `.env` file in the root directory with the following keys:
     ```env
     GOOGLE_API_KEY=your_google_api_key
     GOOGLE_PROJECT_ID=your_project_id
     GOOGLE_LOCATION=us-central1
     AMADEUS_CLIENT_ID=your_amadeus_client_id
     AMADEUS_CLIENT_SECRET=your_amadeus_client_secret
     TRIPXPLO_EMAIL=your_tripxplo_email
     TRIPXPLO_PASSWORD=your_tripxplo_password
     ```
4. **Run the app**
   ```bash
   python main.py
   ```
   The API will be available at `http://localhost:8000/`

## API Endpoints
- `GET /` — Serve the frontend (static/index.html)
- `GET /plans` — List available travel plans
- `POST /select_plan` — Book a selected plan
- `POST /book` — Book a plan (alternate endpoint)
- `GET /destinations` — List all destinations
- `GET /packages?destination=DEST` — List packages for a destination

## Customization
- Add new business logic in `business_logic.py`
- Extend API integrations in `tripxplo_api.py` or `amadeus_api.py`
- Add utility functions in `utils.py`

## License
MIT 
