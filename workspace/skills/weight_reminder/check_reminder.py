#!/usr/bin/env python3
"""
检查体重提醒状态

执行时机：心跳任务检查时（每 30 分钟）
逻辑：
1. 读取 HEARTBEAT.md
2. 检查当前时间是否 >= 8:30
3. 检查 "体重提醒" 任务是否在 Completed 部分
4. 输出状态信息
"""

import os
import json
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
HEARTBEAT_FILE = WORKSPACE / "HEARTBEAT.md"
STATE_FILE = Path(__file__).parent / "state.json"

def get_current_time():
    """获取当前时间（CST）"""
    return datetime.now()

def is_after_8_30():
    """检查当前时间是否 >= 8:30"""
    now = get_current_time()
    return now.hour > 8 or (now.hour == 8 and now.minute >= 30)

def read_heartbeat():
    """读取 HEARTBEAT.md 内容"""
    if not HEARTBEAT_FILE.exists():
        return None
    return HEARTBEAT_FILE.read_text(encoding='utf-8')

def check_task_status(content):
    """检查体重提醒任务的状态"""
    if not content:
        return "unknown", "HEARTBEAT.md 不存在"
    
    # 分割 Active Tasks 和 Completed 部分
    parts = content.split("## Completed")
    if len(parts) < 2:
        return "active", "未找到 Completed 部分"
    
    active_section = parts[0]
    completed_section = parts[1] if len(parts) > 1 else ""
    
    # 检查体重提醒在哪个部分
    if "体重提醒" in completed_section:
        return "completed", "今日已完成"
    elif "体重提醒" in active_section:
        return "active", "待提醒"
    else:
        return "missing", "未找到体重提醒任务"

def main():
    now = get_current_time()
    current_time_str = now.strftime("%H:%M")
    
    print(f"当前时间：{current_time_str}")
    
    # 检查时间
    if not is_after_8_30():
        print("⏰ 未到提醒时间（8:30 后）")
        print("状态：等待")
        return 0
    
    # 读取文件并检查状态
    content = read_heartbeat()
    status, message = check_task_status(content)
    
    print(f"📊 体重提醒状态：{status.upper()}")
    print(f"📝 {message}")
    
    if status == "completed":
        print("✅ 今日已完成，等待明日重置")
    elif status == "active":
        print("⏳ 待提醒状态，等待用户报体重")
    elif status == "missing":
        print("❌ 任务配置缺失，请检查 HEARTBEAT.md")
    
    return 0

if __name__ == "__main__":
    exit(main())
