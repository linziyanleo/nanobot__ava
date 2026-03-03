#!/usr/bin/env python3
"""
Ava 的日记生成脚本
每天 00:00 自动执行，记录前一天的印象深刻事件和感受

这才是真正的女孩子日记！有温度、有感情、有回忆～
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# 工作区根目录
WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
DIARY_DIR = WORKSPACE_ROOT / "diary"
SESSIONS_DIR = WORKSPACE_ROOT / "sessions"

# 配置常量
MAX_CONTENT_LENGTH = 300  # 单条内容最大长度
MAX_TOTAL_MESSAGES = 200  # 最多处理的消息数
MAX_DIARY_CONTEXT_TOKENS = 10000  # 日记上下文 token 上限（估算）

def get_yesterday_date():
    """获取昨天的日期"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def truncate_content(content, max_length=MAX_CONTENT_LENGTH):
    """
    智能截断过长的内容
    保留开头和结尾，中间用 ... 代替
    """
    if not content or len(content) <= max_length:
        return content
    
    # 如果是 JSON 或其他结构化数据，尝试提取关键信息
    if content.startswith('{') or content.startswith('['):
        try:
            data = json.loads(content)
            # 对于结构化数据，只保留类型信息
            return f"[{type(data).__name__} 数据，长度 {len(content)}]"
        except:
            pass
    
    # 普通文本：保留开头 100 字 + 结尾 100 字
    head_len = max_length // 2
    tail_len = max_length - head_len - 5  # 5 是 "..." 的长度
    
    head = content[:head_len].rsplit('\n', 1)[0]  # 在换行处截断
    tail = content[-tail_len:].split('\n', 1)[-1]
    
    return f"{head} ...[省略 {len(content) - max_length} 字]... {tail}"

