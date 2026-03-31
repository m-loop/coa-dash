#!/usr/bin/env python3
"""
COA-dash - Command Orchestration Agent Dashboard
Mobile-first, touch-first dashboard for AI agent orchestration
"""

import json
import os
import re
import subprocess
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


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


def update_task_priority(config, task_id, priority):
    """Update task priority in tasks.jsonl"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    lines = []
    found = False
    updated_task = None

    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["priority"] = priority
                        found = True
                        updated_task = task
                    lines.append(json.dumps(task, ensure_ascii=False))
                except:
                    lines.append(line)

    if not found:
        return {"success": False, "error": "Task not found"}

    with open(tasks_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    return {"success": True, "task": {"taskId": task_id, "priority": priority}}



def delete_task(config, task_id):
    """Delete task from tasks.jsonl"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    lines_data = []
    found = False

    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        found = True
                        continue  # Skip this line (delete it)
                    lines_data.append(json.dumps(task, ensure_ascii=False))
                except:
                    lines_data.append(line)

    if not found:
        return {"success": False, "error": "Task not found"}

    with open(tasks_path, "w", encoding="utf-8") as f:
        for line in lines_data:
            f.write(line + "\n")

    return {"success": True, "deleted": True}



def update_task_assignee(config, task_id, assignee):
    """Update task assignee in tasks.jsonl"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    lines = []
    found = False

    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["assignee"] = assignee if assignee else ""
                        found = True
                    lines.append(json.dumps(task, ensure_ascii=False))
                except:
                    lines.append(line)

    if not found:
        return {"success": False, "error": "Task not found"}

    with open(tasks_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    return {"success": True, "task": {"taskId": task_id, "assignee": assignee}}


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
            openclaw_agents.append({
                "id": agent_id,
                "type": "openclaw",
                "displayName": agent_id.capitalize(),
                "avatar": None,
            })
    
    # OpenCode Agents
    opencode_agents = [
        {"id": "opencode", "type": "opencode", "displayName": "OpenCode", "avatar": None},
    ]
    
    return {
        "humans": humans,
        "openclaw": openclaw_agents,
        "opencode": opencode_agents,
    }


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
        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

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
        else:
            match = re.match(r"/api/tasks/([^/]+)/priority", path)
        if match:
            task_id = match.group(1)
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
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        notify_match = re.match(r"/api/tasks/([^/]+)/notify", path)
        work_next_match = re.match(r"/api/tasks/([^/]+)/work-next", path)

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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

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
