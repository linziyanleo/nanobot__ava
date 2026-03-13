#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# sync-gitlab.sh
# 双仓库同步脚本：GitHub (原 author) + GitLab (改写 author)
# ============================================================

GITLAB_REMOTE="gitlab"
GITHUB_REMOTE="origin"

NEW_NAME="方壶"
NEW_EMAIL="fanghu.lzy@alibaba-inc.com"

REPO_ROOT="$(git rev-parse --show-toplevel)"
TMP_DIR=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

cleanup() {
    if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
        log_info "清理临时目录: ${TMP_DIR}"
        rm -rf "${TMP_DIR}"
    fi
}
trap cleanup EXIT

usage() {
    cat <<EOF
用法: $(basename "$0") [选项]

选项:
  --github-only    仅推送到 GitHub（保持原 author）
  --gitlab-only    仅推送到 GitLab（改写 author）
  --branches LIST  指定分支列表（逗号分隔），默认推送所有本地分支
  --dry-run        仅打印操作，不实际执行
  -h, --help       显示帮助

示例:
  $(basename "$0")                              # 同步全部分支到两个仓库
  $(basename "$0") --gitlab-only                # 仅推送到 GitLab
  $(basename "$0") --branches feat/0.0.1,main   # 仅同步指定分支
EOF
}

check_prerequisites() {
    if ! git remote get-url "${GITLAB_REMOTE}" &>/dev/null; then
        log_error "Remote '${GITLAB_REMOTE}' 不存在，请先添加: git remote add ${GITLAB_REMOTE} <url>"
        exit 1
    fi

    if ! git remote get-url "${GITHUB_REMOTE}" &>/dev/null; then
        log_error "Remote '${GITHUB_REMOTE}' 不存在"
        exit 1
    fi

    if command -v git-filter-repo &>/dev/null; then
        FILTER_TOOL="filter-repo"
        log_info "使用 git-filter-repo 进行 author 改写"
    else
        FILTER_TOOL="filter-branch"
        log_warn "git-filter-repo 未安装，降级使用 git filter-branch（性能较差）"
        log_warn "推荐安装: brew install git-filter-repo"
    fi
}

get_local_branches() {
    git for-each-ref --format='%(refname:short)' refs/heads/
}

push_to_github() {
    local branches=("$@")
    log_info "========== 推送到 GitHub (${GITHUB_REMOTE}) =========="
    for branch in "${branches[@]}"; do
        if [[ "${DRY_RUN}" == "true" ]]; then
            log_info "[DRY-RUN] git push ${GITHUB_REMOTE} ${branch}"
        else
            log_info "推送分支: ${branch}"
            git push "${GITHUB_REMOTE}" "${branch}" 2>&1 || log_warn "推送 ${branch} 到 GitHub 失败，继续..."
        fi
    done
    log_info "GitHub 推送完成"
}

rewrite_and_push_filter_repo() {
    local branches=("$@")

    TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sync-gitlab-XXXXXX")"
    log_info "创建临时 bare clone: ${TMP_DIR}"

    git clone --bare "${REPO_ROOT}" "${TMP_DIR}/repo.git"

    cd "${TMP_DIR}/repo.git"

    local mailmap_file="${TMP_DIR}/mailmap"

    log_info "收集所有 author/committer 邮箱，生成 mailmap..."
    > "${mailmap_file}"
    git log --all --format='%an <%ae>' | sort -u | while IFS= read -r entry; do
        echo "${NEW_NAME} <${NEW_EMAIL}> ${entry}" >> "${mailmap_file}"
    done
    git log --all --format='%cn <%ce>' | sort -u | while IFS= read -r entry; do
        echo "${NEW_NAME} <${NEW_EMAIL}> ${entry}" >> "${mailmap_file}"
    done
    sort -u -o "${mailmap_file}" "${mailmap_file}"

    log_info "mailmap 条目数: $(wc -l < "${mailmap_file}" | tr -d ' ')"
    log_info "执行 git-filter-repo author 改写..."
    git filter-repo --mailmap "${mailmap_file}" --force

    git remote add "${GITLAB_REMOTE}" "$(git -C "${REPO_ROOT}" remote get-url "${GITLAB_REMOTE}")"

    for branch in "${branches[@]}"; do
        if git show-ref --verify --quiet "refs/heads/${branch}" 2>/dev/null; then
            log_info "推送分支到 GitLab: ${branch}"
            git push "${GITLAB_REMOTE}" "${branch}" --force 2>&1 || log_warn "推送 ${branch} 到 GitLab 失败，继续..."
        else
            log_warn "临时仓库中不存在分支 ${branch}，跳过"
        fi
    done

    cd "${REPO_ROOT}"
}

