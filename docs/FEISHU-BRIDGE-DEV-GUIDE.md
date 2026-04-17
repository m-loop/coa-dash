# Feishu-Claude Bridge: 面向 Claude Code 的开发指引

> 本文档面向 Claude Code（或任何 AI 编码 agent），目的是在一台全新电脑上从零重建此系统。
> 包含：架构设计、实现细节、踩过的坑、以及关键决策的 why。

---

## 1. 这是什么

一个飞书 Bot，让用户在飞书聊天里直接和 Claude Code 交互。用户发消息 → Bot 转发给 Claude Code → Claude 回复 → Bot 把回复发回飞书（以卡片形式）。

```
飞书用户 ←→ 飞书平台 (WebSocket) ←→ feishu-bridge.py ←→ coa-dash server.py ←→ Claude CLI
```

### 组件

| 文件 | 角色 | 运行方式 |
|------|------|---------|
| `src/feishu-bridge.py` | 飞书 Bot：WS 监听、命令处理、轮询、卡片/reaction | systemd: feishu-bridge.service |
| `src/server.py` | Session 管理：创建/发送/流式输出/历史 | systemd: coa-dash.service |
| Claude CLI | `claude --print --output-format stream-json --resume` | 每条消息一个子进程 |

---

## 2. 从零搭建

### 2.1 前置条件

```bash
# Python 3.10+
python3 --version

# Claude Code CLI (必须)
claude --version

# 飞书 SDK
pip install lark-oapi requests

# systemd 用户目录
mkdir -p ~/.config/systemd/user
```

### 2.2 飞书应用配置

