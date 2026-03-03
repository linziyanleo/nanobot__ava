# Identity Manager - 通讯录管理

## 功能描述

管理 nanobot 的 identity_map.yaml，实现"识人"功能的增删改查。通过这个 skill，Ava 可以：
- 添加新联系人
- 更新现有联系人的多平台账号
- 查询联系人信息
- 删除联系人

## 核心概念

### identity_map.yaml 结构

```yaml
persons:
  <person_key>:
    display_name: <称呼列表，用 / 分隔>
    ids:
      - channel: <平台名称，如 telegram/feishu/cli/wechat>
        id:
          - <账号 ID 1>
          - <账号 ID 2>
```

### 平台名称规范

- `telegram` - Telegram
- `feishu` - 飞书
- `cli` - 命令行
- `wechat` - 微信
- `dingtalk` - 钉钉

## 使用方法

### 1. 添加新联系人

**场景**: 第一次认识某个人，需要记录他的信息

**步骤**:
1. 读取 identity_map.yaml
2. 在 `persons` 下添加新条目
3. 写入文件

**示例代码** (Python):
```python
import yaml

def add_person(person_key: str, display_name: str, channel: str, account_id: str):
    # 读取现有文件
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {'persons': {}}
    
    # 添加新人
    data['persons'][person_key] = {
        'display_name': display_name,
        'ids': [{
            'channel': channel,
            'id': [account_id]
        }]
    }
    
    # 写回文件
    with open('workspace/memory/identity_map.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    return f"✅ 已添加 {display_name} 到通讯录！"
```

**使用示例**:
```bash
# 添加新人 Tony
python -c "
import yaml
with open('workspace/memory/identity_map.yaml', 'r') as f:
    data = yaml.safe_load(f)
data['persons']['tony'] = {
    'display_name': 'Tony Lee / 祥子哥',
    'ids': [{'channel': 'telegram', 'id': ['12345678']}]
}
with open('workspace/memory/identity_map.yaml', 'w') as f:
    yaml.dump(data, f, allow_unicode=True)
"
```

### 2. 为现有联系人添加新平台账号

**场景**: 已经认识的人，又在一个新平台联系上了

**步骤**:
1. 读取 identity_map.yaml
2. 找到对应 person
3. 检查该平台是否已存在
   - 存在：追加账号 ID 到列表
   - 不存在：添加新的 channel 条目
4. 写入文件

**示例代码** (Python):
```python
def add_account(person_key: str, channel: str, account_id: str):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    person = data['persons'].get(person_key)
    if not person:
        return f"❌ 未找到联系人：{person_key}"
    
    # 查找该平台是否已存在
    for item in person['ids']:
        if item['channel'] == channel:
            # 平台已存在，追加账号
            if account_id not in item['id']:
                item['id'].append(account_id)
            break
    else:
        # 平台不存在，添加新条目
        person['ids'].append({
            'channel': channel,
            'id': [account_id]
        })
    
    with open('workspace/memory/identity_map.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    return f"✅ 已为 {person['display_name']} 添加 {channel} 账号！"
```

### 3. 查询联系人信息

**场景**: 想知道某个人的所有账号信息

**示例代码**:
```python
def get_person(person_key: str):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    person = data['persons'].get(person_key)
    if not person:
        return None
    
    return {
        'key': person_key,
        'display_name': person['display_name'],
        'accounts': person['ids']
    }
```

### 4. 通过平台账号反查联系人

**场景**: 收到消息，想知道是谁发的

**示例代码**:
```python
def lookup_by_account(channel: str, account_id: str):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    for person_key, person in data['persons'].items():
        for item in person['ids']:
            if item['channel'] == channel and account_id in item['id']:
                return {
                    'person_key': person_key,
                    'display_name': person['display_name']
                }
    
    return None  # 未找到
```

### 5. 更新联系人 display_name

**场景**: 联系人的称呼变了

**示例代码**:
```python
def update_display_name(person_key: str, new_display_name: str):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if person_key not in data['persons']:
        return f"❌ 未找到联系人：{person_key}"
    
    data['persons'][person_key]['display_name'] = new_display_name
    
    with open('workspace/memory/identity_map.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    return f"✅ 已更新称呼为：{new_display_name}"
```

### 6. 删除联系人

