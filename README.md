# SAS-API

This is the backend API for the SAS (Speed Acquaintances Service) application.

## Setup and Installation

### Prerequisites

- Python 3.7+
- PostgreSQL (or SQLite for development)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sas-api.git
cd sas-api
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file in the project root with the following content:
```
DATABASE_URL=sqlite:///app.db
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
```

5. Initialize the database:
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

## Running the Application

Start the Flask development server:
```bash
flask run
```

The API will be available at `http://localhost:5000`.

## API Endpoints

### Authentication

- `POST /user/signup`: Register a new user
- `POST /user/signin`: Login existing user

### Health Check

- `GET /health`: Basic health check endpoint

## Development

To run the application in debug mode:
```bash
FLASK_DEBUG=1 flask run
```

## Testing

Run tests with:
```bash
pytest
```
