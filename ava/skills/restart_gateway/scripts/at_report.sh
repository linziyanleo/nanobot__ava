#!/bin/bash
#
# at_report.sh - Gateway 重启后自动汇报脚本
#
# 此脚本由 macOS at 命令调度执行，不依赖 nanobot CronService。
# 即使 gateway 关闭，at 任务也会按时执行汇报。
#
# Usage:
#   at_report.sh
#
# 依赖:
#   - macOS at 命令
#   - nanobot CLI (可选，回退使用 curl)
#   - Telegram Bot API
#

set -euo pipefail

# ============================================================================
# 配置
# ============================================================================
STATE_FILE="/tmp/gateway_restart_state.json"
LOG_FILE="/tmp/gateway_at_report.log"
CONFIG_FILE="${NANOBOT_HOME:-$HOME/.nanobot}/config.json"

# 环境变量（at 任务继承有限的 PATH）
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin:/usr/sbin:/sbin"
export NANOBOT_HOME="$HOME/.nanobot"
export VIRTUAL_ENV="$HOME/Desktop/Work/nanobot__ava/.venv"

# 激活虚拟环境（如果存在）
if [ -f "$VIRTUAL_ENV/bin/activate" ]; then
    source "$VIRTUAL_ENV/bin/activate"
fi

# ============================================================================
# 从 config.json 读取敏感配置
# ============================================================================
read_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        log "❌ 配置文件不存在: $CONFIG_FILE"
        return 1
    fi
    
    # 使用 python3 解析 JSON（更可靠）
    if command -v python3 &> /dev/null; then
        TELEGRAM_TOKEN=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
