#!/usr/bin/env bash
#
# gateway_watchdog.sh - Gateway 看门狗脚本
#
# 功能：
#   1. 检查 Gateway 进程是否存在，不存在则启动
#   2. 如果存在多个进程，清理到只剩 1 个
#
# 用法：
#   gateway_watchdog.sh [--silent]
#
# 建议通过 launchd 每 5 分钟执行一次
#

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
LOG_FILE="/tmp/gateway_watchdog.log"
SILENT=false
MAX_LOG_LINES=500

# 环境变量
export PATH="/Users/fanghu/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export HOME="${HOME:-/Users/$(whoami)}"
export NANOBOT_HOME="$HOME/.nanobot"

# ============================================================================
# 参数解析
# ============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --silent|-s)
            SILENT=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# ============================================================================
# 日志函数
# ============================================================================
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" >> "$LOG_FILE"
    if [ "$SILENT" = false ]; then
        echo "$msg"
    fi
}

# 限制日志文件大小
truncate_log() {
    if [ -f "$LOG_FILE" ]; then
        local lines=$(wc -l < "$LOG_FILE" | tr -d ' ')
        if [ "$lines" -gt "$MAX_LOG_LINES" ]; then
            tail -n "$MAX_LOG_LINES" "$LOG_FILE" > "$LOG_FILE.tmp"
            mv "$LOG_FILE.tmp" "$LOG_FILE"
        fi
    fi
}

# ============================================================================
# 进程查找函数
# ============================================================================
find_all_gateway_pids() {
    local all_pids=""
    
    # 方法1: PID 文件
    local pid_file="$HOME/.nanobot/gateway.pid"
    if [ -f "$pid_file" ]; then
        local file_pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$file_pid" ] && kill -0 "$file_pid" 2>/dev/null; then
            all_pids="$file_pid"
        fi
    fi
    
    # 方法2: ps + grep (always check to catch orphan processes)
    local ps_pids=$(ps aux | grep -E "python.*nanobot.*gateway" | grep -v "watchdog" | grep -v "restart_" | grep -v grep | awk '{print $2}') || true
    
    # Merge both sources and deduplicate
    if [ -n "$ps_pids" ]; then
        if [ -n "$all_pids" ]; then
            all_pids=$(printf "%s\n%s" "$all_pids" "$ps_pids" | sort -un)
        else
            all_pids=$(echo "$ps_pids" | sort -un)
        fi
    fi
    
    if [ -n "$all_pids" ]; then
        echo "$all_pids"
    fi
}

count_gateway_pids() {
    local pids=$(find_all_gateway_pids)
    if [ -z "$pids" ]; then
        echo 0
    else
        echo "$pids" | wc -l | tr -d ' '
    fi
}

# ============================================================================
# 启动 Gateway
# ============================================================================
start_gateway() {
    log "🚀 启动 Gateway..."
    
    # 激活虚拟环境（如果存在）
    local venv_activate=""
    for venv_path in \
        "$HOME/Desktop/Work/nanobot__ava/.venv/bin/activate" \
        "$HOME/.nanobot/.venv/bin/activate" \
        "/opt/nanobot/.venv/bin/activate"
    do
        if [ -f "$venv_path" ]; then
            venv_activate="$venv_path"
            break
        fi
    done
    
    if [ -n "$venv_activate" ]; then
        log "使用虚拟环境: $venv_activate"
        (
            source "$venv_activate"
            nohup nanobot gateway >> /tmp/nanobot_gateway.log 2>&1 &
        )
    else
        log "未找到虚拟环境，直接启动..."
        nohup nanobot gateway >> /tmp/nanobot_gateway.log 2>&1 &
    fi
    
    # 等待启动
    sleep 3
    
    # 验证
    local new_count=$(count_gateway_pids)
    if [ "$new_count" -ge 1 ]; then
        log "✅ Gateway 启动成功 (进程数: $new_count)"
        return 0
    else
        log "❌ Gateway 启动失败"
        return 1
    fi
}

# ============================================================================
# 清理多余进程
# ============================================================================
cleanup_extra_processes() {
    local pids=$(find_all_gateway_pids)
    local count=$(echo "$pids" | wc -l | tr -d ' ')
    
    if [ "$count" -le 1 ]; then
        return 0
    fi
    
    log "⚠️ 检测到 $count 个 Gateway 进程，清理中..."
    
    # 保留最新的进程（最后一个 PID 通常是最新的）
    local keep_pid=$(echo "$pids" | tail -1)
    log "保留进程: $keep_pid"
    
    for pid in $pids; do
        if [ "$pid" != "$keep_pid" ]; then
            log "终止多余进程: $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    # 等待进程退出
    sleep 2
    
    # 强制终止未退出的进程
    for pid in $pids; do
        if [ "$pid" != "$keep_pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "强制终止: $pid"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    local final_count=$(count_gateway_pids)
    log "清理完成，当前进程数: $final_count"
}

# ============================================================================
# 主函数
# ============================================================================
main() {
    truncate_log
    
    log "========== Gateway 看门狗检查 =========="
    
    local count=$(count_gateway_pids)
    log "当前 Gateway 进程数: $count"
    
    if [ "$count" -eq 0 ]; then
        log "⚠️ 未检测到 Gateway 进程"
        start_gateway
    elif [ "$count" -eq 1 ]; then
        local pid=$(find_all_gateway_pids | head -1)
        log "✅ Gateway 运行正常 (PID: $pid)"
    else
        log "⚠️ 检测到多个 Gateway 进程 ($count 个)"
        cleanup_extra_processes
    fi
    
    log "========================================="
}

# 运行主函数
main
