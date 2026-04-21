# Feishu Bridge Feature Matrix

> 每个特性的定义、设计决策、测试覆盖、已知问题。
> 修 bug 或加功能时先更新此文档，再派生测试用例。

## F01: Discovery Commands

**/help, /sessions, /list, /status**

| 项目 | 值 |
|------|-----|
| 设计决策 | D99, D108 |
| 测试用例 | FB-01, FB-02, FB-03, FB-14, FB-15, FB-21 |
| 状态 | active |

**行为**：
- `/help`：未 link → 显示控制面板卡片（绿色 header，[Sessions][New]）；已 link → 显示 session 信息卡片 + 按钮
- `/sessions`：列出所有项目 sessions，带状态标签（terminal/active/idle），可点击 link
- `/list`：显示当前 chat→session 映射
- `/status`：显示 link 的 session 详情

**已知 bug**：无

---

## F02: Connection Management

**/link, /new, /unlink**

| 项目 | 值 |
|------|-----|
| 设计决策 | D99, D102, D112, D113, D114, D117 |
| 测试用例 | FB-04 ~ FB-13 |
| 状态 | active |

**行为**：
- `/link <id|index|name>`：绑定 session 到当前聊天，启动 poll 线程
- `/new <name>`：创建项目目录 + git init + 新 session + 自动 link
- `/unlink`：解除绑定，停止 poll

**已知 bug**：无

---

## F03: Message Forwarding

**飞书文本 → Claude session → 回复卡片**

| 项目 | 值 |
|------|-----|
| 设计决策 | D99, D101, D102, D105, D109, D117 |
| 测试用例 | FB-22, FB-23, FB-24, FB-25 |
| 状态 | active |

**行为**：
- 用户发文本 → Typing reaction → 注入到 Claude session
- Claude 处理中 → poll 检测 working 状态 → 更新卡片 + 切换 reaction
- Claude 完成 → poll 检测 done → 同一卡片变绿 + CheckMark reaction
- Session busy → Alarm reaction + 拒绝提示
- Session 已删除 → CrossMark + auto-unlink

**消息注入状态**：
| 状态 | 含义 | 卡片行为 |
|------|------|----------|
| `injected=True, retained=False` | Claude 正在处理 | 创建蓝色 working 卡片 |
| `injected=True, retained=True` | 消息排队（终端 idle） | 文本通知"已排队" + Hourglass |
| `injected=False` | 注入失败 | CrossMark + 错误提示 |

**已知 bug**：无

---

## F04: Card Lifecycle

**working（蓝）→ done（绿）复用 + TTL**

| 项目 | 值 |
|------|-----|
| 设计决策 | D106, D116 |
| 测试用例 | FB-34, FB-35 |
| 状态 | active |

**行为**：
- 一轮对话 = 一张卡片，working→done 同一张变色
- `_response_cards[session_id]` 追踪 card_message_id
- `_card_done_at[session_id]` 记录 done 时间戳
- 10 分钟 TTL：done 后 10 分钟内复用，超过则新建
- done 路径必须写 `_response_cards`（修复 commit `82bc9c7`）

**已知 bug（已修）**：
- BUG-A：stale card_id → patch 到远处不可见卡片（修：TTL 检查）
- 分卡片：done else 分支没写 `_response_cards` → 每次新建（修：补写）
- done pop `_response_cards` → 新建卡片（修：不 pop）

---

## F05: Reaction Protocol

**用户消息上的 emoji reaction 状态指示**

| 项目 | 值 |
|------|-----|
| 设计决策 | D106, D107, D118 |
| 测试用例 | FB-33 |
| 状态 | active |

**Reaction 映射**：
| 阶段 | emoji_type | 触发 |
|------|-----------|------|
| 收到消息 | Typing | 消息到达 |
| Claude 思考 | THINKING | activity=thinking |
| 工具：Bash | BOMB | activity 包含 bash |
| 工具：Edit | Fire | activity 包含 edit |
| 工具：Grep | SMART | activity 包含 grep |
| 工具：Agent | SHOCKED | activity 包含 agent |
| 其他工具 | STRIVE | activity 其他 |
| 完成 | CheckMark | done |
| 忙碌 | Alarm | busy guard |
| 错误 | CrossMark | 错误 |
| 排队等待 | Hourglass | retained |
| 超时 | SWEAT | stale |

**已知 bug（已修）**：
- BUG-B：done 时 pop `_pending_reactions` → 第二条消息丢失 reaction（修：不 pop，D118）

**已知限制**：重启后 reaction 状态丢失

---

## F06: Card Button Interactions

**卡片上的交互按钮**

| 项目 | 值 |
|------|-----|
| 设计决策 | D104, D106 |
| 测试用例 | FB-26 ~ FB-32 |
| 状态 | active |

**行为**：
- [Sessions] → 显示 session 列表卡片
- [Link] → 绑定 session
- [Stop] → 终止 Claude 进程
- [Unlink] → 解除绑定
- [History] → 显示最近 N 轮对话
- [Compact] → 压缩上下文
- [New] → 显示 /new 用法

**已知 bug**：无

---

## F07: Session Commands

**/stop, /compact, /load, /ls**

| 项目 | 值 |
|------|-----|
| 设计决策 | D99, D101, D102, D113, D115 |
| 测试用例 | FB-16 ~ FB-20 |
| 状态 | active |

