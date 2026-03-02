#!/usr/bin/env bash
#
# restart_gateway.sh - Delayed restart of nanobot gateway
#
# Usage:
#   restart_gateway.sh --delay <milliseconds> --confirm [--force]
#
# Options:
#   --delay <ms>   Delay before restart in milliseconds (default: 5000)
#   --confirm      Required flag to confirm restart
#   --force        Force kill instead of graceful shutdown
#   --help         Show this help message
#

set -euo pipefail

# Default values
DELAY_MS=5000
CONFIRM=false
FORCE=false
GRACEFUL_TIMEOUT=30  # seconds to wait before force kill

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    cat << EOF
Usage: restart_gateway.sh --delay <milliseconds> --confirm [--force]

Delayed restart of nanobot gateway service.

Options:
  --delay <ms>   Delay before restart in milliseconds (default: 5000)
  --confirm      Required flag to confirm restart (safety mechanism)
  --force        Force kill instead of graceful SIGTERM shutdown
  --help         Show this help message

Examples:
  # Standard restart with 5 second delay
  restart_gateway.sh --delay 5000 --confirm

  # Quick restart with 1 second delay
  restart_gateway.sh --delay 1000 --confirm

  # Force restart (when gateway is unresponsive)
  restart_gateway.sh --delay 1000 --confirm --force

Safety:
  The --confirm flag is required to prevent accidental restarts.
  Without it, the script will exit with an error.
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --delay)
            DELAY_MS="$2"
            shift 2
            ;;
        --confirm)
            CONFIRM=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate confirmation
if [ "$CONFIRM" != true ]; then
    log_error "Confirmation required. Add --confirm flag to proceed."
    log_warn "This is a safety mechanism to prevent accidental restarts."
    exit 1
fi

# Validate delay
if ! [[ "$DELAY_MS" =~ ^[0-9]+$ ]]; then
    log_error "Invalid delay value: $DELAY_MS (must be a positive integer)"
    exit 1
fi

# Find gateway process
find_gateway_pid() {
    # Try multiple methods to find the gateway process
    local pid=""
    
    # Method 1: Look for 'nanobot gateway' process
    pid=$(pgrep -f "nanobot gateway" 2>/dev/null | head -1) || true
    
    # Method 2: Look for 'python.*nanobot.*gateway' pattern
    if [ -z "$pid" ]; then
        pid=$(pgrep -f "python.*nanobot.*gateway" 2>/dev/null | head -1) || true
    fi
    
    # Method 3: Look for the main nanobot process
    if [ -z "$pid" ]; then
        pid=$(pgrep -f "python.*-m.*nanobot.*gateway" 2>/dev/null | head -1) || true
    fi
    
    echo "$pid"
}

# Wait for process to exit with timeout
wait_for_exit() {
    local pid=$1
    local timeout=$2
    local elapsed=0
    
    while kill -0 "$pid" 2>/dev/null && [ $elapsed -lt $timeout ]; do
        sleep 1
        elapsed=$((elapsed + 1))
        log_info "Waiting for gateway to exit... ($elapsed/$timeout)"
    done
    
    if kill -0 "$pid" 2>/dev/null; then
        return 1  # Process still running
    fi
    return 0  # Process exited
}

# Main restart logic
main() {
    log_info "Nanobot Gateway Restart Script"
    log_info "==============================="
    
    # Find the gateway process
    GATEWAY_PID=$(find_gateway_pid)
    
    if [ -z "$GATEWAY_PID" ]; then
        log_warn "Gateway process not found. It may not be running."
        log_info "Attempting to start gateway..."
        
        # Try to start gateway in background
        nohup nanobot gateway > /tmp/nanobot_gateway.log 2>&1 &
        sleep 2
        
        NEW_PID=$(find_gateway_pid)
        if [ -n "$NEW_PID" ]; then
            log_info "Gateway started successfully (PID: $NEW_PID)"
            exit 0
        else
            log_error "Failed to start gateway. Check /tmp/nanobot_gateway.log for details."
            exit 1
        fi
    fi
    
    log_info "Found gateway process (PID: $GATEWAY_PID)"
    
    # Convert milliseconds to seconds for sleep
    DELAY_SEC=$(echo "scale=3; $DELAY_MS / 1000" | bc)
    
    log_info "Restart scheduled in ${DELAY_MS}ms (${DELAY_SEC}s)..."
    log_warn "Press Ctrl+C to cancel"
    
    # Wait for the delay
    sleep "$DELAY_SEC"
    
    log_info "Starting restart process..."
    
    if [ "$FORCE" = true ]; then
        log_warn "Force mode enabled - sending SIGKILL"
        kill -9 "$GATEWAY_PID" 2>/dev/null || true
    else
        # Graceful shutdown with SIGTERM
        log_info "Sending SIGTERM for graceful shutdown..."
        kill -TERM "$GATEWAY_PID" 2>/dev/null || true
        
        # Wait for graceful exit
        if ! wait_for_exit "$GATEWAY_PID" "$GRACEFUL_TIMEOUT"; then
            log_warn "Gateway did not exit gracefully within ${GRACEFUL_TIMEOUT}s"
            log_warn "Sending SIGKILL..."
            kill -9 "$GATEWAY_PID" 2>/dev/null || true
            sleep 1
        fi
    fi
    
    # Verify process is gone
    if kill -0 "$GATEWAY_PID" 2>/dev/null; then
        log_error "Failed to stop gateway process"
        exit 1
    fi
    
    log_info "Gateway stopped successfully"
    
    # Wait a moment before restart
    sleep 1
    
    # Start new gateway instance
    log_info "Starting new gateway instance..."
    
    # Use nohup to ensure it survives script exit
    nohup nanobot gateway > /tmp/nanobot_gateway.log 2>&1 &
    
    # Wait and verify startup
    sleep 3
    
    NEW_PID=$(find_gateway_pid)
    if [ -n "$NEW_PID" ]; then
        log_info "Gateway restarted successfully!"
        log_info "New PID: $NEW_PID"
        log_info "Logs: /tmp/nanobot_gateway.log"
        exit 0
    else
        log_error "Gateway restart failed!"
        log_error "Check /tmp/nanobot_gateway.log for details"
        exit 1
    fi
}

# Run main function
main
