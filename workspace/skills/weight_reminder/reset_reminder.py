#!/usr/bin/env python3
"""
重置体重提醒状态

执行时机：每天早上 8:30 后自动执行一次
逻辑：
1. 读取 HEARTBEAT.md 和 state.json
2. 检查今天是否已经重置过
3. 如果是新的一天，将任务从 Completed 移回 Active Tasks
4. 更新 state.json
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
HEARTBEAT_FILE = WORKSPACE / "HEARTBEAT.md"
STATE_FILE = Path(__file__).parent / "state.json"

def get_today():
    """获取今天的日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")

def load_state():
    """加载状态文件"""
    if not STATE_FILE.exists():
        return {"lastReset": None, "lastReminderDate": None}
    
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"lastReset": None, "lastReminderDate": None}

def save_state(state):
    """保存状态文件"""
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def read_heartbeat():
    """读取 HEARTBEAT.md 内容"""
    if not HEARTBEAT_FILE.exists():
        return None
    return HEARTBEAT_FILE.read_text(encoding='utf-8')

def save_heartbeat(content):
    """保存 HEARTBEAT.md 内容"""
    HEARTBEAT_FILE.write_text(content, encoding='utf-8')

def move_task_to_active(content, task_keyword="体重提醒"):
    """将任务从 Completed 移回 Active Tasks"""
    # 分割文件
    parts = content.split("## Completed")
    if len(parts) < 2:
        return content, False
    
    active_section = parts[0]
    completed_section = "## Completed" + parts[1]
    
    # 在 Completed 中查找任务行
    completed_lines = completed_section.split('\n')
    task_line = None
    task_line_idx = None
    
    for i, line in enumerate(completed_lines):
        if task_keyword in line and ("- [ ]" in line or "- [x]" in line):
            task_line = line.strip()
            task_line_idx = i
            break
    
    if not task_line:
        return content, False
    
    # 从 Completed 中移除
    completed_lines.pop(task_line_idx)
    
    # 确保任务是未选中状态
    if "- [x]" in task_line:
        task_line = task_line.replace("- [x]", "- [ ]")
    elif "- [ ]" not in task_line:
        task_line = f"- [ ] {task_line}"
    
    # 添加到 Active Tasks
    # 找到 Active Tasks 部分的末尾（## Completed 之前或文件末尾）
    active_lines = active_section.split('\n')
    
    # 找到最后一个非空行
    insert_idx = len(active_lines)
    for i in range(len(active_lines) - 1, -1, -1):
        if active_lines[i].strip() and not active_lines[i].strip().startswith('<!--'):
            insert_idx = i + 1
            break
    
    # 插入任务
    active_lines.insert(insert_idx, task_line)
    
    # 重新组合
    new_active_section = '\n'.join(active_lines)
    new_completed_section = '\n'.join(completed_lines)
    
    return new_active_section + new_completed_section, True

def main():
    today = get_today()
    state = load_state()
    
    print(f"📅 今天日期：{today}")
    print(f"📝 上次重置：{state['lastReset']}")
    
    # 检查今天是否已经重置过
    if state['lastReset'] == today:
        print("✅ 今日已重置，跳过")
        return 0
    
    # 检查时间是否 >= 7:00
    now = datetime.now()
    if now.hour < 7:
        print("⏰ 未到重置时间（7:00 后）")
        return 0
    
    # 读取 HEARTBEAT.md
    content = read_heartbeat()
    if not content:
        print("❌ HEARTBEAT.md 不存在")
        return 1
    
    # 移动任务到 Active Tasks
    new_content, moved = move_task_to_active(content)
    
    if moved:
        # 保存更新
        save_heartbeat(new_content)
        
        # 更新状态
        state['lastReset'] = today
        state['lastReminderDate'] = today
        save_state(state)
        
        print("✅ 已将体重提醒重置为 Active 状态")
        print("📊 状态文件已更新")
    else:
        print("ℹ️ 任务已在 Active Tasks 中或不存在")
        # 仍然更新状态，避免重复检查
        state['lastReset'] = today
        save_state(state)
    
    return 0

if __name__ == "__main__":
    exit(main())
