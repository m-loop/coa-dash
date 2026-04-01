#!/usr/bin/env python3
"""
COA-dash - Command Orchestration Agent Dashboard
Mobile-first, touch-first dashboard for AI agent orchestration
"""

import fcntl
import json
import os
import re
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")


def load_config():
    """Load config from JSON file with environment variable overrides.

    Security-sensitive values can be overridden via environment variables:
    - OPENCLAW_GATEWAY_TOKEN: Overrides config.gateway.token
    - COA_ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Environment variable overrides for security-sensitive values
    if os.environ.get("OPENCLAW_GATEWAY_TOKEN"):
        if "gateway" not in config:
            config["gateway"] = {}
        config["gateway"]["token"] = os.environ["OPENCLAW_GATEWAY_TOKEN"]

    if os.environ.get("COA_ALLOWED_ORIGINS"):
        config["allowedOrigins"] = os.environ["COA_ALLOWED_ORIGINS"].split(",")

    return config


class AgentConfigCache:
    """Cache for agent configuration from openclaw.json (D55-D56)"""

    OPENCLAW_CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")

    def __init__(self, ttl=60):
        self._agents_list = None
        self._last_read = 0
        self._ttl = ttl
        self._cached = False

    def get_agents_list(self):
        """Get configured agent IDs from openclaw.json with TTL cache"""
        now = int(time.time() * 1000)

        if self._agents_list is not None and (now - self._last_read) < (
            self._ttl * 1000
        ):
            self._cached = True
            return self._agents_list

        self._cached = False
        self._agents_list = self._read_openclaw_config()
        self._last_read = now
        return self._agents_list

    def _read_openclaw_config(self):
        """Read agent list from openclaw.json"""
        if not os.path.exists(self.OPENCLAW_CONFIG_PATH):
            return None

        try:
            with open(self.OPENCLAW_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            agents_config = data.get("agents", {})
            agents_list = agents_config.get("list", [])
            return [a.get("id") for a in agents_list if a.get("id")]
        except Exception as e:
            print(f"[ERROR] Failed to read openclaw.json: {e}")
            return None

    def invalidate(self):
        """Clear cache (D61: for force refresh)"""
        self._agents_list = None
        self._last_read = 0
        self._cached = False

    def is_cached(self):
        """Check if last result was from cache"""
        return self._cached


agent_cache = AgentConfigCache()


def get_agents(config, force_refresh=False):
    """Get agent status from openclaw.json config (D55-D62)"""
    agents = []
    error = None

    if force_refresh:
        agent_cache.invalidate()

    configured_agents = agent_cache.get_agents_list()
    cached = agent_cache.is_cached()

    if configured_agents is None:
        return {
            "agents": [],
            "gateway": {
                "healthy": False,
                "activeAgents": 0,
                "lastChecked": int(time.time() * 1000),
            },
            "meta": {
                "configSource": None,
                "agentCount": 0,
                "cached": cached,
            },
            "error": "openclaw.json not found or invalid",
        }

    for agent_id in configured_agents:
        try:
            session_data = get_session_info(config, agent_id)
            agents.append(
                {
                    "id": agent_id,
                    "displayName": agent_id.capitalize(),
                    "status": derive_status(True, session_data),
                    "enabled": True,
                    "lastActivityAt": session_data.get("updatedAt", 0),
                    "lastActivityAgo": format_time_ago(
                        session_data.get("updatedAt", 0)
                    ),
                    "model": session_data.get("model", "unknown"),
                    "sessionCount": session_data.get("sessionCount", 0),
                    "currentSessionId": session_data.get("currentSessionId", ""),
                    "lastChannel": session_data.get("lastChannel", ""),
                    "currentActivity": session_data.get("currentActivity", ""),
                }
            )
        except Exception as e:
            print(f"[WARN] Failed to get session for {agent_id}: {e}")
            agents.append(
                {
                    "id": agent_id,
                    "displayName": agent_id.capitalize(),
                    "status": "offline",
                    "enabled": True,
                    "lastActivityAt": 0,
                    "lastActivityAgo": "never",
                    "model": "unknown",
                    "sessionCount": 0,
                    "currentSessionId": "",
                    "lastChannel": "",
                    "currentActivity": "",
                }
            )

    active_count = sum(1 for a in agents if a.get("lastActivityAt", 0) > 0)

    return {
        "agents": agents,
        "gateway": {
            "healthy": len(agents) > 0,
            "activeAgents": active_count,
            "lastChecked": int(time.time() * 1000),
        },
        "meta": {
            "configSource": "openclaw.json",
            "agentCount": len(agents),
            "cached": cached,
        },
        "error": None,
    }


def get_session_info(config, agent_id):
    """Get session info from sessions.json"""
    sessions_path = os.path.expanduser(config["agents"]["sessionsPath"])
    session_file = os.path.join(sessions_path, agent_id, "sessions", "sessions.json")

    if not os.path.exists(session_file):
        return {}

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sessions = list(data.values()) if isinstance(data, dict) else []
        if not sessions:
            return {"sessionCount": 0}

        latest = max(sessions, key=lambda s: s.get("updatedAt", 0), default={})

        # D53: Extract lastChannel for current activity display
        last_channel = latest.get("lastChannel", "")
        current_activity = format_activity(last_channel)

        return {
            "updatedAt": latest.get("updatedAt", 0),
            "model": latest.get("model", "unknown"),
            "currentSessionId": latest.get("sessionId", ""),
            "sessionCount": len(sessions),
            "lastChannel": last_channel,
            "currentActivity": current_activity,
        }
    except:
        return {"sessionCount": 0}


def derive_status(enabled, session_data):
    """Derive agent status from enabled state and session activity"""
    if not enabled:
        return "offline"

    updated_at = session_data.get("updatedAt", 0)
    if updated_at == 0:
        return "offline"

    now = int(time.time() * 1000)
    busy_threshold = 30 * 1000
    idle_threshold = 5 * 60 * 1000

    age = now - updated_at

    if age < busy_threshold:
        return "busy"
    elif age < idle_threshold:
        return "online"
    else:
        return "idle"


def format_time_ago(timestamp):
    """Format timestamp as human-readable time ago"""
    if not timestamp:
        return "never"

    now = int(time.time() * 1000)
    diff = now - timestamp

    if diff < 60000:
        return "just now"
    elif diff < 3600000:
        return f"{diff // 60000} min ago"
    elif diff < 86400000:
        return f"{diff // 3600000} hr ago"
    else:
        return f"{diff // 86400000} days ago"


def format_activity(channel):
    """Format channel as human-readable activity (D53)"""
    if not channel:
        return ""

    activity_map = {
        "webchat": "在 WebChat",
        "feishu": "在飞书对话",
        "discord": "在 Discord",
        "slack": "在 Slack",
    }
    return activity_map.get(channel.lower(), f"在 {channel}")


def get_gateway_status(config):
    """Check gateway health"""
    import urllib.request
    import urllib.error

    gateway = config.get("gateway", {})
    healthz_url = gateway.get(
        "healthz", f"http://localhost:{gateway.get('port', 18789)}/healthz"
    )
    readyz_url = gateway.get(
        "readyz", f"http://localhost:{gateway.get('port', 18789)}/readyz"
    )

    result = {
        "healthy": False,
        "ready": False,
        "healthz": {"status": "unknown"},
        "readyz": {"status": "unknown"},
    }

    try:
        req = urllib.request.Request(healthz_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            result["healthz"] = {"status": "ok", "timestamp": int(time.time() * 1000)}
            result["healthy"] = True
    except Exception as e:
        result["healthz"] = {"status": "error", "error": str(e)}

    try:
        req = urllib.request.Request(readyz_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            result["readyz"] = {"status": "ok", "checks": []}
            result["ready"] = True
    except Exception as e:
        result["readyz"] = {"status": "error", "error": str(e)}

    return result


def get_sessions(config, agent_filter="all", type_filter="all"):
    """Get live sessions from sessions.json (D64-D65)"""
    now = int(time.time() * 1000)
    sessions = []
    counts = {"total": 0, "feishu": 0, "webchat": 0, "other": 0}

    # Get agents to query
    configured_agents = agent_cache.get_agents_list()
    if configured_agents is None:
        return {"sessions": [], "counts": counts, "error": "openclaw.json not found"}

    if agent_filter != "all" and agent_filter in configured_agents:
        agents_to_query = [agent_filter]
    else:
        agents_to_query = configured_agents

    for agent_id in agents_to_query:
        agent_sessions = get_all_sessions_for_agent(config, agent_id)

        for session_key, session_data in agent_sessions:
            channel = session_data.get("lastChannel")
            updated_at = session_data.get("updatedAt", 0)
            ended_at = session_data.get("endedAt")

            # D65: Live Session = has channel + updated within 7d
            if not channel:
                continue

            age_ms = now - updated_at
            if age_ms > 24 * 3600000:  # 24 hours (D73)
                continue

            # Extract session type
            parts = session_key.split(":")
            session_type = parts[2] if len(parts) > 2 else "unknown"

            # Apply type filter
            if type_filter != "all" and session_type != type_filter:
                continue

            # Determine status
            if not ended_at and age_ms < 3600000:  # 1 hour
                status = "online"
            elif not ended_at and age_ms < 86400000:  # 1 day
                status = "idle"
            else:
                status = "offline"

            # D78: Get additional session details
            session_file_path = session_data.get("sessionFile", "")
            job_name = get_session_job_name(session_file_path)
            model = session_data.get("model", "")
            runtime_ms = session_data.get("runtimeMs", 0)
            chat_type = session_data.get("chatType", "direct")
            started_at = session_data.get("startedAt", 0)

            sessions.append(
                {
                    "sessionId": session_data.get("sessionId", session_key),
                    "agentId": agent_id,
                    "type": session_type,
                    "channel": channel,
                    "status": status,
                    "updatedAt": updated_at,
                    "updatedAtAgo": format_time_ago(updated_at),
                    "endedAt": ended_at,
                    "model": model,
                    "jobName": job_name,
                    "runtimeMs": runtime_ms,
                    "runtimeFormatted": format_duration(runtime_ms),
                    "chatType": chat_type,
                    "startedAt": started_at,
                    "startedAtAgo": format_time_ago(started_at),
                }
            )

            # Update counts
            counts["total"] += 1
            if channel == "feishu":
                counts["feishu"] += 1
            elif channel == "webchat":
                counts["webchat"] += 1
            else:
                counts["other"] += 1

    # Sort by updatedAt descending
    sessions.sort(key=lambda s: s.get("updatedAt", 0), reverse=True)

    return {"sessions": sessions, "counts": counts, "error": None}


def get_all_sessions_for_agent(config, agent_id):
    """Get all sessions for an agent as list of (key, value) tuples"""
    sessions_path = os.path.expanduser(config["agents"]["sessionsPath"])
    session_file = os.path.join(sessions_path, agent_id, "sessions", "sessions.json")

    if not os.path.exists(session_file):
        return []

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return list(data.items())
        return []
    except:
        return []


def get_session_job_name(session_file_path):
    """Extract job name from session JSONL file (D78)"""
    if not session_file_path or not os.path.exists(session_file_path):
        return ""

    try:
        with open(session_file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    if d.get("type") == "message":
                        msg = d.get("message", {})
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and "text" in c:
                                    try:
                                        text_data = json.loads(c["text"])
                                        jobs = text_data.get("jobs", [])
                                        if jobs and len(jobs) > 0:
                                            return jobs[0].get("name", "")
                                    except:
                                        pass
                except:
                    pass
    except:
        pass
    return ""


def format_duration(ms):
    """Format milliseconds as human-readable duration"""
    if not ms:
        return "-"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def get_tasks(config, filters=None):
    """Get tasks from tasks.jsonl"""
    tasks_path = config["tasks"]["path"]
    tasks = []

    if not os.path.exists(tasks_path):
        return {"tasks": [], "stats": {}, "error": "Tasks file not found"}

    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        task = json.loads(line)

                        if filters:
                            if (
                                filters.get("status")
                                and task.get("status") != filters["status"]
                            ):
                                continue
                            if (
                                filters.get("priority")
                                and task.get("priority") != filters["priority"]
                            ):
                                continue
                            if filters.get("search"):
                                search = filters["search"].lower()
                                if (
                                    search not in task.get("title", "").lower()
                                    and search not in task.get("notes", "").lower()
                                ):
                                    continue

                        task["children"] = []
                        tasks.append(task)
                    except:
                        pass
    except Exception as e:
        return {"tasks": [], "stats": {}, "error": str(e)}

    tasks_by_id = {t["task_id"]: t for t in tasks}
    root_tasks = []

    for task in tasks:
        parent_id = task.get("parent_id")
        if parent_id and parent_id in tasks_by_id:
            tasks_by_id[parent_id]["children"].append(task)
        else:
            root_tasks.append(task)

    stats = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.get("status") == "已完成"),
        "pending": sum(1 for t in tasks if t.get("status") == "待处理"),
        "inProgress": sum(1 for t in tasks if t.get("status") == "进行中"),
        "blocked": sum(1 for t in tasks if t.get("status") == "挂起"),
    }

    return {"tasks": root_tasks, "stats": stats, "error": None}


def with_jsonl_lock(file_path, read_modify_write_func):
    """Execute a read-modify-write operation with exclusive file lock.

    Prevents race conditions when multiple requests modify tasks.jsonl.
    """
    with open(file_path, "r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            result = read_modify_write_func(f)
            f.flush()
            return result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def update_task_priority(config, task_id, priority):
    """Update task priority in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["priority"] = priority
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "priority": priority}}


