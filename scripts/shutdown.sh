#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Shutting down SAS Application Stack...${NC}"

# Kill processes on specific port
kill_port() {
    local port=$1
    local pids=$(lsof -ti:$port)
    if [ ! -z "$pids" ]; then
        echo -e "${YELLOW}Found process(es) on port $port (PIDs: $pids). Stopping them...${NC}"
        for pid in $pids; do
            echo -e "${YELLOW}Killing process $pid and its children...${NC}"
            pkill -TERM -P $pid 2>/dev/null  # Kill children first
            kill -TERM $pid 2>/dev/null       # Try SIGTERM first
            sleep 1
            # If process still exists, force kill it
            if ps -p $pid > /dev/null; then
                pkill -9 -P $pid 2>/dev/null
                kill -9 $pid 2>/dev/null
            fi
        done
    fi
}

# Kill any Flask processes
kill_flask() {
    local flask_pids=$(pgrep -f "python.*start.py")
    if [ ! -z "$flask_pids" ]; then
        echo -e "${YELLOW}Found Flask processes (PIDs: $flask_pids). Stopping them...${NC}"
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
    fi
}

# Kill any Node.js processes for the UI
kill_node() {
    local node_pids=$(pgrep -f "node.*start")
    if [ ! -z "$node_pids" ]; then
        echo -e "${YELLOW}Found Node.js processes (PIDs: $node_pids). Stopping them...${NC}"
        for pid in $node_pids; do
            echo -e "${YELLOW}Killing Node process $pid and its children...${NC}"
            pkill -TERM -P $pid 2>/dev/null  # Kill children first
            kill -TERM $pid 2>/dev/null       # Try SIGTERM first
            sleep 1
            # If process still exists, force kill it
            if ps -p $pid > /dev/null; then
                pkill -9 -P $pid 2>/dev/null
                kill -9 $pid 2>/dev/null
            fi
        done
    fi
}

# Stop the Flask API
echo -e "${GREEN}Stopping Flask API...${NC}"
kill_flask
kill_port 5001

# Stop the UI
echo -e "${GREEN}Stopping UI...${NC}"
kill_node
kill_port 3000

# Clean up any remaining PID files
rm -f /tmp/sas_api.pid /tmp/sas_ui.pid

# Double-check ports are free
if lsof -i:5001 > /dev/null 2>&1; then
    echo -e "${RED}Warning: Port 5001 is still in use${NC}"
fi
if lsof -i:3000 > /dev/null 2>&1; then
    echo -e "${RED}Warning: Port 3000 is still in use${NC}"
fi

# Optionally stop PostgreSQL
read -p "Do you want to stop PostgreSQL? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Stopping PostgreSQL...${NC}"
    brew services stop postgresql@14
fi

echo -e "\n${GREEN}All components have been stopped!${NC}" 