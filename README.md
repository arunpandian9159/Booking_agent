# Travel Booking Terminal

A terminal-based AI assistant for booking travel services such as flights, cabs, trains, and sleeper buses. Powered by Google Gemini (via LangChain) and FastAPI ecosystem tools.

## Features
- Classifies user requests as flight, cab, train, sleeper bus, or unknown
- Simulates booking and provides confirmation for each type
- Interactive terminal chat interface
- Built with LangGraph, LangChain, and Google Generative AI

## Requirements
- Python 3.8+
- Google Generative AI API key (for Gemini)

## Installation
1. Clone this repository:
   ```bash
   git clone <repo-url>
   cd <repo-folder>
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your Google API key:
   - Create a `.env` file in the project root with:
     ```env
     GOOGLE_API_KEY=your_google_api_key_here
     ```

## Usage
Run the chatbot in your terminal:
```bash
python travel_booking_terminal.py
```
Type your booking request (e.g., "Book a flight to Paris" or "I need a cab to the airport"). Type `exit` to quit.

## Dependencies
- fastapi
- uvicorn
- langgraph
- requests
- pydantic
- langchain-google-community
- langchain-google-genai

## Notes
- This app simulates bookings and does not make real reservations.
- Requires a valid Google Generative AI API key for operation.

## License
MIT 