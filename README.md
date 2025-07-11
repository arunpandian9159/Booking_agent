# Booking Agent Chatbot

A conversational AI agent for booking flights, cabs, trains, and sleeper buses. The agent classifies user requests and routes them to the appropriate booking handler using a language model (Google Gemini via LangChain).

## Features
- Classifies booking requests: flight, cab, train, sleeper bus, or unknown
- Handles each booking type with a simulated confirmation
- Interactive command-line chat interface

## Requirements
- Python 3.8+
- Google API Key for Gemini (set as `GOOGLE_API_KEY` in a `.env` file)

### Python Dependencies
All dependencies are listed in `requirements.txt`:
- langgraph
- pydantic
- langchain-google-genai
- python-dotenv

Install them with:
```bash
pip install -r requirements.txt
```

## Setup
1. **Clone the repository**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up your Google API Key:**
   - Create a `.env` file in the project root:
     ```env
     GOOGLE_API_KEY=your_google_api_key_here
     ```

## Usage
Run the chatbot from the command line:
```bash
python main.py
```
Type your booking request (e.g., "Book a flight to Paris" or "I need a cab to the airport"). Type `exit` to quit.

## Example
```
Message: Book a train ticket to New York
Assistant: Train ticket booked! Confirmation: TRAIN789
```

## Project Structure
- `main.py` - Main chatbot logic and booking agent
- `requirements.txt` - Python dependencies
- `README.md` - Project documentation

## License
MIT License
