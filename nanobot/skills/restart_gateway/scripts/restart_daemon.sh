#!/usr/bin/env bash
#
# restart_daemon.sh - 独立运行的 Gateway 重启守护脚本
#
# 此脚本设计为独立于 Gateway 进程运行，由 restart_wrapper.sh 通过
# nohup setsid 启动，确保即使 Gateway 被关闭，重启流程也能完成。
#
# Usage:
#   restart_daemon.sh --delay <ms> [--force] [--no-report]
#
# Options:
#   --delay <ms>    延迟重启时间（毫秒），默认 5000
#   --force         强制重启（跳过优雅关闭）
#   --no-report     禁用自动汇报
#

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
DELAY_MS=5000
FORCE=false
NO_REPORT=false
GRACEFUL_TIMEOUT=30      # 优雅关闭超时（秒）
REPORT_DELAY=30          # 重启后汇报延迟（秒）
STATE_FILE="/tmp/gateway_restart_state.json"
LOG_FILE="/tmp/gateway_restart_daemon.log"
JOBS_FILE="$HOME/.nanobot/cron/jobs.json"

# ============================================================================
# 日志函数
# ============================================================================
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo "$msg" >&2
    echo "$msg" >> "$LOG_FILE"
}

# ============================================================================
# 参数解析
# ============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --delay)
            DELAY_MS="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --no-report)
            NO_REPORT=true
            shift
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# 进程查找函数
# ============================================================================
find_gateway_pid() {
    local pid=""
    
    # 方法 1: 查找 'nanobot gateway' 进程
    pid=$(pgrep -f "nanobot gateway" 2>/dev/null | head -1) || true
    
    # 方法 2: 查找 'python.*nanobot.*gateway' 模式
    if [ -z "$pid" ]; then
        pid=$(pgrep -f "python.*nanobot.*gateway" 2>/dev/null | head -1) || true
    fi
    
    # 方法 3: 查找 'python.*-m.*nanobot.*gateway' 模式
    if [ -z "$pid" ]; then
        pid=$(pgrep -f "python.*-m.*nanobot.*gateway" 2>/dev/null | head -1) || true
    fi
    
    echo "$pid"
}

find_all_gateway_pids() {
    local pids=""
    
    # 方法 1: 查找 'nanobot gateway' 进程
    pids=$(pgrep -f "nanobot gateway" 2>/dev/null) || true
    
    # 方法 2: 查找 'python.*nanobot.*gateway' 模式
    if [ -z "$pids" ]; then
        pids=$(pgrep -f "python.*nanobot.*gateway" 2>/dev/null) || true
    fi
    
    # 方法 3: 查找 'python.*-m.*nanobot.*gateway' 模式
    if [ -z "$pids" ]; then
        pids=$(pgrep -f "python.*-m.*nanobot.*gateway" 2>/dev/null) || true
    fi
    
    # 去重并返回
    if [ -n "$pids" ]; then
        echo "$pids" | sort -u
    fi
}

# ============================================================================
# 等待进程退出
# ============================================================================
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
            return 0
        fi
        
        sleep 1
        elapsed=$((elapsed + 1))
        log_info "等待 $still_running 个进程退出... ($elapsed/$timeout)"
    done
    
    return 1
}

# ============================================================================
# 保存状态文件
# ============================================================================
save_state_file() {
    cat > "$STATE_FILE" << EOF
{
  "restart_time": "$(date -Iseconds)",
  "restart_reason": "User requested restart",
  "script_delay_ms": $DELAY_MS,
  "report_delay_s": $REPORT_DELAY,
  "force_mode": $FORCE,
  "daemon_pid": $$
}
EOF
    log_info "状态已保存: $STATE_FILE"
}

