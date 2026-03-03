#!/usr/bin/env python3
"""
Ava 的记忆整理脚本
每天自动整理 MEMORY.md 和 HISTORY.md
- 保留重要信息（长期偏好、身份、项目背景）
- 清理临时信息（时间线条目、临时过程细节）
"""

import os
import re
from datetime import datetime

WORKSPACE = os.environ.get('NANOBOT_WORKSPACE', '/Users/leolin/Desktop/Work/nanobot__ava/workspace')
MEMORY_FILE = os.path.join(WORKSPACE, 'memory/MEMORY.md')
HISTORY_FILE = os.path.join(WORKSPACE, 'memory/HISTORY.md')

def is_important_line(line):
    """判断一行是否是重要信息（应该保留在 MEMORY.md）"""
    # 时间线条目应该移到 HISTORY.md
    if re.match(r'^\s*-\s*\[\d{4}-\d{2}-\d{2}', line):
        return False
    if re.match(r'^\s*\[?\d{4}-\d{2}-\d{2}', line):
        return False
    
    # 临时状态、过程细节不应该保留
    temp_keywords = ['临时', '暂时', '进行中', 'testing', 'debug', 'todo']
    if any(kw in line.lower() for kw in temp_keywords):
        return False
    
    return True

def is_timeline_entry(line):
    """判断是否是时间线条目（应该放在 HISTORY.md）"""
    return bool(re.match(r'^\s*-\s*\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]', line))

def cleanup_memory():
    """整理 MEMORY.md"""
    if not os.path.exists(MEMORY_FILE):
        print("MEMORY.md 不存在，跳过")
        return
    
    with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    important_lines = []
    timeline_lines = []
    
    for line in lines:
        if is_timeline_entry(line):
            timeline_lines.append(line)
        elif is_important_line(line):
            important_lines.append(line)
    
    # 写回 MEMORY.md（只保留重要信息）
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        f.writelines(important_lines)
    
    # 如果有时间线条目，追加到 HISTORY.md
    if timeline_lines:
        with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')} 记忆整理\n\n")
            f.writelines(timeline_lines)
    
    print(f"✓ MEMORY.md 整理完成：保留 {len(important_lines)} 行，移动 {len(timeline_lines)} 行时间线条目到 HISTORY.md")

def main():
    print(f"🧹 开始整理记忆... ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    cleanup_memory()
    print("✨ 记忆整理完成！")

if __name__ == '__main__':
    main()
