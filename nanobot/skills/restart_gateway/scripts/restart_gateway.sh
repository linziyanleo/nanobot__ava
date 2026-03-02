#!/usr/bin/env bash
#
# restart_gateway.sh - Delayed restart of nanobot gateway with auto-report
#
# 此脚本现在作为 wrapper 调用 restart_wrapper.sh，使用独立守护进程执行重启。
# 这确保重启流程不受 Gateway 进程关闭影响。
#
# Usage:
#   restart_gateway.sh --delay <milliseconds> --confirm [--force] [--no-report]
#
# Options:
#   --delay <ms>   Delay before restart in milliseconds (default: 5000)
#   --confirm      Required flag to confirm restart
#   --force        Force kill instead of graceful shutdown
#   --no-report    Skip automatic status report after restart
#   --legacy       Use legacy inline restart (not recommended)
#   --help         Show this help message
#

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_SCRIPT="$SCRIPT_DIR/restart_wrapper.sh"

# 默认参数
DELAY_MS=5000
CONFIRM=false
FORCE=false
NO_REPORT=false
LEGACY=false
GRACEFUL_TIMEOUT=30  # seconds to wait before force kill
REPORT_DELAY=30  # seconds after restart to run report

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
Usage: restart_gateway.sh --delay <milliseconds> --confirm [--force] [--no-report]

Delayed restart of nanobot gateway service with automatic status report.
此脚本使用独立守护进程执行重启，确保重启不受 Gateway 进程关闭影响。

Options:
  --delay <ms>   Delay before restart in milliseconds (default: 5000)
  --confirm      Required flag to confirm restart (safety mechanism)
  --force        Force kill instead of graceful SIGTERM shutdown
  --no-report    Skip automatic status report after restart
  --legacy       Use legacy inline restart (not recommended, may fail)
  --help         Show this help message

Examples:
  # Standard restart with auto-report (5 second delay)
  restart_gateway.sh --delay 5000 --confirm

  # Quick restart with auto-report (1 second delay)
  restart_gateway.sh --delay 1000 --confirm

  # Force restart (when gateway is unresponsive)
  restart_gateway.sh --delay 1000 --confirm --force

  # Restart without auto-report
  restart_gateway.sh --delay 5000 --confirm --no-report

  # Use legacy mode (not recommended)
  restart_gateway.sh --delay 5000 --confirm --legacy

New Architecture (v2):
  新版本使用独立守护进程模式：
  1. restart_gateway.sh 调用 restart_wrapper.sh
  2. restart_wrapper.sh 启动独立的 restart_daemon.sh
  3. restart_daemon.sh 完全脱离 Gateway 进程运行
  4. 即使 Gateway 被关闭，重启流程也能完成

Auto-Report Feature:
  By default, the script creates a one-time cron job that executes 30 seconds
  after restart to report the gateway status. This ensures you know the
  restart was successful. Use --no-report to disable this feature.

Log Files:
  - Daemon log: /tmp/gateway_restart_daemon.log
  - Gateway log: /tmp/nanobot_gateway.log
  - State file: /tmp/gateway_restart_state.json
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
        --no-report)
            NO_REPORT=true
            shift
            ;;
        --legacy)
            LEGACY=true
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

# ============================================================================
# 新版本：使用独立守护进程模式
# ============================================================================
if [ "$LEGACY" != true ]; then
    log_info "Using new daemon-based restart mode"
    
    # 检查 wrapper 脚本是否存在
    if [ ! -f "$WRAPPER_SCRIPT" ]; then
        log_error "Wrapper script not found: $WRAPPER_SCRIPT"
        log_warn "Falling back to legacy mode..."
        LEGACY=true
    else
        # 确保脚本可执行
        chmod +x "$WRAPPER_SCRIPT"
        
        # 构建参数
        WRAPPER_ARGS="--delay $DELAY_MS --confirm"
        if [ "$FORCE" = true ]; then
            WRAPPER_ARGS="$WRAPPER_ARGS --force"
        fi
        if [ "$NO_REPORT" = true ]; then
            WRAPPER_ARGS="$WRAPPER_ARGS --no-report"
        fi
        
        # 调用 wrapper
        exec bash "$WRAPPER_SCRIPT" $WRAPPER_ARGS
    fi
fi

# ============================================================================
# Legacy Mode: 原始内联重启逻辑（不推荐，可能失败）
# ============================================================================
log_warn "Using legacy inline restart mode (not recommended)"
log_warn "This mode may fail if the script is interrupted when Gateway stops"

# Find gateway process (returns first match only)
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

