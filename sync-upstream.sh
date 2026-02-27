#!/bin/bash
set -euo pipefail

UPSTREAM_REMOTE="upstream"
UPSTREAM_BRANCH="main"
DEV_BRANCH="feat/0.0.1"
TEST_FILES=(
    "tests/test_context_prompt_cache.py"
    "tests/test_consolidate_offset.py"
    "tests/test_task_cancel.py"
    "tests/test_message_tool_suppress.py"
)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[1/5]${NC} 检查当前分支..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "$DEV_BRANCH" ]; then
    echo -e "${RED}✗ 当前在 $current_branch，请先切换到 $DEV_BRANCH${NC}"
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${RED}✗ 工作区有未提交变更，请先 commit 或 stash${NC}"
    git status --short
    exit 1
fi

echo -e "${YELLOW}[2/5]${NC} 拉取 upstream/$UPSTREAM_BRANCH..."
git fetch "$UPSTREAM_REMOTE" "$UPSTREAM_BRANCH"

behind=$(git rev-list --count HEAD.."$UPSTREAM_REMOTE/$UPSTREAM_BRANCH")
if [ "$behind" -eq 0 ]; then
    echo -e "${GREEN}✓ 已是最新，无需合并${NC}"
    git rev-list --left-right --count HEAD..."$UPSTREAM_REMOTE/$UPSTREAM_BRANCH" | awk '{printf "本地领先: %s 提交\n", $1}'
    exit 0
fi
echo "  落后上游 $behind 个提交"

echo -e "${YELLOW}[3/5]${NC} 合并 upstream/$UPSTREAM_BRANCH..."
if git merge "$UPSTREAM_REMOTE/$UPSTREAM_BRANCH" --no-edit 2>&1; then
    echo -e "${GREEN}✓ 合并成功（无冲突）${NC}"
else
    echo ""
    echo -e "${RED}✗ 合并产生冲突，请手动解决以下文件：${NC}"
    echo ""
    git diff --name-only --diff-filter=U
    echo ""
    echo -e "${YELLOW}解决步骤：${NC}"
    echo "  1. 编辑上面列出的文件，解决冲突标记 (<<<<<<< / >>>>>>> )"
    echo "  2. git add <已解决的文件>"
    echo "  3. git commit"
    echo "  4. 再次运行本脚本跑测试"
    echo ""
    echo "  放弃本次合并: git merge --abort"
    exit 1
fi

echo -e "${YELLOW}[4/5]${NC} 运行测试..."
if pytest "${TEST_FILES[@]}" -q 2>&1; then
    echo -e "${GREEN}✓ 测试全部通过${NC}"
else
    echo -e "${RED}✗ 测试失败，请检查后再推送${NC}"
    exit 1
fi

echo -e "${YELLOW}[5/5]${NC} 同步状态:"
git rev-list --left-right --count HEAD..."$UPSTREAM_REMOTE/$UPSTREAM_BRANCH" | awk '{printf "本地领先: %s 提交 | 落后上游: %s 提交\n", $1, $2}'
echo ""
echo -e "${GREEN}✅ 同步完成！推送请执行: git push origin $DEV_BRANCH${NC}"
