# Booking Agent

This is a Booking Agent application for managing travel plans. The backend is implemented in Python and uses Supabase as the database for storing travel plans.

## Features
- Manage and store travel plans
- Integration with Supabase database
- Simple web interface (see `static/index.html`)

## Project Structure
- `booking_agent.py`: Main backend application
- `static/index.html`: Frontend HTML file
- `requirements.txt`: Python dependencies
- `package-lock.json`: Node dependencies (if applicable)

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js (if using frontend build tools)
- Supabase account and project

### Installation
1. Clone the repository:
   ```bash
   git clone <https://github.com/arunpandian9159/Booking_agent>
   cd Booking_agent
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. (Optional) Install Node dependencies:
   ```bash
   npm install
   ```
4. Configure your Supabase credentials (see below).

### Supabase Configuration
Set your Supabase URL and API key as environment variables or in your configuration file as required by your application.

## Usage
Run the backend server:
```bash
python booking_agent.py
```

Open `static/index.html` in your browser to access the frontend.

## License
MIT 
