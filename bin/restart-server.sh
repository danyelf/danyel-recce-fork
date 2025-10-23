#!/bin/bash
# ABOUTME: Restart recce server with optional debug event logging
# ABOUTME: Kills any existing recce processes and starts a fresh server instance

set -e

# Configuration
PROJECT_ROOT="/Users/danyel/code/danyel-recce-fork"
JAFFLE_SHOP="/Users/danyel/code/jaffle_shop_duckdb"
VENV_PATH="$PROJECT_ROOT/venv"

# Parse arguments
DEBUG_EVENTS="${1:-false}"
LOG_FILE="${2:-}"
WATCH_MODE="${3:-false}"

# Show usage
show_usage() {
    cat <<EOF
Usage: $0 [DEBUG_EVENTS] [LOG_FILE] [WATCH]

Modes:
  $0                          # Start server silently
  $0 true /tmp/log.log        # Start with debug logging to file
  $0 true /tmp/log.log watch  # Start with debug logging and watch output
  $0 false "" watch           # Start silently, watch output with tail -f

With WATCH mode, output scrolls in real-time so you can monitor the server.
Press Ctrl+C to stop watching (server continues running).

EOF
}

# Kill any existing recce processes
echo "Killing existing recce server processes..."
pkill -9 -f "recce server" || true
sleep 1

# Start the server
echo "Starting recce server..."
cd "$JAFFLE_SHOP"
source "$VENV_PATH/bin/activate"

if [ "$DEBUG_EVENTS" = "true" ]; then
    if [ -z "$LOG_FILE" ]; then
        echo "ERROR: DEBUG_EVENTS=true requires LOG_FILE argument"
        show_usage
        exit 1
    fi
    echo "Starting with RECCE_DEBUG_EVENTS=true, logging to $LOG_FILE"
    RECCE_DEBUG_EVENTS=true recce server > "$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    sleep 3
    echo "✓ Server started (PID: $SERVER_PID)"

    if [ "$WATCH_MODE" = "watch" ]; then
        echo "Watching output... (Press Ctrl+C to stop watching, server keeps running)"
        tail -f "$LOG_FILE"
    fi
else
    if [ "$WATCH_MODE" = "watch" ]; then
        echo "Starting server with live output..."
        recce server &
        SERVER_PID=$!
        sleep 3
        echo "✓ Server started (PID: $SERVER_PID)"
        echo "Output will appear below. Press Ctrl+C to stop watching."
        wait $SERVER_PID 2>/dev/null || true
    else
        echo "Starting server without debug event logging"
        recce server > /dev/null 2>&1 &
        SERVER_PID=$!
        sleep 3
        echo "✓ Server started (PID: $SERVER_PID)"
    fi
fi
