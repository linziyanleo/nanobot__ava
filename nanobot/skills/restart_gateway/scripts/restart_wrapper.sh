#!/usr/bin/env bash
#
# restart_wrapper.sh - Gateway 重启包装脚本
#
# 此脚本用于快速启动独立的守护进程执行重启，然后立即返回。
# Agent 调用此脚本后可以立即得到响应，而实际的重启流程由
# 独立的守护进程完成，不受 Gateway 关闭影响。
#
# Usage:
#   restart_wrapper.sh --delay <ms> --confirm [--force] [--no-report]
#
# Options:
#   --delay <ms>    延迟重启时间（毫秒），默认 5000
#   --confirm       确认标志（安全机制）
#   --force         强制重启（跳过优雅关闭）
#   --no-report     禁用自动汇报
#

set -euo pipefail

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_SCRIPT="$SCRIPT_DIR/restart_daemon.sh"

# 默认参数
DELAY_MS=5000
CONFIRM=false
FORCE=false
NO_REPORT=false

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 参数解析
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
        --help)
            cat << EOF
Usage: restart_wrapper.sh --delay <ms> --confirm [--force] [--no-report]

快速启动 Gateway 重启流程，立即返回。

Options:
  --delay <ms>    延迟重启时间（毫秒），默认 5000
  --confirm       确认标志（安全机制，必须提供）
  --force         强制重启（跳过优雅关闭）
  --no-report     禁用自动汇报

Examples:
  # 标准重启（5秒延迟，自动汇报）
  restart_wrapper.sh --delay 5000 --confirm

  # 快速重启（1秒延迟）
  restart_wrapper.sh --delay 1000 --confirm

  # 强制重启
  restart_wrapper.sh --delay 1000 --confirm --force

  # 禁用自动汇报
  restart_wrapper.sh --delay 5000 --confirm --no-report

流程说明:
  1. 此脚本启动独立的守护进程执行重启
  2. 守护进程完全脱离当前 Gateway 进程
  3. 即使 Gateway 被关闭，重启流程也能完成
  4. 守护进程日志: /tmp/gateway_restart_daemon.log
EOF
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            log_warn "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 验证确认标志
if [ "$CONFIRM" != true ]; then
    log_error "需要确认标志。请添加 --confirm 参数。"
    log_warn "这是防止意外重启的安全机制。"
    exit 1
fi

# 验证延迟参数
if ! [[ "$DELAY_MS" =~ ^[0-9]+$ ]]; then
    log_error "无效的延迟值: $DELAY_MS（必须是正整数）"
    exit 1
fi

# 验证守护脚本存在
if [ ! -f "$DAEMON_SCRIPT" ]; then
    log_error "守护脚本不存在: $DAEMON_SCRIPT"
    exit 1
fi

# 确保守护脚本可执行
chmod +x "$DAEMON_SCRIPT"

# 构建守护进程参数
DAEMON_ARGS="--delay $DELAY_MS"
if [ "$FORCE" = true ]; then
    DAEMON_ARGS="$DAEMON_ARGS --force"
fi
if [ "$NO_REPORT" = true ]; then
    DAEMON_ARGS="$DAEMON_ARGS --no-report"
fi

# 启动独立守护进程
# - nohup: 忽略 SIGHUP 信号
# - setsid: 创建新的会话，完全脱离当前进程组
# - </dev/null: 断开标准输入
# - >/dev/null 2>&1: 重定向输出到 null（守护脚本有自己的日志）
log_info "正在启动重启守护进程..."

nohup setsid bash "$DAEMON_SCRIPT" $DAEMON_ARGS </dev/null >/dev/null 2>&1 &
DAEMON_PID=$!

# 等待一小会确保守护进程启动
sleep 0.5

# 检查守护进程是否启动成功
# 注意：由于 setsid，我们无法直接跟踪子进程，这里只是做基本检查
if pgrep -f "restart_daemon.sh" >/dev/null 2>&1; then
    log_info "================================================"
    log_info "✅ 重启已安排！"
    log_info "================================================"
    log_info "📅 延迟: ${DELAY_MS}ms"
    log_info "🔧 模式: $( [ "$FORCE" = true ] && echo "强制" || echo "正常" )"
    log_info "📢 汇报: $( [ "$NO_REPORT" = true ] && echo "禁用" || echo "启用" )"
    log_info "📄 守护进程日志: /tmp/gateway_restart_daemon.log"
    log_info ""
    log_info "重启流程将在后台独立运行，不受当前会话影响。"
    log_info "您可以安全地关闭此终端。"
    log_info "================================================"
    exit 0
else
    log_error "守护进程启动失败"
    log_warn "请检查日志: /tmp/gateway_restart_daemon.log"
    exit 1
fi
