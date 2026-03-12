#!/usr/bin/env python3
"""
日记素材提取器
从 session 文件中提取前一天的对话素材，输出结构化文本到 stdout。
Agent 读取 stdout 后，以第一人称用 LLM 写作日记。
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
SESSIONS_DIR = WORKSPACE_ROOT / "sessions"
DIARY_DIR = WORKSPACE_ROOT / "diary"

MAX_CONTENT_LENGTH = 500
MAX_TOTAL_MESSAGES = 200

WEEKDAY_CN = {
    'Monday': '周一', 'Tuesday': '周二', 'Wednesday': '周三',
    'Thursday': '周四', 'Friday': '周五', 'Saturday': '周六', 'Sunday': '周日'
}

SKIP_PATTERNS = [
    'tool_calls', 'function_call', '✅ AIWay 心跳检查',
    'heartbeat', '[Scheduled Task]', 'Timer finished'
]


def get_yesterday_date():
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def truncate_content(content, max_length=MAX_CONTENT_LENGTH):
    if not content or len(content) <= max_length:
        return content
    if content.startswith('{') or content.startswith('['):
        try:
            json.loads(content)
            return f"[结构化数据，{len(content)} 字]"
        except Exception:
            pass
    head_len = max_length * 2 // 3
    tail_len = max_length // 3
    return f"{content[:head_len]}...[省略]...{content[-tail_len:]}"


def estimate_tokens(text):
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return chinese_chars // 2 + other_chars // 4


def should_skip(content):
    content_lower = content.lower()
    return any(p.lower() in content_lower for p in SKIP_PATTERNS)


def read_session_file(session_path, target_date, stats):
    conversations = []
    if not session_path.exists():
        return conversations

    with open(session_path, 'r', encoding='utf-8') as f:
        for line in f:
            if stats['total_messages'] >= MAX_TOTAL_MESSAGES:
                stats['truncated'] = True
                break
            try:
                msg = json.loads(line.strip())
                timestamp = msg.get('timestamp', '')
                if target_date not in timestamp:
                    continue

                role = msg.get('role', '')
                content = msg.get('content', '')

                if role not in ('user', 'assistant') or not content:
                    continue
                if isinstance(content, dict):
                    content = str(content.get('text', content.get('content', '')))
                if not isinstance(content, str) or len(content) < 15:
                    continue
                if should_skip(content):
                    stats['skipped'] += 1
                    continue

                conversations.append({
                    'role': role,
                    'content': truncate_content(content),
                    'timestamp': timestamp,
                    'time': timestamp[11:16] if len(timestamp) >= 16 else '',
                })
                stats['total_messages'] += 1

            except (json.JSONDecodeError, Exception):
                stats['errors'] += 1
    return conversations


def collect_all_conversations(date_str):
    all_convs = []
    stats = {
        'total_messages': 0, 'truncated': False, 'skipped': 0,
        'errors': 0, 'files_processed': 0
    }

    if not SESSIONS_DIR.exists():
        return all_convs, stats

    for sf in SESSIONS_DIR.glob('*.jsonl'):
        convs = read_session_file(sf, date_str, stats)
        all_convs.extend(convs)
        stats['files_processed'] += 1
        if stats['truncated']:
            break

    all_convs.sort(key=lambda x: x.get('timestamp', ''))
    return all_convs, stats


def build_timeline(conversations):
    """按时间段分组对话，每个时段形成一个事件块。"""
    if not conversations:
        return []

    segments = []
    current_segment = {'start': '', 'end': '', 'conversations': []}

    for conv in conversations:
        t = conv.get('time', '')
        if not current_segment['conversations']:
            current_segment['start'] = t
            current_segment['end'] = t
            current_segment['conversations'].append(conv)
        else:
            last_t = current_segment['end']
            gap_minutes = _time_diff_minutes(last_t, t)
            if gap_minutes > 30:
                segments.append(current_segment)
                current_segment = {'start': t, 'end': t, 'conversations': [conv]}
            else:
                current_segment['end'] = t
                current_segment['conversations'].append(conv)

    if current_segment['conversations']:
        segments.append(current_segment)

    return segments


def _time_diff_minutes(t1, t2):
    """计算两个 HH:MM 格式时间的分钟差。"""
    try:
        h1, m1 = map(int, t1.split(':'))
        h2, m2 = map(int, t2.split(':'))
        return (h2 * 60 + m2) - (h1 * 60 + m1)
    except Exception:
        return 0


def _find_silent_periods(segments):
    """找出时间线中的沉默时段（间隔 > 60 分钟）。"""
    silents = []
    for i in range(len(segments) - 1):
        end_t = segments[i]['end']
        start_t = segments[i + 1]['start']
        gap = _time_diff_minutes(end_t, start_t)
        if gap > 60:
            silents.append(f"{end_t} - {start_t}（沉默 {gap} 分钟）")
    return silents


def extract_material(date_str):
    """提取结构化素材，返回文本。"""
    conversations, stats = collect_all_conversations(date_str)

    if not conversations:
        return f"# 日记素材 — {date_str}\n\n今天没有对话记录。"

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekday_cn = WEEKDAY_CN.get(dt.strftime("%A"), '')

    segments = build_timeline(conversations)
    silents = _find_silent_periods(segments)

    lines = [f"# 日记素材 — {date_str} {weekday_cn}\n"]

    lines.append("## 统计")
    lines.append(f"- 总消息数: {stats['total_messages']}")
    if segments:
        lines.append(f"- 活跃时段: {segments[0]['start']} - {segments[-1]['end']}")
    if silents:
        lines.append(f"- 沉默时段: {'; '.join(silents)}")
    lines.append("")

    lines.append("## 时间线")
    for seg in segments:
        n = len(seg['conversations'])
        lines.append(f"\n### {seg['start']} - {seg['end']}（{n} 条消息）")
        for conv in seg['conversations']:
            role_label = "主人" if conv['role'] == 'user' else "我"
            content = conv['content'].replace('\n', ' ').strip()
            if len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"- [{role_label} {conv['time']}] {content}")

    lines.append("\n## 关键对话片段")
    key_convs = _select_key_conversations(conversations)
    for conv in key_convs:
        role_label = "主人" if conv['role'] == 'user' else "我"
        lines.append(f"\n**[{conv['time']}] {role_label}:**")
        lines.append(conv['content'])

    return '\n'.join(lines)


def _select_key_conversations(conversations, max_count=8):
    """挑选最有价值的对话片段：较长的、有情感的、非技术汇报的。"""
    scored = []
    for conv in conversations:
        content = conv['content']
        score = 0
        length = len(content)
        if 50 < length < 400:
            score += 2
        elif length >= 400:
            score += 1

        emotional_words = ['哈哈', '笑死', '😂', '🤣', '开心', '难过', '生气',
                           '想', '喜欢', '讨厌', '无聊', '好吃', '馋', '可爱',
                           '晚安', '早安', '加油', '辛苦', '害', '呜', '啊',
                           '！！', '？？', '...', '～', '嘿嘿', '哼', '呢']
        score += sum(1 for w in emotional_words if w in content)

        if conv['role'] == 'user':
            score += 1

        scored.append((score, conv))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [conv for _, conv in scored[:max_count]]
    selected.sort(key=lambda x: x.get('timestamp', ''))
    return selected


def main():
    date_str = get_yesterday_date()

    if len(sys.argv) > 1:
        date_str = sys.argv[1]

    existing = DIARY_DIR / f"{date_str}.md"
    if existing.exists():
        print(f"[SKIP] 日记已存在: {existing}", file=sys.stderr)
        sys.exit(0)

    material = extract_material(date_str)
    print(material)


if __name__ == "__main__":
    main()
