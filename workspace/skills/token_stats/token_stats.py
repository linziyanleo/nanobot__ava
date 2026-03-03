#!/usr/bin/env python3
"""
查看 session 的 token 消耗统计
"""

import json
import os
from pathlib import Path
from datetime import datetime

WORKSPACE = os.environ.get('NANOBOT_WORKSPACE', '/Users/leolin/Desktop/Work/nanobot__ava/workspace')
SESSIONS_DIR = Path(WORKSPACE) / 'sessions'

def format_tokens(num: int) -> str:
    """格式化 token 数字"""
    if num >= 1000000:
        return f"{num / 1000000:.2f}M"
    elif num >= 1000:
        return f"{num / 1000:.2f}K"
    return str(num)

def list_sessions():
    """列出所有 session 的 token 统计"""
    if not SESSIONS_DIR.exists():
        print("❌ sessions 目录不存在")
        return
    
    sessions = []
    for path in SESSIONS_DIR.glob("*.jsonl"):
        try:
            with open(path, encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line:
                    data = json.loads(first_line)
                    if data.get("_type") == "metadata":
                        token_stats = data.get("token_stats", {})
                        sessions.append({
                            "key": data.get("key", path.stem),
                            "updated_at": data.get("updated_at"),
                            "total_tokens": token_stats.get("total_tokens", 0),
                            "total_prompt_tokens": token_stats.get("total_prompt_tokens", 0),
                            "total_completion_tokens": token_stats.get("total_completion_tokens", 0),
                            "llm_calls": token_stats.get("llm_calls", 0),
                        })
        except Exception as e:
            print(f"⚠️ 读取 {path.name} 失败：{e}")
    
    if not sessions:
        print("📭 没有找到 session 记录")
        return
    
    # 按 total_tokens 排序
    sessions.sort(key=lambda x: x["total_tokens"], reverse=True)
    
    print(f"\n{'='*80}")
    print(f"📊 Session Token 消耗统计 ({len(sessions)} 个会话)")
    print(f"{'='*80}\n")
    
    total_all = 0
    for i, s in enumerate(sessions, 1):
        total_all += s["total_tokens"]
        updated = s["updated_at"][:16].replace("T", " ") if s.get("updated_at") else "Unknown"
        print(f"{i:2}. {s['key'][:40]:<40}  {s['total_tokens']:>10,} tokens")
        print(f"    └─ Prompt: {s['total_prompt_tokens']:>10,} | Completion: {s['total_completion_tokens']:>10,} | Calls: {s['llm_calls']:>5}")
        print(f"    └─ 更新：{updated}\n")
    
    print(f"{'='*80}")
    print(f"📈 总计：{format_tokens(total_all)} tokens ({total_all:,})")
    print(f"{'='*80}\n")

def main():
    print(f"🔍 扫描 sessions 目录：{SESSIONS_DIR}")
    list_sessions()

if __name__ == '__main__':
    main()