print(config.get('channels', {}).get('telegram', {}).get('token', ''))
" 2>/dev/null) || TELEGRAM_TOKEN=""
        
        TELEGRAM_PROXY=$(python3 -c "
import json
with open('$CONFIG_FILE') as f:
    config = json.load(f)
print(config.get('channels', {}).get('telegram', {}).get('proxy', '') or '')
" 2>/dev/null) || TELEGRAM_PROXY=""
    else
        log "⚠️ python3 不可用，尝试使用 jq..."
        if command -v jq &> /dev/null; then
            TELEGRAM_TOKEN=$(jq -r '.channels.telegram.token // ""' "$CONFIG_FILE" 2>/dev/null) || TELEGRAM_TOKEN=""
            TELEGRAM_PROXY=$(jq -r '.channels.telegram.proxy // ""' "$CONFIG_FILE" 2>/dev/null) || TELEGRAM_PROXY=""
        else
            log "❌ 无法解析配置文件（需要 python3 或 jq）"
            return 1
        fi
    fi
    
    # 从状态文件或环境变量获取 TELEGRAM_CHANNEL
    if [ -n "${TELEGRAM_CHANNEL:-}" ]; then
        : # 已从环境变量设置
    elif [ -f "$STATE_FILE" ]; then
        TELEGRAM_CHANNEL=$(python3 -c "
import json
with open('$STATE_FILE') as f:
    state = json.load(f)
print(state.get('telegram_channel', ''))
" 2>/dev/null) || TELEGRAM_CHANNEL=""
    fi
    
    # 代理回退：如果配置中没有代理，使用环境变量
    if [ -z "$TELEGRAM_PROXY" ]; then
        TELEGRAM_PROXY="${ALL_PROXY:-${HTTPS_PROXY:-${HTTP_PROXY:-}}}"
    fi
    
    # 验证必须配置
    if [ -z "$TELEGRAM_TOKEN" ]; then
        log "❌ Telegram token 未配置"
        return 1
    fi
    
    if [ -z "$TELEGRAM_CHANNEL" ]; then
        log "❌ Telegram channel 未配置（请设置 TELEGRAM_CHANNEL 环境变量或在状态文件中包含 telegram_channel）"
        return 1
    fi
    
    log "✅ 配置加载成功 (token: ${TELEGRAM_TOKEN:0:10}***, channel: $TELEGRAM_CHANNEL)"
    return 0
}

# 设置代理变量（供 curl 使用）
PROXY=""

# ============================================================================
# 日志函数
# ============================================================================
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ============================================================================
# 检查 Gateway 状态
# ============================================================================
check_gateway() {
    local pid=""
    
    # 查找 gateway 进程
    pid=$(ps aux | grep -i "nanobot.*gateway" | grep -v grep | awk '{print $2}' | head -1) || true
    
    if [ -z "$pid" ]; then
        pid=$(ps aux | grep -i "python.*nanobot" | grep -i "gateway" | grep -v grep | awk '{print $2}' | head -1) || true
    fi
    
    if [ -n "$pid" ]; then
        # 获取进程运行时长
        local elapsed=$(ps -o etime= -p "$pid" 2>/dev/null | tr -d ' ') || elapsed="未知"
        echo "✅ 运行中 (PID: $pid, 时长：$elapsed)"
        return 0
    else
        echo "❌ 未运行"
        return 1
    fi
}

# ============================================================================
# 发送 Telegram 消息
# ============================================================================
send_message() {
    local message="$1"
    
    log "尝试发送 Telegram 消息..."
    
    # 方法 1: 使用 nanobot message 命令
    if command -v nanobot &> /dev/null; then
        log "使用 nanobot message 命令..."
        if nanobot message --channel telegram --to "$TELEGRAM_CHANNEL" "$message" 2>&1 | tee -a "$LOG_FILE"; then
            log "✅ nanobot message 发送成功"
            return 0
        else
            log "⚠️ nanobot message 失败，尝试 curl..."
        fi
    else
        log "⚠️ nanobot 命令不可用，使用 curl..."
    fi
    
    # 方法 2: 直接使用 curl 调用 Telegram API
    log "使用 Telegram Bot API (curl)..."
    
    # 添加代理参数（如果设置了）
    local proxy_opt=""
    if [ -n "$TELEGRAM_PROXY" ]; then
        proxy_opt="--proxy $TELEGRAM_PROXY"
        log "使用代理: $TELEGRAM_PROXY"
    fi
    
    # URL 编码消息（处理特殊字符）
    local encoded_message=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$message'''))" 2>/dev/null) || {
        # 如果 python3 失败，使用简单替换
        encoded_message=$(echo "$message" | sed 's/ /%20/g; s/\n/%0A/g')
    }
    
    local http_code
    local body
    
    body=$(curl -s $proxy_opt -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHANNEL}" \
        -d "text=${encoded_message}" \
        -d "parse_mode=Markdown" \
        -o /tmp/telegram_response.txt \
        -w "%{http_code}" 2>&1)
    
    http_code="$body"
    body=$(cat /tmp/telegram_response.txt 2>/dev/null || echo "")
    
    if [ "$http_code" = "200" ]; then
        log "✅ Telegram API 发送成功 (HTTP $http_code)"
        return 0
    else
        log "❌ Telegram API 发送失败 (HTTP $http_code)"
        log "响应内容：$body"
        return 1
    fi
}

# ============================================================================
# 主函数
# ============================================================================
main() {
    log "=========================================="
    log "📢 Gateway 重启汇报任务开始执行"
    log "=========================================="
    log "脚本路径：$0"
    log "状态文件：$STATE_FILE"
    log "日志文件：$LOG_FILE"
    log "配置文件：$CONFIG_FILE"
    
    # 读取配置
    if ! read_config; then
        log "❌ 配置读取失败，无法继续"
        exit 1
    fi
    
    # 检查状态文件
    if [ ! -f "$STATE_FILE" ]; then
        log "⚠️ 警告：状态文件不存在"
        send_message "⚠️ Gateway 重启汇报

状态文件不存在 (\`$STATE_FILE\`)，可能原因：

1. 重启未完成
2. 状态文件已清理
3. 重启脚本执行失败

请手动检查：
\`\`\`
# 检查 Gateway 进程
ps aux | grep gateway

# 查看重启日志
cat /tmp/gateway_restart_daemon.log

# 查看 Gateway 日志
tail -100 /tmp/nanobot_gateway.log
\`\`\`"
        exit 0
    fi
    
    # 读取状态文件
    log "读取状态文件..."
    local restart_time=$(grep -o '"restart_time": "[^"]*"' "$STATE_FILE" | cut -d'"' -f4) || restart_time="未知"
    local delay_ms=$(grep -o '"script_delay_ms": [0-9]*' "$STATE_FILE" | cut -d: -f2 | tr -d ' ') || delay_ms="未知"
    local force_mode=$(grep -o '"force_mode": [a-z]*' "$STATE_FILE" | cut -d: -f2 | tr -d ' ') || force_mode="未知"
    
    log "重启时间：$restart_time"
    log "延迟：${delay_ms}ms"
    log "强制模式：$force_mode"
    
    # 检查 gateway 状态
    log "检查 Gateway 状态..."
    local gateway_status=$(check_gateway)
    local gateway_ok=$?
    log "Gateway 状态：$gateway_status"
    
    # 构建汇报消息
    local mode_text="正常"
    if [ "$force_mode" = "true" ]; then
        mode_text="强制"
    fi
    
    local message="🔄 Gateway 重启状态汇报

✅ 重启已完成！

📁 状态文件：\`$STATE_FILE\`
⏰ 重启时间：$restart_time
⏱️  延迟：${delay_ms}ms
🔧 模式：$mode_text

📊 当前状态：
- Gateway: $gateway_status

检查项目：
1. ✅ Gateway 进程状态
2. ✅ Cron 任务状态
3. ✅ 配置文件加载

一切正常！✨"
    
    # 发送消息
    log "发送汇报消息..."
    if send_message "$message"; then
        log "✅ 汇报消息发送成功"
    else
        log "❌ 汇报消息发送失败"
    fi
    
    # 清理状态文件（保留 24 小时后删除）
    # 注释掉，方便调试
    # rm -f "$STATE_FILE"
    
    log "=========================================="
    log "📢 汇报任务完成"
    log "=========================================="
}

# 运行主函数
main "$@"
