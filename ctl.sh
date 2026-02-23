#!/usr/bin/env bash
#
# ctl.sh — SenseBase API server control script
#
# Usage:
#   ./ctl.sh start          Start the API server in the background
#   ./ctl.sh stop           Stop the API server
#   ./ctl.sh restart        Restart the API server
#   ./ctl.sh status         Show server status
#   ./ctl.sh logs           Tail the server log file
#   ./ctl.sh crawl [--llm]  Trigger a crawl via the API
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.sensebase.pid"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/sensebase.log"

# Configurable via env vars
SB_HOST="${SB_HOST:-0.0.0.0}"
SB_PORT="${SB_PORT:-12500}"

# ── Helpers ──────────────────────────────────────────────────────────

_activate_venv() {
    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        if [[ -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.venv/bin/activate"
        else
            echo "Warning: No virtualenv found at .venv/ and none active." >&2
        fi
    fi
}

_is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(<"$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        # Stale PID file
        rm -f "$PID_FILE"
    fi
    return 1
}

_read_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE"
    fi
}

# ── Subcommands ──────────────────────────────────────────────────────

cmd_start() {
    if _is_running; then
        echo "Server is already running (PID $(_read_pid))."
        exit 1
    fi

    _activate_venv

    mkdir -p "$LOG_DIR"

    echo "Starting SenseBase API on ${SB_HOST}:${SB_PORT}..."
    nohup sb-api --host "$SB_HOST" --port "$SB_PORT" >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Brief wait to verify the process didn't die immediately
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo "Server started (PID $pid). Logs: $LOG_FILE"
    else
        rm -f "$PID_FILE"
        echo "Server failed to start. Check logs: $LOG_FILE" >&2
        exit 1
    fi
}

cmd_stop() {
    if ! _is_running; then
        echo "Server is not running."
        exit 0
    fi

    local pid
    pid=$(_read_pid)
    echo "Stopping server (PID $pid)..."

    kill "$pid" 2>/dev/null || true

    # Wait up to 5 seconds for graceful shutdown
    local waited=0
    while kill -0 "$pid" 2>/dev/null && (( waited < 5 )); do
        sleep 1
        (( waited++ ))
    done

    # Force kill if still alive
    if kill -0 "$pid" 2>/dev/null; then
        echo "Sending SIGKILL..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "Server stopped."
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    if _is_running; then
        local pid
        pid=$(_read_pid)
        echo "Server is running (PID $pid)."

        # Try to hit the health endpoint
        local url="http://127.0.0.1:${SB_PORT}/health"
        if command -v curl &>/dev/null; then
            echo -n "Health check: "
            if curl -sf --max-time 3 "$url"; then
                echo ""
            else
                echo "FAILED (server may still be starting)"
            fi
        fi
    else
        echo "Server is not running."
        exit 1
    fi
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "No log file found at $LOG_FILE"
        exit 1
    fi
    tail -f "$LOG_FILE"
}

cmd_crawl() {
    local use_llm="false"
    for arg in "$@"; do
        case "$arg" in
            --llm) use_llm="true" ;;
            *) echo "Unknown crawl option: $arg" >&2; exit 1 ;;
        esac
    done

    local url="http://127.0.0.1:${SB_PORT}/crawl/start"
    echo "Triggering crawl (llm=$use_llm)..."

    if ! command -v curl &>/dev/null; then
        echo "Error: curl is required for the crawl command." >&2
        exit 1
    fi

    local response
    response=$(curl -sf --max-time 10 \
        -X POST "$url" \
        -H "Content-Type: application/json" \
        -d "{\"use_llm\": $use_llm}" 2>&1) || {
        echo "Failed to reach server at $url" >&2
        echo "Is the server running? Try: ./ctl.sh status" >&2
        exit 1
    }

    echo "$response"
}

cmd_help() {
    echo "Usage: $0 {start|stop|restart|status|logs|crawl [--llm]}"
    echo ""
    echo "Commands:"
    echo "  start          Start the API server in the background"
    echo "  stop           Stop the API server"
    echo "  restart        Restart the API server"
    echo "  status         Show if server is running and hit /health"
    echo "  logs           Tail the server log file"
    echo "  crawl [--llm]  Trigger a crawl run via the API"
    echo ""
    echo "Environment variables:"
    echo "  SB_HOST        Host to bind (default: 0.0.0.0)"
    echo "  SB_PORT        Port to bind (default: 8000)"
}

# ── Main ─────────────────────────────────────────────────────────────

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    crawl)   shift; cmd_crawl "$@" ;;
    help|-h|--help) cmd_help ;;
    *)
        cmd_help >&2
        exit 1
        ;;
esac