def update_task_status(config, task_id, status):
    """Update task status in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["status"] = status
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "status": status}}


def update_task_status_batch(config, task_ids, status):
    """Update multiple tasks status in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        updated_count = 0
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") in task_ids:
                        task["status"] = status
                        updated_count += 1
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "updated": updated_count}

    return with_jsonl_lock(tasks_path, modify)


def delete_task(config, task_id):
    """Delete task from tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        found = True
                        continue  # Skip this line (delete it)
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "deleted": True}


def update_task_assignee(config, task_id, assignee):
    """Update task assignee in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["assignee"] = assignee if assignee else ""
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "assignee": assignee}}


def get_stats(config):
    """Get statistics for dashboard (Phase 2)

    Returns agent utilization, task throughput, and session activity.
    """
    now = int(time.time() * 1000)
    one_day_ms = 24 * 60 * 60 * 1000
    one_week_ms = 7 * one_day_ms

    # Agent stats from get_agents
    agents_data = get_agents(config)
    agents = agents_data.get("agents", [])

    agent_counts = {"online": 0, "busy": 0, "idle": 0, "offline": 0}
    for a in agents:
        status = a.get("status", "offline")
        if status in agent_counts:
            agent_counts[status] += 1

    total_agents = len(agents)
    active_agents = agent_counts["online"] + agent_counts["busy"]
    utilization = round((active_agents / total_agents * 100), 1) if total_agents > 0 else 0

    # Task stats from get_tasks
    tasks_data = get_tasks(config)
    tasks = []
    tasks_path = config["tasks"]["path"]

    if os.path.exists(tasks_path):
        with open(tasks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        tasks.append(json.loads(line))
                    except:
                        pass

    task_counts = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.get("status") == "已完成"),
        "pending": sum(1 for t in tasks if t.get("status") == "待处理"),
        "inProgress": sum(1 for t in tasks if t.get("status") == "进行中"),
        "blocked": sum(1 for t in tasks if t.get("status") == "挂起"),
    }

    completion_rate = round((task_counts["completed"] / task_counts["total"] * 100), 1) if task_counts["total"] > 0 else 0

    # Count completed today (by checking notes for completion timestamp)
    # For simplicity, we estimate based on recent activity
    completed_today = 0
    completed_week = 0

    # Session stats
    sessions_data = get_sessions(config)
    sessions = sessions_data.get("sessions", [])

    session_counts = {"total": len(sessions), "feishu": 0, "webchat": 0, "other": 0}
    total_runtime = 0

    for s in sessions:
        channel = s.get("channel", "other")
        if channel == "feishu":
            session_counts["feishu"] += 1
        elif channel == "webchat":
            session_counts["webchat"] += 1
        else:
            session_counts["other"] += 1
        total_runtime += s.get("runtimeMs", 0)

    return {
        "agents": {
            "total": total_agents,
            "online": agent_counts["online"],
            "busy": agent_counts["busy"],
            "idle": agent_counts["idle"],
            "offline": agent_counts["offline"],
            "utilizationPercent": utilization,
        },
        "tasks": {
            "total": task_counts["total"],
            "completed": task_counts["completed"],
            "pending": task_counts["pending"],
            "inProgress": task_counts["inProgress"],
            "blocked": task_counts["blocked"],
            "completionRate": completion_rate,
        },
        "sessions": {
            "active24h": session_counts["total"],
            "feishu": session_counts["feishu"],
            "webchat": session_counts["webchat"],
            "totalRuntimeMs": total_runtime,
        },
    }


