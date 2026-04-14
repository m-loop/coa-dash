#!/usr/bin/env python3
"""
COA-dash MCP Server — Exposes Claude Code session management as MCP tools.

Wraps the coa-dash HTTP API at localhost:8890, providing:
  - claude_session_create: Create new Claude Code session
  - claude_session_list:   List active sessions
  - claude_chat:           Send message + wait for response (sync)
  - claude_session_history: Get conversation history
  - claude_session_delete:  Delete session

Transport: stdio (for OpenClaw / Claude Code / any MCP client)
"""

import json
import os
import time
import urllib.request
import urllib.error

from fastmcp import FastMCP

COA_DASH = os.environ.get("COA_DASH_URL", "http://localhost:8890")
ALLOWED_CWD = "/home/aegis/vault/projects/"

mcp = FastMCP(
    "coa-dash",
    instructions=(
        "Manage Claude Code sessions via coa-dash. "
        "Use claude_session_list to find sessions, claude_chat to talk to Claude, "
        "and claude_session_create to start new sessions. "
        "Each session is tied to a project directory and maintains conversation context."
    ),
)


# ── Internal Helpers ────────────────────────────────────────────────────

def _api(method: str, path: str, body: dict = None, timeout: int = 10) -> dict:
    """Call coa-dash HTTP API. Returns parsed JSON."""
    url = f"{COA_DASH}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
        except Exception:
            err_body = {"error": str(e)}
        return {"error": f"HTTP {e.code}", "detail": err_body}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def _extract_assistant_text(messages: list, skip_count: int = 0) -> str:
    """Extract text from the FIRST assistant message after skip_count messages.

    Uses message count offset (not content matching) for reliable positioning
    in sessions with thousands of messages where content matching is fragile.
    """
    texts = []
    tools_used = []
    for msg in messages[skip_count:]:
        if msg.get("type") == "assistant":
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                content = [content] if content else []
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text", "").strip():
                    texts.append(c["text"].strip())
                elif c.get("type") == "tool_use":
                    tools_used.append(c.get("name", "?"))
            if texts or tools_used:
                break
        elif msg.get("type") == "result":
            break
    result = "\n".join(texts)
    if tools_used:
        unique_tools = list(dict.fromkeys(tools_used))
        result += f"\n\n[Tools used: {', '.join(unique_tools)}]"
    return result


# ── MCP Tools ───────────────────────────────────────────────────────────

@mcp.tool()
def claude_session_create(
    name: str,
    cwd: str = "",
    model: str = "",
) -> str:
    """Create a new Claude Code session for multi-round conversation.

    Args:
        name: Human-readable session/project name (e.g. "fix-auth-bug")
        cwd: Working directory. Defaults to /home/aegis/vault/projects/{name}
        model: Optional model override (e.g. "sonnet", "opus", "haiku")

    Returns:
        JSON with session_id, status, and project info
    """
    if not cwd:
        cwd = f"{ALLOWED_CWD}{name}"
    if not cwd.startswith(ALLOWED_CWD):
        return json.dumps({"error": f"cwd must be within {ALLOWED_CWD}"})

    body = {"name": name, "cwd": cwd}
    if model:
        body["model"] = model

    result = _api("POST", "/api/claudecode/sessions", body)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def claude_session_list() -> str:
    """List all active Claude Code sessions, sorted by health (idle first).

    Returns:
        JSON with sessions array sorted: idle > starting > working > error.
        Each session includes id, name, status, messageCount, projectName.
    """
    result = _api("GET", "/api/claudecode/sessions")
    sessions = result.get("sessions", [])

    status_order = {"idle": 0, "starting": 1, "working": 2, "error": 3}
    sessions.sort(key=lambda s: status_order.get(s.get("status", ""), 4))

    return json.dumps({"sessions": sessions, "total": len(sessions)}, ensure_ascii=False)