**行为**：
- `/stop`：pgrep 找 Claude 进程 → kill
- `/compact`：`claude --resume` + stdin "/compact"
- `/load [N]`：显示最近 N 轮对话（默认 3，最大 10）
- `/ls [path]`：列出项目目录

**已知 bug**：无

---

## F08: Terminal Detection

**/sessions 中终端状态检测**

| 项目 | 值 |
|------|-----|
| 设计决策 | — |
| 测试用例 | FB-44 |
| 状态 | active |

**行为**：
- terminal 图标：/proc/*/cwd 匹配项目目录 AND JSONL mtime < 300s
- active 标签：isActiveInTerminal from API

**已知 bug（已修）**：false terminal status on idle sessions

**已知限制**：project 级检测，非 session 级

---

## F09: Dedup & Persistence

**重启后状态保持 + 响应去重**

| 项目 | 值 |
|------|-----|
| 设计决策 | D103, D108, D109, D114 |
| 测试用例 | FB-36, FB-38, FB-39 |
| 状态 | active |

**行为**：
- `_forward_baselines`：session → messageCount 快照，避免重播
- `_last_delivered_hash`：session → 最后交付内容 hash，避免重复
- 持久化到 `config/feishu-persistence.json`
- 重启后从 persistence 加载

**已知 bug（已修）**：poll threads dead on startup（`_running` 时序）

---

## F10: Stale Session Detection

**长时间 working + 进程不存在的检测**

| 项目 | 值 |
|------|-----|
| 设计决策 | — |
| 测试用例 | FB-37 |
| 状态 | active |

**行为**：
- working 5+ 分钟 + 同一 activity + 进程不存在 → reset to idle + 通知用户

**已知 bug**：无

---

## F11: Resilience & Security

**WS 重连、消息去重、安全校验**

| 项目 | 值 |
|------|-----|
| 设计决策 | D104, D105, D114 |
| 测试用例 | FB-38 ~ FB-43 |
| 状态 | active |

**行为**：
- 非 whitelist chat → 静默忽略
- bot 自身消息 → 忽略（防无限循环）
- msg_id 去重 → `_seen_msg_ids`
- 路径穿越 → 拒绝

**已知 bug**：无

---

## F12: Retained Message Handling

**消息注入到 idle session 的处理**

| 项目 | 值 |
|------|-----|
| 设计决策 | D119 |
| 测试用例 | FB-46 |
| 状态 | active |

**行为**：
- `retained=True` 表示消息写入 pending 文件但终端未消费
- bridge 发送文本通知"消息已排队"+ Hourglass reaction
- **不创建** working 卡片（因为不会立即处理）

**正确体验**：
```
用户发消息 → Hourglass reaction → 文本"⏳ 消息已排队，终端空闲后将自动处理"
终端空闲后读取 pending → Claude 处理 → poll 检测 done → done 卡片
```

**已知 bug（已修）**：retained 也创建 working 卡片 → 卡片永远蓝色（修：区分 injected-only vs retained）

---

## F13: Working Card Timeout

**working 卡片长时间无更新的超时处理**

| 项目 | 值 |
|------|-----|
| 设计决策 | — |
| 测试用例 | FB-47 |
| 状态 | **pending** |

**计划行为**：
- working 卡片创建后，如果 poll 持续 5 分钟看到 idle 且 messageCount 不变
- working 卡片变为黄色 "Claude (waiting)"
- 发送文本通知"响应超时"

**状态**：待实现（依赖 F10 Stale Detection 增强）

---

## 测试用例 → 特性映射

| Case | Feature | P |
|------|---------|---|
| FB-01 | F01 | P0 |
| FB-02 | F01 | P0 |
| FB-03 | F01 | P0 |
| FB-14 | F01 | P1 |
| FB-15 | F01 | P1 |
| FB-21 | F01 | P2 |
| FB-04 | F02 | P0 |
| FB-05 | F02 | P1 |
| FB-06 | F02 | P1 |
| FB-07 | F02 | P2 |
| FB-08 | F02 | P1 |
| FB-09 | F02 | P0 |
| FB-10 | F02, F11 | P0 |
| FB-11 | F02 | P2 |
| FB-12 | F02 | P1 |
| FB-13 | F02 | P0 |
| FB-22 | F03 | P0 |
| FB-23 | F03, F04 | P0 |
| FB-24 | F03 | P0 |
| FB-25 | F03 | P1 |
| FB-26 | F06 | P0 |
| FB-27 | F06 | P0 |
| FB-28 | F06, F07 | P0 |
| FB-29 | F06, F02 | P0 |
| FB-30 | F06 | P1 |
| FB-31 | F06 | P1 |
| FB-32 | F06 | P2 |
| FB-33 | F05 | P0 |
| FB-34 | F04 | P0 |
| FB-35 | F04 | P0 |
| FB-36 | F09 | P1 |
| FB-37 | F10 | P1 |
| FB-38 | F09, F11 | P0 |
| FB-39 | F09, F11 | P1 |
| FB-40 | F11 | P0 |
| FB-41 | F11 | P1 |
| FB-42 | F11 | P1 |
| FB-43 | F11 | P2 |
| FB-44 | F08 | P0 |
| FB-45 | F03 | P0 |
| FB-46 | F12 | P0 |
| FB-47 | F13 | P1 |