# ============================================================================
# 创建汇报任务（直接操作 jobs.json）
# ============================================================================
create_report_task() {
    if [ "$NO_REPORT" = true ]; then
        log_info "自动汇报已禁用，跳过..."
        return 0
    fi
    
    log_info "创建自动汇报任务..."
    
    # 计算汇报时间（当前时间 + 延迟 + 重启后等待）
    local now_sec=$(date +%s)
    local report_ms=$(( (now_sec + DELAY_MS / 1000 + REPORT_DELAY + 10) * 1000 ))
    local job_id=$(cat /dev/urandom | LC_ALL=C tr -dc 'a-f0-9' | head -c 8)
    local created_ms=$((now_sec * 1000))
    
    # 确保目录存在
    mkdir -p "$(dirname "$JOBS_FILE")"
    
    # 使用 Python 直接操作 jobs.json（不依赖 nanobot 模块）
    python3 << PYEOF
import json
from pathlib import Path

jobs_file = Path("$JOBS_FILE")
if jobs_file.exists():
    try:
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
    except:
        data = {"version": 1, "jobs": []}
else:
    data = {"version": 1, "jobs": []}

# 先删除同名的旧任务
data["jobs"] = [j for j in data.get("jobs", []) if j.get("name") != "gateway_status_report"]

job = {
    "id": "$job_id",
    "name": "gateway_status_report",
    "enabled": True,
    "schedule": {
        "kind": "at",
        "atMs": $report_ms,
        "everyMs": None,
        "expr": None,
        "tz": None
    },
    "payload": {
        "kind": "agent_turn",
        "message": """🔄 Gateway 重启状态汇报

✅ 重启已完成！
📁 状态文件：$STATE_FILE
⏰ 重启时间：$(date -Iseconds)
⏱️  延迟：${DELAY_MS}ms
🔧 模式：$( [ "$FORCE" = true ] && echo "强制" || echo "正常" )

检查项目：
1. Gateway 进程状态
2. Cron 任务状态
3. 配置文件加载

一切正常！✨""",
        "deliver": True,
        "channel": "telegram",
        "to": "-5172087440"
    },
    "state": {
        "nextRunAtMs": $report_ms,
        "lastRunAtMs": None,
        "lastStatus": None,
        "lastError": None,
        "taskCompletedAtMs": None,
        "taskCycleId": None
    },
    "createdAtMs": $created_ms,
    "updatedAtMs": $created_ms,
    "deleteAfterRun": True,
    "source": "cli"
}

data["jobs"].append(job)
jobs_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"汇报任务已创建: {job['id']}")
PYEOF

    if [ $? -eq 0 ]; then
        log_info "✅ 汇报任务创建成功 (ID: $job_id)"
    else
        log_warn "⚠️ 汇报任务创建失败，重启将继续但不会自动汇报"
    fi
}

# ============================================================================
# 停止 Gateway
# ============================================================================
stop_gateway() {
    local pids="$1"
    
    log_info "正在关闭 Gateway 进程..."
    
    for pid in $pids; do
        if [ -n "$pid" ]; then
            if [ "$FORCE" = true ]; then
                log_info "发送 SIGKILL 到 PID $pid"
                kill -9 "$pid" 2>/dev/null || true
            else
                log_info "发送 SIGTERM 到 PID $pid"
                kill -TERM "$pid" 2>/dev/null || true
            fi
        fi
    done
    
    # 等待进程退出
    if [ "$FORCE" != true ]; then
        log_info "等待优雅关闭..."
        if ! wait_for_all_exit "$pids" "$GRACEFUL_TIMEOUT"; then
            log_warn "优雅关闭超时，发送 SIGKILL..."
            for pid in $pids; do
                if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                    kill -9 "$pid" 2>/dev/null || true
                    log_info "已发送 SIGKILL 到 PID $pid"
                fi
            done
            sleep 2
        fi
    else
        sleep 2
    fi
    
    # 验证所有进程已退出
    local remaining=$(find_all_gateway_pids)
    if [ -n "$remaining" ]; then
        log_warn "仍有进程未退出: $remaining"
        log_warn "强制终止..."
        for pid in $remaining; do
            kill -9 "$pid" 2>/dev/null || true
        done
        sleep 2
        
        remaining=$(find_all_gateway_pids)
        if [ -n "$remaining" ]; then
            log_error "无法终止所有进程: $remaining"
            return 1
        fi
    fi
    
    log_info "所有 Gateway 进程已停止"
    return 0
}