@mcp.tool()
def claude_chat(
    session_id: str,
    content: str,
    timeout: int = 120,
) -> str:
    """Send a message to a Claude Code session and wait for the full response.

    Blocks until Claude responds (up to timeout seconds). Use for multi-round
    conversations — session context is preserved across calls.

    Args:
        session_id: The session ID (8-char hex, e.g. "abc12345")
        content: The message to send
        timeout: Max seconds to wait for response (default 120)

    Returns:
        JSON with "response" (Claude's text), "status", "duration_seconds"
    """
    # Check session exists and get pre-send message count
    info = _api("GET", f"/api/claudecode/sessions/{session_id}")
    if "error" in info:
        return json.dumps({"error": f"Session not found: {session_id}", "detail": info})

    status = info.get("status", "unknown")
    if status == "working":
        return json.dumps({
            "error": "Session is busy",
            "status": "working",
            "activity": info.get("activity", ""),
            "hint": "Wait and retry, or use a different session",
        })

    pre_send_count = info.get("messageCount", 0)
    if status == "error":
        # Allow sending to error sessions (may recover), but include warning
        pass

    # Send message
    send_result = _api(
        "POST",
        f"/api/claudecode/sessions/{session_id}/message",
        {"content": content},
        timeout=timeout + 10,
    )
    if "error" in send_result:
        return json.dumps({"error": "Send failed", "detail": send_result})

    # Poll until Claude finishes
    t0 = time.time()
    final_status = "working"
    while time.time() - t0 < timeout:
        time.sleep(2)
        info = _api("GET", f"/api/claudecode/sessions/{session_id}")
        final_status = info.get("status", "unknown")
        if final_status not in ("working", "starting"):
            break

    elapsed = round(time.time() - t0, 1)

    if final_status == "working":
        return json.dumps({
            "error": "Timeout",
            "message": f"Claude did not respond within {timeout}s",
            "elapsed": elapsed,
            "hint": "The session may still be processing. Try claude_session_history later.",
        })

    # Extract response — use message count to skip past pre-send messages
    history = _api("GET", f"/api/claudecode/sessions/{session_id}/history?limit=50")
    messages = history.get("messages", [])

    # history returns most recent N messages; calculate how many to skip
    total_in_history = len(messages)
    # The history endpoint returns the latest messages, so if pre_send_count < total,
    # the new messages start at offset (total_in_history - new_msg_count)
    new_msg_count = info.get("messageCount", 0) - pre_send_count
    skip = max(0, total_in_history - new_msg_count)

    response_text = _extract_assistant_text(messages, skip_count=skip)

    if not response_text:
        response_text = f"[No text response. Status: {final_status}]"

    return json.dumps({
        "response": response_text,
        "status": final_status,
        "duration_seconds": elapsed,
        "session_id": session_id,
    }, ensure_ascii=False)


@mcp.tool()
def claude_session_history(
    session_id: str,
    limit: int = 20,
) -> str:
    """Get conversation history for a Claude Code session.

    Returns formatted conversation with role and content for each message.

    Args:
        session_id: The session ID
        limit: Number of recent messages to return (default 20)

    Returns:
        JSON with messages array: [{role, content}, ...]
    """
    result = _api("GET", f"/api/claudecode/sessions/{session_id}/history?limit={limit}")
    if "error" in result:
        return json.dumps({"error": result["error"]})

    messages = result.get("messages", [])
    formatted = []
    for msg in messages:
        msg_type = msg.get("type", "")
        if msg_type == "user":
            content = msg.get("message", {}).get("content", "")
            if isinstance(content, list):
                texts = []
                for c in content:
                    if isinstance(c, dict) and c.get("text"):
                        texts.append(c["text"])
                content = " ".join(texts)
            if isinstance(content, str) and content.strip():
                formatted.append({"role": "user", "content": content.strip()[:500]})

        elif msg_type == "assistant":
            content = msg.get("message", {}).get("content", [])
            if isinstance(content, list):
                texts = []
                tools = []
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text" and c.get("text", "").strip():
                        texts.append(c["text"].strip())
                    elif c.get("type") == "tool_use":
                        tools.append(c.get("name", "?"))
                text = "\n".join(texts)
                if tools:
                    text += f"\n[Tools: {', '.join(dict.fromkeys(tools))}]"
                if text.strip():
                    formatted.append({"role": "assistant", "content": text.strip()[:500]})

    return json.dumps({
        "messages": formatted,
        "total": len(formatted),
        "session_id": session_id,
    }, ensure_ascii=False)


@mcp.tool()
def claude_session_delete(session_id: str) -> str:
    """Delete a Claude Code session and clean up resources.

    Args:
        session_id: The session ID to delete

    Returns:
        JSON with success confirmation
    """
    result = _api("DELETE", f"/api/claudecode/sessions/{session_id}")
    return json.dumps(result, ensure_ascii=False)


# ── Entry Point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