1. 去 [飞书开放平台](https://open.feishu.cn/) 创建应用
2. 开启以下能力：
   - **机器人** (Bot)
   - **WebSocket 长连接**（不是 HTTP 回调，用 WS 更稳定、不需要公网）
3. 权限 scope：
   - `im:message` / `im:message:send_as_bot` — 收发消息
   - `im:message.reaction` — 添加/替换 emoji reaction
4. 获取 `app_id` 和 `app_secret`

### 2.3 配置文件

**`config/feishu-bridge.json`**（手动创建）：
```json
{
  "app_id": "cli_xxxxx",
  "app_secret": "xxxxx",
  "mode": "dm",
  "coa_dash_url": "http://localhost:8890"
}
```

**`config/feishu-persistence.json`**（运行时自动生成，不要手动编辑）

### 2.4 启动

```bash
# 启动 coa-dash server
systemctl --user start coa-dash

# 启动 bridge
systemctl --user start feishu-bridge

# 查看日志
journalctl --user -u feishu-bridge -f
journalctl --user -u coa-dash -f
```

---

## 3. 核心设计

### 3.1 消息流（用户发消息 → 收到回复）

```
1. 用户在飞书发消息
2. 飞书 WS 推送事件到 bridge (_on_message_receive)
3. Bridge 添加 ⌨️ reaction，记录 msg_id
4. Bridge POST 到 coa-dash: /api/claudecode/sessions/{id}/message
5. coa-dash spawn Claude CLI: claude --resume --print --output-format stream-json
6. Claude 流式输出 JSON → server 逐行解析 → 更新 activity
7. Bridge poll loop (2-6s) 检测变化：
   a. Activity 变化 → 更新蓝色 working 卡片 + 切换 reaction emoji
   b. messageCount 增加 → 获取历史 → 提取 assistant 文本
8. 完成：发绿色 done 卡片 + ✅ reaction
```

### 3.2 Session 管理

每个飞书聊天 link 到一个 Claude Code session。Session 包含：
- `claude_session_id`: Claude 的内部 session ID（用于 `--resume`）
- `messages[]`: 完整消息历史（内存 + JSONL buffer 文件）
- `status`: idle / working / starting / error
- `current_activity`: "Tool: Grep" / "Thinking..." / "Ready"

### 3.3 Poll Loop 状态机

每个 link 的 session 有一个独立的 poll 线程：

```
START → 加载 baseline
  │
  ├─ GET session info → 提取 status, activity, messageCount
  │
  ├─ Working? → 更新 reaction + 卡片（有节流）
  │   └─ Stale 5min + process dead? → Reset session
  │
  ├─ messageCount > baseline? → 新消息
  │   ├─ 获取 history, 提取 assistant text
  │   ├─ Working → 更新卡片显示 partial text
  │   └─ Done → 发 done 卡片, 更新 baseline, 保存 persistence
  │
  └─ Sleep (2s working / 6s idle) → loop
```

### 3.4 Reaction 协议

| 阶段 | Emoji | 飞书 emoji_type |
|------|-------|----------------|
| 收到 | ⌨️ | Typing |
| 思考 | 🧠 | THINKING |
| Grep/Search | 💡 | SMART |
| Read | 📌 | Pin |
| Write/Edit | 🔥 | Fire |
| Bash | 💣 | BOMB |
| 完成 | ✅ | CheckMark |
| Busy | ⏰ | Alarm |
| Error | ❌ | CrossMark |

**重要**: 飞书 API 的 emoji_type 有白名单。`MEMO`、`OPEN_BOOK`、`SHOCKED` 都会静默失败。上线前必须验证每个 emoji_type。

### 3.5 卡片协议

| 阶段 | 颜色 | 标题 | 更新方式 |
|------|------|------|---------|
| Working | 蓝色 | "Claude (working)" | PatchMessage |
| Done | 绿色 | "Claude" | 新卡片 |
| Error | 红色 | "Claude" | 新卡片 |

---

## 4. 关键实现细节

### 4.1 Claude CLI 调用

```python
proc = subprocess.Popen(
    ["claude", "--resume", claude_session_id,
     "--print", "--output-format", "stream-json"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,  # 必须！否则 >64KB stderr 会死锁
    cwd=session_cwd,
)

# 写入消息后关闭 stdin
proc.stdin.write(content.encode())
proc.stdin.close()

# 流式读取 stdout（不是 communicate()！communicate 会缓冲全部输出）
for line in proc.stdout:
    data = json.loads(line)
    # 处理每行 JSON...
```

**坑 1: `stderr=PIPE` 死锁**。Claude CLI 可能输出大量 stderr（>64KB），如果用 `PIPE` 不读取就会阻塞。必须用 `stderr=DEVNULL`。

**坑 2: `communicate()` 不适合流式**。`communicate()` 会等进程结束才返回所有输出。要用 `for line in proc.stdout` 逐行读取。

### 4.2 并发消息防护（P1 Fix）

```python
def send_claude_message(session_id, content):
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if session.status not in ["idle", "starting", "error"]:
            return {"error": "busy"}
        # 原子操作：检查+设置在同一个 lock 内
        session.status = "working"
    # lock 外启动异步进程
    session.send_message_async(content)
```

**关键**: `status` 的检查和设置必须在同一个 lock 内完成，否则两个请求可能同时通过检查。

### 4.3 内容去重

飞书 WS 会重复推送同一条消息（已确认），bridge 重启也会导致重复投递。三层防护：

1. **msg_id 去重**: WS 推送的事件有 `msg_id`，相同 `msg_id` 在 5 分钟窗口内只处理一次
2. **内容 hash 去重**: 每次投递记录 MD5 hash，相同内容不发第二张卡片
3. **Working 卡片节流**: 只有内容变化才更新卡片，避免 API spam

```python
# msg_id 去重（防 WS 重放）
if msg_id in self._seen_msg_ids:
    return  # 跳过

# 内容 hash 去重（防重启后重复投递）
content_hash = hashlib.md5(text.encode()).hexdigest()[:12]
if content_hash == self._last_delivered_hash.get(session_id):
    return  # 跳过

# Working 卡片节流（防 API spam）
if last_assistant_text != self._last_working_text.get(session_id):
    # 只在内容变化时更新
```

### 4.4 Persistence

以下状态跨重启持久化：

```json
{
  "chat_session_map": {"chat_id": "session_id"},
  "forward_baselines": {"session_id": messageCount},
  "last_delivered_hash": {"session_id": "md5hash"},
  "mode": "dm"
}
```

以下状态仅内存（重启丢失）：
- `_response_cards` — working 卡片 ID（重启后蓝色卡片卡住）
- `_pending_reactions` — reaction 状态
- `_current_reactions` — 当前 reaction ID
- `_last_working_text` — working 卡片上次内容

### 4.5 /load 命令

加载最近 N 轮对话到飞书卡片。关键：Claude 的 stream-json 格式中，`type="user"` 的消息可能是 `tool_result`（没有用户文本），需要跳过：

```python
while j >= 0:
    um = messages[j]
    if um.get("type") == "user":
        candidate = extract_text(um)
        if candidate:
            user_text = candidate
            break
        # tool_result 也是 type="user" 但没有文本，继续往前找
    j -= 1
```

---

## 5. 踩过的坑（按严重度排序）

### 🔴 Critical

| ID | 问题 | 原因 | 修复 |
|----|------|------|------|
| B6 | `/stop` 后 session 死锁 | kill 进程但不 reset server 的 status | `/stop` 需要额外调 API reset status |
| B3/B4 | `/new` 路径注入 | bridge 侧 `os.makedirs` 在 server 校验前执行 | bridge 侧也加 realpath 校验 |
| B12 | 无鉴权 | 任何人发消息 = 代码执行 | 需要白名单 chat_id |
| P1 | 并发消息竞争 | status 检查和设置不在同一个 lock | 原子 check+set |
| P2 | stderr 死锁 | `stderr=PIPE` + >64KB 输出 | `stderr=DEVNULL` |
| WS-DUP | WS 重复推送 | 飞书平台行为，同一条消息推 3 次 | msg_id 去重 |
| OLD-DELIVER | 重启后投递老内容 | baseline 未持久化 + fallback 搜全量历史 | 删除 full history fallback + 持久化 hash |

### 🟡 Medium

| ID | 问题 | 状态 |
|----|------|------|
| B1 | Busy 时无文本反馈，只有 ⏰ | 待修 |
| B2 | Baseline 在 POST 后设置 | 待修 |
| B5 | 同 session 多 chat link 重复投递 | 待修 |
| B7 | Claude 子进程孤儿 | 待修 |
| B9 | 重启后 working 卡片卡住 | 待修 |
| S9 | session 删除后 poll 404 循环 | 待修 |
| MEM | messages 列表无限增长 | 待修 |
| C1 | 无效 emoji_type 静默失败 | 已修 |

### 🟢 已修复

| 修复 | 描述 |
|------|------|
| 流式 stdout | `communicate()` → `for line in proc.stdout` |
| P9 线程安全 | Lock → RLock |
| 内容去重 | MD5 hash + 持久化 |
| WS 去重 | msg_id 5 分钟窗口 |
| Working 卡片节流 | 只在内容变化时更新 |
| /load Q 为空 | 跳过 tool_result user messages |
| /load 单卡片 | 合并所有 rounds 为一张卡片 |
| /sessions 排序 | 按时间倒序 + 相对时间显示 |
| Emoji 修复 | MEMO/OPEN_BOOK → Pin/Fire |

---

## 6. 新机器部署 Checklist

```bash
# 1. 克隆代码
git clone https://github.com/m-loop/coa-dash.git
cd coa-dash

# 2. 安装依赖
pip install lark-oapi requests

# 3. 确认 Claude CLI 可用
claude --version

# 4. 配置飞书应用
#    - 创建应用，开启 Bot + WebSocket
#    - 配置 scope: im:message, im:message.reaction
cp config/feishu-bridge.json.example config/feishu-bridge.json
# 编辑填入 app_id, app_secret

# 5. 安装 systemd 服务
./scripts/install.sh
# 或手动：
# cp systemd/coa-dash.service ~/.config/systemd/user/
# cp systemd/feishu-bridge.service ~/.config/systemd/user/

# 6. 启动
systemctl --user start coa-dash
systemctl --user start feishu-bridge

# 7. 验证
journalctl --user -u feishu-bridge -f  # 应该看到 WS connected
curl http://localhost:8890/api/agents    # 应该返回 JSON

# 8. 在飞书测试
#    给 bot 发 /help → 应该收到命令列表
#    发 /sessions → 应该显示可用 session
#    发 /link <id> → link 到一个 session
#    发文字 → 应该收到卡片回复
```

---

## 7. 文件结构

```
coa-dash/
├── src/
│   ├── server.py           # HTTP server, session 管理
│   ├── feishu-bridge.py    # 飞书 Bot 主程序
│   └── index.html           # Dashboard UI
├── config/
│   ├── config.json          # Dashboard 配置
│   ├── feishu-bridge.json   # Bridge 配置 (app_id, app_secret)
│   └── feishu-persistence.json  # 运行时状态 (自动生成)
├── systemd/
│   ├── coa-dash.service
│   └── feishu-bridge.service
├── docs/
│   ├── BRIDGE-DESIGN-AUDIT.md  # 设计 & 审计文档
│   └── FEISHU-BRIDGE-DEV-GUIDE.md  # 本文档
└── scripts/
    └── install.sh
```

---

## 8. E2E 测试

无需飞书参与，可直接通过 API 测试核心功能：

```bash
# 创建 session
SID=$(curl -s -X POST http://localhost:8890/api/claudecode/sessions \
  -H "Content-Type: application/json" \
  -d '{"name":"test","cwd":"/home/aegis/vault/projects/coa-dash"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['id'])")

# 发消息 & 等完成
curl -s -X POST "http://localhost:8890/api/claudecode/sessions/$SID/message" \
  -H "Content-Type: application/json" \
  -d '{"content":"Say exactly: TEST_OK"}'

# 等 idle
while [ "$(curl -s http://localhost:8890/api/claudecode/sessions/$SID | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")" != "idle" ]; do sleep 2; done

# 读回复
curl -s "http://localhost:8890/api/claudecode/sessions/$SID/history?limit=5" \
  | python3 -c "import sys,json; [print(x['text'][:200]) for m in json.load(sys.stdin)['messages'] if m['type']=='assistant' for x in m.get('message',{}).get('content',[]) if isinstance(x,dict) and x.get('type')=='text']"

# 清理
curl -s -X DELETE "http://localhost:8890/api/claudecode/sessions/$SID"
```

完整测试脚本见仓库根目录或 `/tmp/bridge-e2e-test.py`。

---

## 9. 开发建议

### 优先修什么

1. **B6 `/stop` 死锁** — 5 行代码，加一个 PUT status 调用
2. **B3/B4 路径注入** — bridge 侧加 realpath 校验
3. **B12 鉴权** — chat_id 白名单，防任意代码执行
4. **B1 Busy 反馈** — 发文字 "会话忙碌，请稍后重试"

### 值得做的架构改进

- **消息队列**: busy 时不丢弃，排队等 idle 后处理
- **优雅停机**: SIGTERM handler，kill 子进程 + 保存状态
- **消息驱逐**: messages 列表保留最近 N 条，防止 OOM
- **单卡片设计**: 蓝色 working 卡片变绿色 done（而不是发两张）

### 不要做的事

- 不要用 `proc.communicate()` — 用流式 stdout
- 不要用 `stderr=PIPE` — 用 DEVNULL
- 不要在 poll loop 里搜全量历史 — 只处理 baseline 之后的消息
- 不要信任飞书 WS 不重复推送 — 必须 msg_id 去重
- 不要假设 emoji_type 有效 — 必须验证（MEMO, OPEN_BOOK 都无效）
