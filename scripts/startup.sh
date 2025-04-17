#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the absolute path of the project root
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

echo -e "${GREEN}Starting SAS Application Stack...${NC}"

# Function to check if a port is in use
check_port() {
    lsof -i:$1 >/dev/null 2>&1
}

# Function to kill process on a specific port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ ! -z "$pids" ]; then
        echo -e "${YELLOW}Found existing process(es) on port $port (PIDs: $pids). Stopping them...${NC}"
        for pid in $pids; do
            pkill -P $pid 2>/dev/null  # Kill children first
            kill -9 $pid 2>/dev/null    # Kill the parent
        done
        sleep 2
    fi
}

# Kill any existing Flask processes
kill_flask() {
    # Find and kill any Python processes running start.py
    local flask_pids=$(pgrep -f "python.*start.py")
    if [ ! -z "$flask_pids" ]; then
        echo -e "${YELLOW}Found existing Flask processes (PIDs: $flask_pids). Stopping them...${NC}"
        for pid in $flask_pids; do
            echo -e "${YELLOW}Killing Flask process $pid and its children...${NC}"
            pkill -TERM -P $pid 2>/dev/null  # Kill children first
            kill -TERM $pid 2>/dev/null       # Try SIGTERM first
            sleep 1
            # If process still exists, force kill it
            if ps -p $pid > /dev/null; then
                pkill -9 -P $pid 2>/dev/null
                kill -9 $pid 2>/dev/null
            fi
        done
        sleep 2
    fi
}

# Check if PostgreSQL is running
echo -e "\n${GREEN}Checking PostgreSQL status...${NC}"
if ! pg_isready > /dev/null 2>&1; then
    echo -e "${RED}PostgreSQL is not running. Starting PostgreSQL...${NC}"
    brew services start postgresql@14
    sleep 5  # Wait for PostgreSQL to fully start
else
    echo -e "${GREEN}PostgreSQL is already running${NC}"
fi

# Check if database exists, if not create it
if ! psql -lqt | cut -d \| -f 1 | grep -qw sas_api_db; then
    echo -e "${GREEN}Creating database sas_api_db...${NC}"
    createdb sas_api_db
fi

# Kill any existing processes
echo -e "\n${GREEN}Cleaning up existing processes...${NC}"
kill_flask      # Kill Flask processes first
if check_port 5001; then
    kill_port 5001
fi
if check_port 3000; then
    kill_port 3000
fi

# Double-check port 5001 is free
if check_port 5001; then
    echo -e "${RED}Failed to free up port 5001. Please check manually or try again.${NC}"
    exit 1
fi

# Create the API startup script
cat > "${PROJECT_ROOT}/scripts/start_api.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/.."
source venv/bin/activate
export FLASK_APP=run.py
export FLASK_ENV=development
export FLASK_DEBUG=1
python start.py
EOF

# Create the UI startup script
cat > "${PROJECT_ROOT}/scripts/start_ui.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../../sas-ui/client"
export PORT=3000
npm install
npm start
EOF

# Make scripts executable
chmod +x "${PROJECT_ROOT}/scripts/start_api.sh"
chmod +x "${PROJECT_ROOT}/scripts/start_ui.sh"

# Function to open a new terminal with a title
open_terminal() {
    local title=$1
    local command=$2
    osascript <<EOF
tell application "Terminal"
    activate
    set newTab to do script "${command}"
    set custom title of tab 1 of window 1 to "${title}"
    delay 1
end tell
EOF
}

# Start API in new terminal
echo -e "\n${GREEN}Starting API in new terminal...${NC}"
open_terminal "SAS API" "cd '${PROJECT_ROOT}' && ./scripts/start_api.sh; exec \$SHELL"

# Wait a moment for API to start
sleep 3

# Start UI in new terminal
echo -e "\n${GREEN}Starting UI in new terminal...${NC}"
open_terminal "SAS UI" "cd '${PROJECT_ROOT}' && ./scripts/start_ui.sh; exec \$SHELL"

echo -e "\n${GREEN}All components started in separate terminals!${NC}"
echo -e "API should be running on http://localhost:5001"
echo -e "UI should be available on http://localhost:3000"
echo -e "\nTo stop all components, run: ./scripts/shutdown.sh"

# Wait a moment to ensure terminals are opened
sleep 2

# Check if services are running
echo -e "\n${GREEN}Checking service status:${NC}"
if curl -s http://localhost:5001 > /dev/null; then
    echo -e "${GREEN}✓ API is running on port 5001${NC}"
else
    echo -e "${RED}✗ API is not responding on port 5001${NC}"
fi

if curl -s http://localhost:3000 > /dev/null; then
    echo -e "${GREEN}✓ UI is running on port 3000${NC}"
else
    echo -e "${RED}✗ UI is not responding on port 3000${NC}"
fi 