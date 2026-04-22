# Diagnosis: Bridge "不通" — is_live() 粒度错误

**Date**: 2026-04-22
**Session**: 20614045-7d6c-42a9-9564-7e584c47d923, ac52ba00
**Symptom**: Bridge inject 成功（日志 `injected=True`），但无回复，飞书端一直 working card

## 根因

`is_live()` 按 cwd 目录判断是否 busy，粒度太粗——同目录任何 claude 进程都触发 busy 拒绝，导致 Terminal 和飞书无法平行运转。

### 证据链

1. **pts/0 上有交互式 CC**：PID 1302226，`claude --resume 20614045 --dangerously-skip-permissions`，从 08:54 运行至今
2. **Bridge 新 session ac52ba00 inject 被拒**：`error=Session is busy (live Claude process active)`——但 ac52ba00 和 20614045 是不同 session
3. **`is_live()` 原实现只匹配 cwd**：不区分 session ID

### 时序

```
08:54  Terminal CC 启动（pts/0，session 20614045）
12:24  Bridge inject session 20614045 → 0.04s 退出，无输出
12:35  Bridge inject session 20614045 → 成功 poll（len=22）
13:03  Bridge inject session 20614045 → 无 poll result
15:28  Bridge 新 session ac52ba00 inject → "Session is busy"（误杀）
16:47  修复 is_live() 为 session ID 匹配 → 重启验证
```

## 修复（2026-04-22 16:47 已合入）

### `is_live()` 改为 session ID 匹配

**Before** (cwd 匹配，误杀同目录不同 session)：
```python
proc_cwd = os.readlink(f"/proc/{pid}/cwd")
if proc_cwd.rstrip("/") == target_cwd:
    return True
```

**After** (session ID 匹配，精确到 session)：
```python
args = raw.split(b"\x00")
for arg in args:
    if arg.startswith(b"--resume="):
        val = arg[len(b"--resume="):].decode(...)
        if val == self.claude_session_id or val.startswith(target_sid + "-"):
            return True
```

### 行为变化

| 场景 | Before | After |
|------|--------|-------|
| Terminal(CC session A) + Bridge(CC session B) 同 cwd | ❌ Busy | ✅ 放行 |
| Terminal(CC session A) + Bridge(CC session A) 同 session | ❌ Busy | ❌ Busy（正确） |
| Bridge 独占 session | ✅ 放行 | ✅ 放行 |

## 未修复项（待后续）

- `send_message()` 同步版没有 `is_live()` 检查（async 版有）
- `--print --resume` 退出太快（<1s）时无检测/重试

## 关联代码

- `server.py:130` `is_live()` — 已改为 session ID 匹配
- `server.py:244` `send_message()` — 同步版，仍无 `is_live()` 检查
- `server.py:167` Popen `claude --print --resume` — 注入入口
