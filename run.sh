#!/usr/bin/env bash
set -e

PORT=8080
APP="web_app.py"
DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Find a suitable Python (>=3.10 needed for py-clob-client)
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return
        fi
    done
    # Fall back to python3 and hope for the best
    echo "python3"
}

setup_venv() {
    if [ ! -d "$VENV" ]; then
        local PY
        PY=$(find_python)
        echo -e "${YELLOW}Creating virtual environment with $PY...${NC}"
        "$PY" -m venv "$VENV"
    fi
    source "$VENV/bin/activate"
}

kill_all() {
    echo -e "${YELLOW}Stopping running processes...${NC}"
    pkill -f "python.*${APP}" 2>/dev/null && echo -e "${RED}Killed ${APP}${NC}" || echo "No ${APP} process found"
    lsof -ti ":${PORT}" | xargs kill -9 2>/dev/null && echo -e "${RED}Freed port ${PORT}${NC}" || true
    sleep 1
}

start() {
    cd "$DIR"
    setup_venv

    # Install deps if needed
    if ! pip show py-clob-client &>/dev/null || ! pip show kalshi-python &>/dev/null || ! pip show flask &>/dev/null; then
        echo -e "${YELLOW}Installing dependencies...${NC}"
        pip install -r requirements.txt
    fi

    # Copy config template if no config exists
    if [ ! -f config.json ] && [ -f config_template.json ]; then
        echo -e "${YELLOW}Creating config.json from template (edit with your API keys)${NC}"
        cp config_template.json config.json
    fi

    echo -e "${GREEN}Starting ${APP} on port ${PORT}...${NC}"
    python3 "$APP" &
    APP_PID=$!
    echo -e "${GREEN}Started with PID ${APP_PID}${NC}"
    echo -e "${GREEN}Open http://localhost:${PORT} in your browser${NC}"
    wait "$APP_PID"
}

case "${1:-start}" in
    start)
        start
        ;;
    stop)
        kill_all
        echo -e "${GREEN}All stopped.${NC}"
        ;;
    restart)
        kill_all
        start
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
