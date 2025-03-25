
## Setup Instructions

```bash
pip install -r requirements.txt
```

```bash
brew services start postgresql
```

Create or modify the `.env` file in the root directory with your database credentials and other configurations:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```

```bash
# Initialize the database
flask db upgrade

# If this is your first time setting up:
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### Running the Application

```bash
# Development mode
python run.py
```

The API will be running at `http://localhost:5000` by default.