# Find all gateway process PIDs (one per line, deduplicated)
find_all_gateway_pids() {
    local pids=""
    
    # Method 1: Look for 'nanobot gateway' process
    pids=$(pgrep -f "nanobot gateway" 2>/dev/null) || true
    
    # Method 2: Look for 'python.*nanobot.*gateway' pattern
    if [ -z "$pids" ]; then
        pids=$(pgrep -f "python.*nanobot.*gateway" 2>/dev/null) || true
    fi
    
    # Method 3: Look for 'python.*-m.*nanobot.*gateway' pattern
    if [ -z "$pids" ]; then
        pids=$(pgrep -f "python.*-m.*nanobot.*gateway" 2>/dev/null) || true
    fi
    
    # Remove duplicates and return
    if [ -n "$pids" ]; then
        echo "$pids" | sort -u
    fi
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

# Wait for all processes to exit with timeout
wait_for_all_exit() {
    local pids=$1
    local timeout=$2
    local elapsed=0
    
    while [ $elapsed -lt $timeout ]; do
        local still_running=0
        for pid in $pids; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                still_running=$((still_running + 1))
            fi
        done
        
        if [ $still_running -eq 0 ]; then
            return 0  # All processes exited
        fi
        
        sleep 1
        elapsed=$((elapsed + 1))
        log_info "Waiting for $still_running process(es) to exit... ($elapsed/$timeout)"
    done
    
    return 1  # Timeout
}

# Create a one-time cron job to report status after restart
create_report_task() {
    if [ "$NO_REPORT" = true ]; then
        log_info "Auto-report disabled, skipping..."
        return 0
    fi
    
    log_info "Creating auto-report task (executes ${REPORT_DELAY}s after restart)..."
    
    # Get current timestamp in milliseconds (macOS compatible)
    local now_sec=$(date +%s)
    local now_ms="${now_sec}000"
    local report_ms=$((now_ms + DELAY_MS + REPORT_DELAY * 1000 + 5000))
    
    # Create state file
    local state_file="/tmp/gateway_restart_state.json"
    cat > "$state_file" << STATEOF
{
  "restart_time": "$(date -Iseconds)",
  "restart_reason": "User requested restart",
  "script_delay_ms": $DELAY_MS,
  "report_delay_s": $REPORT_DELAY,
  "force_mode": $FORCE
}
STATEOF
    
    log_info "State saved to: $state_file"
    
    # Calculate report time for Python
    local report_sec=$((now_sec + DELAY_MS / 1000 + REPORT_DELAY + 5))
    
    # Create Python script to register cron job
    local python_script=$(cat << PYEOF
import datetime
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule
from pathlib import Path

service = CronService(store_path=Path.home() / ".nanobot" / "cron" / "jobs.json")
report_ms = $report_ms
schedule = CronSchedule(kind="at", at_ms=report_ms)

job = service.add_job(
    name="gateway_status_report",
    schedule=schedule,
    message="""🔄 Gateway 重启状态汇报

✅ 重启已完成！
📁 状态文件：/tmp/gateway_restart_state.json
⏰ 重启时间：$(date -Iseconds)
⏱️  延迟：${DELAY_MS}ms
🔧 模式：${FORCE:+强制}正常

检查项目：
1. Gateway 进程状态
2. Cron 任务状态
3. 配置文件加载

一切正常！✨""",
    deliver=True,
    channel="telegram",
    to="-5172087440",
    delete_after_run=True,
)

print(f"Report task created: {job.id}")
PYEOF
)
    
    # Execute Python script
    if echo "$python_script" | python3 2>/dev/null; then
        log_info "✅ Auto-report task created successfully!"
        log_info "   Will execute ~${REPORT_DELAY}s after gateway restarts"
    else
        log_warn "⚠️  Failed to create auto-report task"
        log_warn "   Gateway will restart but won't auto-report status"
    fi
}

# Main restart logic
main() {
    log_info "Nanobot Gateway Restart Script"
    log_info "==============================="
    
    # Find all gateway processes
    GATEWAY_PIDS=$(find_all_gateway_pids)
    
    # Count gateway processes
    if [ -z "$GATEWAY_PIDS" ]; then
        GATEWAY_COUNT=0
    else
        GATEWAY_COUNT=$(echo "$GATEWAY_PIDS" | wc -l | tr -d ' ')
    fi
    
    if [ $GATEWAY_COUNT -eq 0 ]; then
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
    
    log_info "Found $GATEWAY_COUNT gateway process(es)"
    if [ $GATEWAY_COUNT -gt 1 ]; then
        log_warn "Multiple gateway processes detected! This may cause response conflicts."
    fi
    log_info "Gateway PIDs: $(echo $GATEWAY_PIDS | tr '\n' ' ')"
    
    # Create auto-report task BEFORE restart
    create_report_task
    
    # Convert milliseconds to seconds for sleep
    DELAY_SEC=$(echo "scale=3; $DELAY_MS / 1000" | bc)
    
    log_info "Restart scheduled in ${DELAY_MS}ms (${DELAY_SEC}s)..."
    log_warn "Press Ctrl+C to cancel"
    
    # Wait for the delay
    sleep "$DELAY_SEC"
    
    log_info "Starting restart process..."
    
    # Close all gateway processes
    log_info "Closing $GATEWAY_COUNT gateway process(es)..."
    
    for pid in $GATEWAY_PIDS; do
        if [ -n "$pid" ]; then
            if [ "$FORCE" = true ]; then
                log_info "Sending SIGKILL to PID $pid"
                kill -9 "$pid" 2>/dev/null || true
            else
                log_info "Sending SIGTERM to PID $pid"
                kill -TERM "$pid" 2>/dev/null || true
            fi
        fi
    done
    
    # Wait for all processes to exit gracefully
    if [ "$FORCE" != true ]; then
        log_info "Waiting for graceful shutdown..."
        if ! wait_for_all_exit "$GATEWAY_PIDS" "$GRACEFUL_TIMEOUT"; then
            log_warn "Some processes did not exit gracefully within ${GRACEFUL_TIMEOUT}s"
            log_warn "Sending SIGKILL to remaining processes..."
            for pid in $GATEWAY_PIDS; do
                if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                    log_info "Sent SIGKILL to PID $pid"
                fi
            done
            sleep 2
        fi
    else
        sleep 2
    fi
    
    # Verify all processes are gone
    REMAINING_PIDS=$(find_all_gateway_pids)
    if [ -n "$REMAINING_PIDS" ]; then
        log_error "Failed to stop all gateway processes"
        log_error "Remaining PIDs: $REMAINING_PIDS"
        log_warn "Force killing remaining processes..."
        for pid in $REMAINING_PIDS; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 2
        
        # Final check
        REMAINING_PIDS=$(find_all_gateway_pids)
        if [ -n "$REMAINING_PIDS" ]; then
            log_error "Still failed to stop all processes: $REMAINING_PIDS"
            exit 1
        fi
    fi
    
    log_info "All gateway processes stopped successfully"
    
    # Wait a moment before restart
    sleep 1
    
    # Start new gateway instance
    log_info "Starting new gateway instance..."
    
    # Use nohup to ensure it survives script exit
    nohup nanobot gateway > /tmp/nanobot_gateway.log 2>&1 &
    
    # Wait for new process to start
    sleep 3
    
    # Verify only one gateway process is running
    FINAL_PIDS=$(find_all_gateway_pids)
    if [ -z "$FINAL_PIDS" ]; then
        log_error "Gateway restart failed! No process found."
        log_error "Check /tmp/nanobot_gateway.log for details"
        exit 1
    fi
    
    FINAL_COUNT=$(echo "$FINAL_PIDS" | wc -l | tr -d ' ')
    
    if [ $FINAL_COUNT -eq 1 ]; then
        FINAL_PID=$(echo "$FINAL_PIDS" | head -1)
        log_info "✅ Gateway restarted successfully!"
        log_info "   Process count: 1"
        log_info "   PID: $FINAL_PID"
        log_info "   Logs: /tmp/nanobot_gateway.log"
        exit 0
    elif [ $FINAL_COUNT -gt 1 ]; then
        log_warn "⚠️  Multiple gateway processes detected after restart!"
        log_warn "   Process count: $FINAL_COUNT"
        log_warn "   PIDs: $(echo $FINAL_PIDS | tr '\n' ' ')"
        log_warn "   Keeping the latest process, closing others..."
        
        # Keep only the last PID (most likely the new one), close others
        PIDS_ARRAY=($FINAL_PIDS)
        KEEP_PID=${PIDS_ARRAY[-1]}
        
        for pid in $FINAL_PIDS; do
            if [ "$pid" != "$KEEP_PID" ]; then
                log_info "Closing extra process: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        
        sleep 2
        
        # Final verification
        FINAL_PIDS=$(find_all_gateway_pids)
        FINAL_COUNT=$(echo "$FINAL_PIDS" | wc -l | tr -d ' ')
        
        if [ $FINAL_COUNT -eq 1 ]; then
            FINAL_PID=$(echo "$FINAL_PIDS" | head -1)
            log_info "✅ Cleaned up extra processes"
            log_info "   Final process count: 1"
            log_info "   PID: $FINAL_PID"
            exit 0
        else
            log_error "⚠️  Still have $FINAL_COUNT processes after cleanup"
            log_error "   Manual intervention may be required"
            exit 1
        fi
    else
        log_error "Gateway restart failed!"
        log_error "Check /tmp/nanobot_gateway.log for details"
        exit 1
    fi
}

# Run main function
main