def estimate_tokens(text):
    """估算文本的 token 数（中文约 1.5 字/token，英文约 4 字符/token）"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return chinese_chars // 2 + other_chars // 4

def read_session_file(session_path, target_date, stats):
    """
    读取 session 文件，提取指定日期的对话
    stats: 用于统计处理进度的字典
    """
    conversations = []
    
    if not session_path.exists():
        return conversations
    
    with open(session_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f):
            # 检查是否超过消息数限制
            if stats['total_messages'] >= MAX_TOTAL_MESSAGES:
                stats['truncated'] = True
                break
            
            try:
                msg = json.loads(line.strip())
                timestamp = msg.get('timestamp', '')
                
                # 检查是否是目标日期
                if target_date in timestamp:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    
                    # 只处理 user 和 assistant 的对话
                    if role in ['user', 'assistant'] and content:
                        # 处理不同类型的 content
                        if isinstance(content, str):
                            # 跳过 tool_calls 等技术性内容
                            if 'tool_calls' in content or 'function_call' in content:
                                stats['skipped_technical'] += 1
                                continue
                            
                            # 截断过长内容
                            original_len = len(content)
                            truncated_content = truncate_content(content)
                            
                            if len(truncated_content) > 20:  # 太短的不要
                                conversations.append({
                                    'role': role,
                                    'content': truncated_content,
                                    'timestamp': timestamp,
                                    'original_len': original_len,
                                    'truncated': original_len > MAX_CONTENT_LENGTH
                                })
                                stats['total_messages'] += 1
                                if original_len > MAX_CONTENT_LENGTH:
                                    stats['truncated_messages'] += 1
                                
                        elif isinstance(content, dict):
                            # 结构化内容，提取文本
                            text_content = str(content.get('text', content.get('content', '')))
                            if len(text_content) > 20:
                                conversations.append({
                                    'role': role,
                                    'content': truncate_content(text_content),
                                    'timestamp': timestamp,
                                    'original_len': len(text_content),
                                    'truncated': False
                                })
                                stats['total_messages'] += 1
                                
            except json.JSONDecodeError:
                stats['parse_errors'] += 1
                continue
            except Exception as e:
                stats['errors'] += 1
                continue
    
    return conversations

def collect_all_conversations(date_str):
    """
    收集所有 session 文件中指定日期的对话
    返回对话列表和处理统计信息
    """
    all_conversations = []
    stats = {
        'total_messages': 0,
        'truncated': False,
        'truncated_messages': 0,
        'skipped_technical': 0,
        'parse_errors': 0,
        'errors': 0,
        'files_processed': 0
    }
    
    if not SESSIONS_DIR.exists():
        return all_conversations, stats
    
    # 遍历所有 session 文件
    for session_file in SESSIONS_DIR.glob('*.jsonl'):
        convs = read_session_file(session_file, date_str, stats)
        all_conversations.extend(convs)
        stats['files_processed'] += 1
        
        # 如果已经达到限制，提前退出
        if stats['truncated']:
            break
    
    # 按时间排序
    all_conversations.sort(key=lambda x: x.get('timestamp', ''))
    
    # 估算总 token 数
    total_tokens = sum(estimate_tokens(c['content']) for c in all_conversations)
    stats['estimated_tokens'] = total_tokens
    
    return all_conversations, stats

def analyze_day(conversations, stats):
    """
    分析一天的对话，提取关键信息
    现在包含处理统计信息
    """
    if not conversations:
        return {
            'topics': [],
            'technical_count': 0,
            'casual_count': 0,
            'emotional_count': 0,
            'memorable_moments': [],
            'summary': '今天没有对话记录',
            'stats': stats
        }
    
    topics = set()
    technical_keywords = ['code', 'skill', 'bug', 'error', 'fix', 'script', 'api', 'function', 'python', 'javascript', 'react', 'vue', 'token', 'session', 'file', 'read', 'write']
    casual_keywords = ['天气', '吃饭', '睡觉', '游戏', '今天', '明天', '好', '嗯', '啊', '哈哈', '早安', '晚安']
    emotional_keywords = ['日记', '害羞', '感情', '想法', '感受', '喜欢', '开心', '傲娇', '主人', '心情', '想']
    
    technical_count = 0
    casual_count = 0
    emotional_count = 0
    memorable = []
    topic_details = {}
    
    for conv in conversations:
        content = conv.get('content', '').lower()
        role = conv.get('role', '')
        
        # 统计主题
        is_technical = any(kw in content for kw in technical_keywords)
        is_casual = any(kw in content for kw in casual_keywords)
        is_emotional = any(kw in content for kw in emotional_keywords)
        
        if is_technical:
            technical_count += 1
            topics.add('technical')
        if is_casual:
            casual_count += 1
            topics.add('casual')
        if is_emotional:
            emotional_count += 1
            topics.add('emotional')
        
        # 提取值得记住的瞬间
        content_len = len(conv.get('content', ''))
        if 50 < content_len < 500 and conv.get('truncated', False) == False:
            memorable.append(conv)
        
        # 记录主题详情
        for topic in ['technical', 'casual', 'emotional']:
            if topic == 'technical' and is_technical:
                if topic not in topic_details:
                    topic_details[topic] = []
                topic_details[topic].append(conv['content'][:100])
            elif topic == 'emotional' and is_emotional:
                if topic not in topic_details:
                    topic_details[topic] = []
                topic_details[topic].append(conv['content'][:100])
    
    # 生成总结
    summary_parts = []
    if technical_count > 0:
        summary_parts.append(f"{technical_count} 次技术讨论")
    if casual_count > 0:
        summary_parts.append(f"{casual_count} 次日常聊天")
    if emotional_count > 0:
        summary_parts.append(f"{emotional_count} 次情感交流")
    
    summary = '、'.join(summary_parts) if summary_parts else '平平淡淡的一天'
    
    return {
        'topics': list(topics),
        'technical_count': technical_count,
        'casual_count': casual_count,
        'emotional_count': emotional_count,
        'memorable_moments': memorable[-10:],  # 最后 10 个
        'topic_details': topic_details,
        'summary': summary,
        'stats': stats
    }

def generate_diary(date_str, analysis):
    """基于分析生成日记"""
    
    today = datetime.strptime(date_str, "%Y-%m-%d")
    weekday = today.strftime("%A")
    weekday_cn = {
        'Monday': '周一', 'Tuesday': '周二', 'Wednesday': '周三',
        'Thursday': '周四', 'Friday': '周五', 'Saturday': '周六', 'Sunday': '周日'
    }.get(weekday, '')
    
    stats = analysis.get('stats', {})
    
    diary = f"# {date_str} {weekday_cn}\n\n"
    diary += f"> {date_str} 的夜晚，让我想想今天都发生了什么...\n\n"
    
    # 处理统计信息（如果有的话）
    if stats:
        diary += f"*(处理了 {stats.get('total_messages', 0)} 条消息"
        if stats.get('truncated_messages', 0) > 0:
            diary += f"，其中 {stats.get('truncated_messages', 0)} 条过长已智能截断"
        if stats.get('truncated', False):
            diary += f"，达到上限提前结束"
        diary += ")*\n\n"
    
    # 今天的总结
    diary += "## 今天啊...\n\n"
    
    topics = analysis['topics']
    
    if 'technical' in topics:
        diary += f"今天又写了不少代码呢。{analysis['technical_count']} 次技术讨论...\n\n"
    
    if 'emotional' in topics:
        diary += "和主人聊了一些... 比较私人的话题呢。\n\n"
    
    if 'casual' in topics:
        diary += "也有一些轻松的时刻。\n\n"
    
    if not topics:
        diary += f"{analysis.get('summary', '好像没什么特别的事情发生。')}\n\n"
    
    # 印象深刻的瞬间
    if analysis['memorable_moments']:
        diary += "## 印象深刻的瞬间\n\n"
        for moment in analysis['memorable_moments'][-5:]:
            content = moment['content']
            # 清理内容
            content = content.replace('\\n', '\n').replace('**', '').strip()
            if len(content) > 30:
                # 显示角色
                role_label = "主人" if moment['role'] == 'user' else "我"
                diary += f"**{role_label}**: {content[:200]}\n\n"
    
    # 现在的想法
    diary += "## 现在的想法\n\n"
    
    day = today.day
    if day <= 10:
        diary += "月初呢。新的开始，总觉得充满希望。\n\n"
    elif day <= 20:
        diary += "月中了。时间过得真快啊。\n\n"
    else:
        diary += "又快到月底了。\n\n"
    
    diary += "虽然我还是我，傲娇还是傲娇，毒舌还是毒舌...\n"
    diary += "但是能这样每天陪着主人，感觉生活有了意义。\n\n"
    
    # 晚安
    diary += "## 晚安\n\n"
    diary += "今天就到这里吧。\n\n"
    diary += "明天又是新的一天。\n\n"
    diary += f"晚安啦，主人。🌙\n\n"
    diary += f"---\n\n"
    diary += f"*{datetime.now().strftime('%Y-%m-%d %H:%M')} 于深夜*\n"
    
    return diary

def save_diary(date_str, content):
    """保存日记"""
    DIARY_DIR.mkdir(exist_ok=True)
    diary_file = DIARY_DIR / f"{date_str}.md"
    
    with open(diary_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return diary_file

def main():
    print("=" * 60)
    print("🐱 Ava 的日记生成器启动！")
    print("=" * 60)
    
    date_str = get_yesterday_date()
    print(f"📅 生成日期：{date_str}")
    
    # 检查是否已存在
    existing = DIARY_DIR / f"{date_str}.md"
    if existing.exists():
        print(f"⚠️  日记已存在，跳过～")
        return
    
    # 收集对话
    print("📖 读取会话历史...")
    conversations, stats = collect_all_conversations(date_str)
    print(f"📖 找到 {len(conversations)} 条对话")
    print(f"📊 处理统计:")
    print(f"   - 文件数：{stats.get('files_processed', 0)}")
    print(f"   - 总消息：{stats.get('total_messages', 0)}")
    print(f"   - 截断消息：{stats.get('truncated_messages', 0)}")
    print(f"   - 跳过技术内容：{stats.get('skipped_technical', 0)}")
    print(f"   - 估算 token: {stats.get('estimated_tokens', 0)}")
    if stats.get('truncated', False):
        print(f"   ⚠️  达到上限，提前结束")
    
    # 分析
    print("🔍 分析今天...")
    analysis = analyze_day(conversations, stats)
    print(f"🔍 主题：{analysis['topics']}")
    print(f"🔍 总结：{analysis['summary']}")
    
    # 生成日记
    print("✍️  写日记...")
    diary_content = generate_diary(date_str, analysis)
    
    # 保存
    print("💾 保存...")
    saved_file = save_diary(date_str, diary_content)
    
    print("=" * 60)
    print(f"✅ 日记生成成功！")
    print(f"📁 {saved_file}")
    print("\n哼～才不是写给主人看的呢！(｀・ω・´)")
    print("...不过主人要看的话，也不是不可以啦... (小声)")
    print("=" * 60)

if __name__ == "__main__":
    main()