**场景**: 需要移除某个联系人

**示例代码**:
```python
def remove_person(person_key: str):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if person_key not in data['persons']:
        return f"❌ 未找到联系人：{person_key}"
    
    del data['persons'][person_key]
    
    with open('workspace/memory/identity_map.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    return f"✅ 已删除联系人：{person_key}"
```

### 7. 删除某个平台账号

**场景**: 某人在某个平台的账号不再使用

**示例代码**:
```python
def remove_account(person_key: str, channel: str, account_id: str = None):
    with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    person = data['persons'].get(person_key)
    if not person:
        return f"❌ 未找到联系人：{person_key}"
    
    # 找到并删除对应平台
    for i, item in enumerate(person['ids']):
        if item['channel'] == channel:
            if account_id:
                # 删除特定账号
                if account_id in item['id']:
                    item['id'].remove(account_id)
                    # 如果该平台的账号列表为空，删除整个平台条目
                    if not item['id']:
                        person['ids'].pop(i)
            else:
                # 删除整个平台
                person['ids'].pop(i)
            break
    
    with open('workspace/memory/identity_map.yaml', 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    
    return f"✅ 已删除账号！"
```

## 快捷命令示例

### 使用 exec 工具直接操作

**添加新人**:
```bash
python3 -c "
import yaml
path = 'workspace/memory/identity_map.yaml'
with open(path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f) or {'persons': {}}
data['persons']['newperson'] = {
    'display_name': 'New Person / 昵称',
    'ids': [{'channel': 'telegram', 'id': ['12345678']}]
}
with open(path, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
print('✅ 已添加新人！')
"
```

**添加账号**:
```bash
python3 -c "
import yaml
path = 'workspace/memory/identity_map.yaml'
with open(path, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
person = data['persons'].get('leo')
if person:
    found = False
    for item in person['ids']:
        if item['channel'] == 'feishu':
            if 'ou_new123' not in item['id']:
                item['id'].append('ou_new123')
            found = True
            break
    if not found:
        person['ids'].append({'channel': 'feishu', 'id': ['ou_new123']})
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    print('✅ 已添加账号！')
"
```

**查询所有人**:
```bash
python3 -c "
import yaml
with open('workspace/memory/identity_map.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
for key, person in data['persons'].items():
    print(f\"{person['display_name']} ({key}):\")
    for item in person['ids']:
        print(f\"  - {item['channel']}: {item['id']}\")
"
```

## 注意事项

1. **person_key 命名规范**: 使用小写字母，可以包含下划线，如 `leo`, `wei_xia`, `tony_lee`
2. **display_name 格式**: 使用 `/` 分隔多个称呼，如 `Leo / 主人 / 老板`
3. **账号 ID 存储**: 即使只有一个账号，也要用数组存储 `['id123']` 而不是 `'id123'`
4. **YAML 格式**: 使用 `allow_unicode=True` 确保中文正常显示
5. **并发安全**: 读写操作要原子，避免同时修改导致数据丢失
6. **备份习惯**: 重要修改前可以备份文件

## 实际使用场景

### 场景 1: 新用户第一次在 Telegram 联系
```
用户: "你好，我是 Tony"
Ava: (调用 memory map_identity 或执行脚本添加)
→ 在 identity_map.yaml 中添加 tony 的 Telegram 账号
```

### 场景 2: 老用户在飞书上联系了
```
(飞书收到消息，channel=feishu, chat_id=ou_xxx)
Ava: (调用 lookup_by_account 查找)
→ 如果找到，用 display_name 称呼用户
→ 如果没找到，询问用户身份并添加
```

### 场景 3: 用户换了新账号
```
用户: "我换了个 Telegram 号，现在是 99999999"
Ava: (调用 remove_account 删除旧号，add_account 添加新号)
→ 更新 identity_map.yaml
```

## 与 memory 工具的配合

虽然可以直接操作 identity_map.yaml，但推荐使用 `memory` 工具的 `map_identity` 动作：

```bash
# 推荐方式
nanobot memory map_identity --person leo --display_name "Leo / 主人"

# 底层会自动更新 identity_map.yaml
```

这个 skill 主要用于批量操作或复杂场景的自定义脚本。

---

**最后更新**: 2026-02-28
**维护者**: Ava & Leo
