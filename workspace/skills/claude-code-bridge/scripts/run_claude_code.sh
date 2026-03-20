#!/bin/bash
#
# Claude Code 后台执行脚本
# 用法: run_claude_code.sh <task_id> <project_path> <prompt_file> [max_turns] [allowed_tools] [model]
#
# 输出文件 (位于 /tmp/):
#   claude-code-{task_id}.json   — Claude Code 的 JSON 输出
#   claude-code-{task_id}.pid    — 后台进程 PID
#   claude-code-{task_id}.status — 状态: running / done / error
#   claude-code-{task_id}.log    — 执行日志（stderr）

set -uo pipefail

TASK_ID="${1:?用法: run_claude_code.sh <task_id> <project_path> <prompt_file> [max_turns] [allowed_tools] [model]}"
PROJECT_PATH="${2:?缺少 project_path}"
PROMPT_FILE="${3:?缺少 prompt_file}"
MAX_TURNS="${4:-15}"
ALLOWED_TOOLS="${5:-Read,Edit,Bash,Glob,Grep}"
MODEL="${6:-claude-sonnet-4-20250514}"

PREFIX="/tmp/claude-code-${TASK_ID}"
RESULT_FILE="${PREFIX}.json"
PID_FILE="${PREFIX}.pid"
STATUS_FILE="${PREFIX}.status"
LOG_FILE="${PREFIX}.log"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "error" > "$STATUS_FILE"
    echo "{\"error\": \"Prompt file not found: ${PROMPT_FILE}\"}" > "$RESULT_FILE"
    exit 1
fi

if [ ! -d "$PROJECT_PATH" ]; then
    echo "error" > "$STATUS_FILE"
    echo "{\"error\": \"Project path not found: ${PROJECT_PATH}\"}" > "$RESULT_FILE"
    exit 1
fi

PROMPT=$(cat "$PROMPT_FILE")

echo "running" > "$STATUS_FILE"

(
    cd "$PROJECT_PATH"
    npx @anthropic-ai/claude-code \
        -p "$PROMPT" \
        --output-format json \
        --max-turns "$MAX_TURNS" \
        --model "$MODEL" \
        --allowedTools "$ALLOWED_TOOLS" \
        > "$RESULT_FILE" 2>"$LOG_FILE"

    if [ $? -eq 0 ]; then
        echo "done" > "$STATUS_FILE"
    else
        echo "error" > "$STATUS_FILE"
    fi
) &

BG_PID=$!
echo "$BG_PID" > "$PID_FILE"
echo "started task=${TASK_ID} pid=${BG_PID} project=${PROJECT_PATH}"