rewrite_and_push_filter_branch() {
    local branches=("$@")

    TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sync-gitlab-XXXXXX")"
    log_info "创建临时 bare clone: ${TMP_DIR}"

    git clone --bare "${REPO_ROOT}" "${TMP_DIR}/repo.git"

    cd "${TMP_DIR}/repo.git"

    log_info "执行 git filter-branch author 改写（所有 author）..."

    local filter_env
    filter_env=$(cat <<ENVFILTER
export GIT_COMMITTER_NAME="${NEW_NAME}"
export GIT_COMMITTER_EMAIL="${NEW_EMAIL}"
export GIT_AUTHOR_NAME="${NEW_NAME}"
export GIT_AUTHOR_EMAIL="${NEW_EMAIL}"
ENVFILTER
)

    local branch_refs=()
    for branch in "${branches[@]}"; do
        if git show-ref --verify --quiet "refs/heads/${branch}" 2>/dev/null; then
            branch_refs+=("refs/heads/${branch}")
        fi
    done

    if [[ ${#branch_refs[@]} -gt 0 ]]; then
        FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --env-filter "${filter_env}" -- "${branch_refs[@]}"
    fi

    git remote add "${GITLAB_REMOTE}" "$(git -C "${REPO_ROOT}" remote get-url "${GITLAB_REMOTE}")"

    for branch in "${branches[@]}"; do
        if git show-ref --verify --quiet "refs/heads/${branch}" 2>/dev/null; then
            log_info "推送分支到 GitLab: ${branch}"
            git push "${GITLAB_REMOTE}" "${branch}" --force 2>&1 || log_warn "推送 ${branch} 到 GitLab 失败，继续..."
        fi
    done

    cd "${REPO_ROOT}"
}

sync_to_gitlab() {
    local branches=("$@")
    log_info "========== 推送到 GitLab (${GITLAB_REMOTE}) =========="

    if [[ "${DRY_RUN}" == "true" ]]; then
        for branch in "${branches[@]}"; do
            log_info "[DRY-RUN] 改写 author 并推送 ${branch} -> ${GITLAB_REMOTE}"
        done
        return
    fi

    if [[ "${FILTER_TOOL}" == "filter-repo" ]]; then
        rewrite_and_push_filter_repo "${branches[@]}"
    else
        rewrite_and_push_filter_branch "${branches[@]}"
    fi

    log_info "GitLab 推送完成"
}

main() {
    local github_only=false
    local gitlab_only=false
    local custom_branches=""
    DRY_RUN="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --github-only) github_only=true; shift ;;
            --gitlab-only) gitlab_only=true; shift ;;
            --branches)    custom_branches="$2"; shift 2 ;;
            --dry-run)     DRY_RUN="true"; shift ;;
            -h|--help)     usage; exit 0 ;;
            *)             log_error "未知参数: $1"; usage; exit 1 ;;
        esac
    done

    if [[ "${github_only}" == "true" && "${gitlab_only}" == "true" ]]; then
        log_error "--github-only 和 --gitlab-only 不能同时使用"
        exit 1
    fi

    check_prerequisites

    local branches=()
    if [[ -n "${custom_branches}" ]]; then
        IFS=',' read -ra branches <<< "${custom_branches}"
    else
        while IFS= read -r branch; do
            branches+=("${branch}")
        done < <(get_local_branches)
    fi

    if [[ ${#branches[@]} -eq 0 ]]; then
        log_error "没有找到可推送的分支"
        exit 1
    fi

    log_info "待同步分支: ${branches[*]}"
    echo ""

    if [[ "${gitlab_only}" != "true" ]]; then
        push_to_github "${branches[@]}"
        echo ""
    fi

    if [[ "${github_only}" != "true" ]]; then
        sync_to_gitlab "${branches[@]}"
        echo ""
    fi

    log_info "✅ 同步完成！"
}

main "$@"