def get_assignees(config):
    """Get list of available assignees (humans + agents)"""
    # Human assignees
    humans = [
        {"id": "Ricky", "type": "human", "displayName": "Ricky", "avatar": None},
    ]

    # OpenClaw Agents from openclaw.json
    openclaw_agents = []
    configured_agents = agent_cache.get_agents_list()
    if configured_agents:
        for agent_id in configured_agents:
            openclaw_agents.append(
                {
                    "id": agent_id,
                    "type": "openclaw",
                    "displayName": agent_id.capitalize(),
                    "avatar": None,
                }
            )

    # OpenCode Agents
    opencode_agents = [
        {
            "id": "opencode",
            "type": "opencode",
            "displayName": "OpenCode",
            "avatar": None,
        },
    ]

    return {
        "humans": humans,
        "openclaw": openclaw_agents,
        "opencode": opencode_agents,
    }


def get_opencode_sessions(worktree_filter="vault/projects"):
    """Get OpenCode sessions from SQLite database (D94-D95)

    Query sessions with project worktree matching the filter.
    This bypasses the HTTP API which only returns global sessions.
    """
    import sqlite3

    db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")

    if not os.path.exists(db_path):
        return {"sessions": [], "error": "OpenCode database not found"}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT 
                s.id,
                s.title,
                s.project_id as projectID,
                s.directory,
                s.time_created as timeCreated,
                s.time_updated as timeUpdated,
                s.time_archived as timeArchived,
                p.worktree,
                p.name as projectName
            FROM session s
            JOIN project p ON s.project_id = p.id
            WHERE p.worktree LIKE ?
            AND s.time_archived IS NULL
            ORDER BY s.time_updated DESC
        """

        cursor.execute(query, (f"%{worktree_filter}%",))
        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append(
                {
                    "id": row["id"],
                    "title": row["title"] or "Untitled",
                    "projectID": row["projectID"],
                    "directory": row["directory"],
                    "worktree": row["worktree"],
                    "projectName": row["projectName"],
                    "time": {
                        "created": row["timeCreated"],
                        "updated": row["timeUpdated"],
                    },
                    "status": "idle",
                    "time_created": row["timeCreated"],
                }
            )

        return {"sessions": sessions, "count": len(sessions)}

    except sqlite3.Error as e:
        return {"sessions": [], "error": str(e)}


OPENCODE_PROJECTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "opencode-projects.json"
)


def get_opencode_projects():
    """Get OpenCode projects configuration (D88)"""
    if not os.path.exists(OPENCODE_PROJECTS_PATH):
        return {"projects": [], "error": "Config file not found"}

    try:
        with open(OPENCODE_PROJECTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "projects": data.get("projects", []),
            "default": data.get("defaultProject", ""),
        }
    except Exception as e:
        return {"projects": [], "error": str(e)}


def get_session_state(config):
    """Get current session state from openclaw (D72-D76)"""
    session_state_path = os.path.expanduser("~/.openclaw/workspace/session-state.json")

    if not os.path.exists(session_state_path):
        return {"status": "offline", "error": "Session state file not found"}

    try:
        with open(session_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        current_task_id = data.get("current_task")
        status = data.get("status", "idle")
        waiting_events = data.get("waiting_events", [])

        task_info = None
        if current_task_id:
            tasks_path = config.get("tasks", {}).get("path", "")
            if tasks_path and os.path.exists(tasks_path):
                with open(tasks_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            task = json.loads(line)
                            if task.get("task_id") == current_task_id:
                                task_info = {
                                    "id": task.get("task_id"),
                                    "title": task.get("title", ""),
                                    "priority": task.get("priority", "待定"),
                                    "status": task.get("status", "待处理"),
                                }
                                break

        return {
            "status": status,
            "currentTask": task_info,
            "waitingCount": len(waiting_events),
            "model": data.get("model", "unknown"),
            "lastUpdated": data.get("last_updated"),
        }
    except Exception as e:
        return {"status": "offline", "error": str(e)}


def send_notification(config, task_id, agent_id, notification_type):
    """Send notification to agent via openclaw CLI"""
    templates = {
        "PRIORITY_UP": f"Task {task_id} priority changed. Please review.",
        "WORK_NEXT": f"Queue jump: Task {task_id} is highest priority. Start immediately.",
    }

    message = templates.get(notification_type, f"Notification for task {task_id}")

    try:
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--agent",
                agent_id,
                "--message",
                message,
                "--deliver",
                "--reply-channel",
                "feishu",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {"success": True, "message": "通知已发送"}
        else:
            return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}



def execute_task(config, task_id, agent_id, agent_type="openclaw"):
    """Execute task immediately by sending to agent (OpenClaw or OpenCode)"""
    tasks_path = config["tasks"]["path"]
    openclaw_path = "/home/aegis/.npm-global/bin/openclaw"

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        task_data = None
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["status"] = "进行中"
                        task["notes"] = task.get("notes", "") + f"\n\n【执行记录】{datetime.now().isoformat()} - 任务已发送给 {agent_type}:{agent_id} 执行"
                        found = True
                        task_data = task
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found, "task_data": task_data}

    result = with_jsonl_lock(tasks_path, modify)

    if not result["found"]:
        return {"success": False, "error": "Task not found"}

    task_data = result["task_data"]

    # Send task to agent (async - don't wait for completion)
    try:
        if agent_type == "openclaw":
            # Send message to OpenClaw agent using background process
            message = f"【立即执行】Task {task_id}: {task_data.get('title', 'Untitled')}\n\n请开始执行此任务。"

            # Use Popen for async execution (don't block HTTP response)
            subprocess.Popen(
                [
                    openclaw_path,
                    "agent",
                    "--agent",
                    agent_id,
                    "--message",
                    message,
                    "--deliver",
                    "--reply-channel",
                    "feishu",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
            )

            return {
                "success": True,
                "message": f"任务已发送给 {agent_id} 执行（异步执行中）",
                "agentType": agent_type,
                "agentId": agent_id,
                "executionMode": "async"
            }

        elif agent_type == "opencode":
            # For OpenCode, spawn session with task context
            return {
                "success": True,
                "message": f"任务已发送给 OpenCode 执行",
                "agentType": agent_type,
                "agentId": agent_id
            }
        else:
            return {"success": False, "error": f"Unknown agent type: {agent_type}"}

    except Exception as e:
        # Rollback task status on error (also with locking)
        def rollback(f):
            lines = f.read().strip().split("\n")
            f.seek(0)
            f.truncate()
            for line in lines:
                if line.strip():
                    try:
                        task = json.loads(line)
                        if task.get("task_id") == task_id:
                            task["status"] = "待处理"
                        f.write(json.dumps(task, ensure_ascii=False) + "\n")
                    except:
                        f.write(line + "\n")
                else:
                    f.write("\n")
            return {"done": True}

        with_jsonl_lock(tasks_path, rollback)
        return {"success": False, "error": str(e)}


class COADashHandler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html")
        elif path == "/api/agents":
            force_refresh = query.get("force", ["false"])[0].lower() == "true"
            self.send_json(get_agents(self.config, force_refresh))
        elif path == "/api/gateway/status":
            self.send_json(get_gateway_status(self.config))
        elif path == "/api/tasks":
            filters = {}
            if "status" in query:
                filters["status"] = query["status"][0]
            if "priority" in query:
                filters["priority"] = query["priority"][0]
            if "search" in query:
                filters["search"] = query["search"][0]
            self.send_json(get_tasks(self.config, filters if filters else None))
        elif path == "/api/sessions":
            agent_filter = query.get("agent", ["all"])[0]
            type_filter = query.get("type", ["all"])[0]
            self.send_json(get_sessions(self.config, agent_filter, type_filter))
        elif path == "/api/assignees":
            self.send_json(get_assignees(self.config))
        elif path == "/api/stats":
            self.send_json(get_stats(self.config))
        elif path == "/api/config":
            self.send_json(
                {
                    "dashboard": self.config["dashboard"],
                    "gateway": {
                        k: v for k, v in self.config["gateway"].items() if k != "token"
                    },
                    "status": self.config["status"],
                }
            )
        elif path == "/api/opencode/sessions":
            worktree_filter = query.get("worktree", ["vault/projects"])[0]
            self.send_json(get_opencode_sessions(worktree_filter))
        elif path == "/api/opencode/projects":
            self.send_json(get_opencode_projects())
        elif path == "/api/session-state":
            self.send_json(get_session_state(self.config))
        elif path.startswith("/api/opencode/") and "/session/" in path:
            self.proxy_opencode_request(path)
        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Handle /api/tasks/:id/assignee
        assignee_match = re.match(r"/api/tasks/([^/]+)/assignee", path)
        if assignee_match:
            task_id = assignee_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                assignee = data.get("assignee", "")
                result = update_task_assignee(self.config, task_id, assignee)
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/:id/priority
        priority_match = re.match(r"/api/tasks/([^/]+)/priority", path)
        if priority_match:
            task_id = priority_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                priority = data.get("priority")
                if priority:
                    result = update_task_priority(self.config, task_id, priority)
                    self.send_json(result)
                else:
                    self.send_json(
                        {"success": False, "error": "Priority required"}, 400
                    )
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/:id/status
        status_match = re.match(r"/api/tasks/([^/]+)/status", path)
        if status_match:
            task_id = status_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                status = data.get("status")
                if status:
                    result = update_task_status(self.config, task_id, status)
                    self.send_json(result)
                else:
                    self.send_json({"success": False, "error": "Status required"}, 400)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/status/batch
        batch_match = re.match(r"/api/tasks/status/batch", path)
        if batch_match:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                task_ids = data.get("taskIds", [])
                status = data.get("status")
                if task_ids and status:
                    result = update_task_status_batch(self.config, task_ids, status)
                    self.send_json(result)
                else:
                    self.send_json(
                        {"success": False, "error": "taskIds and status required"}, 400
                    )
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        notify_match = re.match(r"/api/tasks/([^/]+)/notify", path)
        work_next_match = re.match(r"/api/tasks/([^/]+)/work-next", path)
        execute_match = re.match(r"/api/tasks/([^/]+)/execute", path)

        if notify_match:
            task_id = notify_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                notification_type = data.get("type", "PRIORITY_UP")
                result = send_notification(
                    self.config, task_id, agent_id, notification_type
                )
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif work_next_match:
            task_id = work_next_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                result = send_notification(self.config, task_id, agent_id, "WORK_NEXT")
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif execute_match:
            task_id = execute_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                agent_type = data.get("agentType", "openclaw")
                result = execute_task(self.config, task_id, agent_id, agent_type)
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif path.startswith("/api/opencode/") and "/session/" in path:
            self.proxy_opencode_request(path)
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        delete_match = re.match(r"/api/tasks/([^/]+)$", path)
        if delete_match:
            task_id = delete_match.group(1)
            result = delete_task(self.config, task_id)
            self.send_json(result)
        else:
            self.send_error(404)

    def send_json(self, data, status=200):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))

        # CORS: Check Origin against whitelist
        origin = self.headers.get("Origin", "")
        allowed_origins = self.config.get("allowedOrigins", [])
        if origin and origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
        elif not origin:
            # No Origin header (direct browser request, curl, etc.)
            pass  # Don't send CORS header

        self.end_headers()
        self.wfile.write(encoded)

    def proxy_opencode_request(self, path):
        """Proxy requests to OpenCode serve (D80-D81, D99)"""
        import urllib.request
        import urllib.error

        parts = path.split("/")
        try:
            port = int(parts[3])
            session_id = parts[5]
            action = parts[6] if len(parts) > 6 else ""
        except (IndexError, ValueError):
            self.send_json({"error": "Invalid path"}, 400)
            return

        # D99: Port whitelist - only allow ports from opencode-projects.json
        projects = get_opencode_projects()
        allowed_ports = [p.get("port") for p in projects.get("projects", []) if p.get("port")]
        if port not in allowed_ports:
            self.send_json({"error": "Port not allowed"}, 403)
            return

        allowed_actions = ["messages", "message", "command"]
        if action and action not in allowed_actions:
            self.send_json({"error": "Action not allowed"}, 403)
            return

        opencode_url = f"http://localhost:{port}/session/{session_id}"
        if action:
            opencode_url += f"/{action}"

        try:
            if self.command == "GET":
                req = urllib.request.Request(
                    opencode_url, headers={"Accept-Encoding": "identity"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
            elif self.command == "POST":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                req = urllib.request.Request(
                    opencode_url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
            else:
                self.send_error(405)
        except urllib.error.URLError as e:
            self.send_json({"error": f"OpenCode connection failed: {e}"}, 502)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_file(self, filename, content_type):
        try:
            path = os.path.join(os.path.dirname(__file__), filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except FileNotFoundError:
            self.send_error(404, "File not found")


class ReusableHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR enabled"""

    allow_reuse_address = True


if __name__ == "__main__":
    config = load_config()
    COADashHandler.config = config

    port = config["dashboard"]["port"]
    host = config["dashboard"]["host"]

    print(f"🦞 COA-dash running on http://{host}:{port}")
    print(f"   Tailscale: http://100.103.186.109:{port}")
    print(f"   Config: {CONFIG_PATH}")

    ReusableHTTPServer((host, port), COADashHandler).serve_forever()