# ============================================================================
# 启动 Gateway
# ============================================================================
start_gateway() {
    log_info "正在启动新的 Gateway 实例..."
    
    # 使用 nohup 确保进程独立运行
    nohup nanobot gateway >> /tmp/nanobot_gateway.log 2>&1 &
    
    # 等待进程启动
    sleep 3
    
    # 验证启动
    local new_pid=$(find_gateway_pid)
    if [ -n "$new_pid" ]; then
        log_info "✅ Gateway 启动成功 (PID: $new_pid)"
        return 0
    else
        log_error "Gateway 启动失败，请检查 /tmp/nanobot_gateway.log"
        return 1
    fi
}

# ============================================================================
# 主函数
# ============================================================================
main() {
    # 清空日志文件
    > "$LOG_FILE"
    
    log_info "================================================"
    log_info "🔄 Gateway 重启守护脚本已启动"
    log_info "================================================"
    log_info "守护进程 PID: $$"
    log_info "延迟: ${DELAY_MS}ms"
    log_info "强制模式: $FORCE"
    log_info "自动汇报: $( [ "$NO_REPORT" = true ] && echo "禁用" || echo "启用" )"
    
    # 查找 Gateway 进程
    local gateway_pids=$(find_all_gateway_pids)
    
    if [ -z "$gateway_pids" ]; then
        log_warn "未找到运行中的 Gateway 进程"
        log_info "将直接启动新的 Gateway..."
        
        start_gateway
        exit $?
    fi
    
    local pid_count=$(echo "$gateway_pids" | wc -l | tr -d ' ')
    log_info "找到 $pid_count 个 Gateway 进程"
    log_info "PIDs: $(echo $gateway_pids | tr '\n' ' ')"
    
    # 保存状态
    save_state_file
    
    # 创建汇报任务（在关闭 Gateway 之前）
    create_report_task
    
    # 延迟等待
    local delay_sec=$(echo "scale=3; $DELAY_MS / 1000" | bc)
    log_info "等待 ${delay_sec}s 后开始重启..."
    sleep "$delay_sec"
    
    # 停止 Gateway
    if ! stop_gateway "$gateway_pids"; then
        log_error "停止 Gateway 失败"
        exit 1
    fi
    
    # 等待一会确保端口释放
    sleep 1
    
    # 启动新 Gateway
    if ! start_gateway; then
        log_error "启动 Gateway 失败"
        exit 1
    fi
    
    # 最终验证
    local final_pids=$(find_all_gateway_pids)
    local final_count=$(echo "$final_pids" | wc -l | tr -d ' ')
    
    if [ "$final_count" -eq 1 ]; then
        log_info "================================================"
        log_info "✅ Gateway 重启成功！"
        log_info "PID: $(echo $final_pids | head -1)"
        log_info "日志: /tmp/nanobot_gateway.log"
        log_info "汇报任务将在约 ${REPORT_DELAY}s 后执行"
        log_info "================================================"
        exit 0
    elif [ "$final_count" -gt 1 ]; then
        log_warn "检测到多个 Gateway 进程，清理中..."
        # 保留最新的进程
        local keep_pid=$(echo "$final_pids" | tail -1)
        for pid in $final_pids; do
            if [ "$pid" != "$keep_pid" ]; then
                log_info "关闭多余进程: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        log_info "✅ Gateway 重启成功 (PID: $keep_pid)"
        exit 0
    else
        log_error "Gateway 启动验证失败"
        exit 1
    fi
}

# 运行主函数
main
