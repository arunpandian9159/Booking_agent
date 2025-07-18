import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_LOCATION = os.getenv("GOOGLE_LOCATION", "us-central1")

# Amadeus API
AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

# TripXplo API
API_BASE = "https://api.tripxplo.com/v1/api"
TRIPXPLO_EMAIL = os.getenv("TRIPXPLO_EMAIL")
TRIPXPLO_PASSWORD = os.getenv("TRIPXPLO_PASSWORD")

# Currency conversion
EUR_TO_INR = 99.7  # As of July 2025 