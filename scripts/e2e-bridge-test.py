#!/usr/bin/env python3
"""
E2E test for Feishu-Claude bridge.

Tests via coa-dash API (simulates what bridge does):
  send message → claude --resume → poll → extract response

Usage:
  python3 scripts/e2e-bridge-test.py [--session SESSION_ID] [--quick]
"""
import json
import sys
import time
import requests

BASE = "http://localhost:8890"


def get_sessions():
    r = requests.get(f"{BASE}/api/claudecode/sessions", timeout=10)
    return r.json().get("sessions", [])


def get_session(sid):
    r = requests.get(f"{BASE}/api/claudecode/sessions/{sid}", timeout=10)
    return r.json()


def send_message(sid, content):
    r = requests.post(
        f"{BASE}/api/claudecode/sessions/{sid}/message",
        json={"content": content},
        headers={"Content-Type": "application/json"},
        timeout=120,
    )
    return r.json()


def get_last_assistant_text(sid, baseline):
    """Fetch history and return last assistant text after baseline."""
    info = get_session(sid)
    count = info.get("messageCount", 0)
    new_count = count - baseline
    if new_count <= 0:
        return None

    r = requests.get(
        f"{BASE}/api/claudecode/sessions/{sid}/history?limit={max(new_count + 20, 50)}",
        timeout=15,
    )
    if r.status_code != 200:
        return None

    messages = r.json().get("messages", [])
    skip = max(0, len(messages) - new_count)
    for msg in reversed(messages[skip:]):
        if msg.get("type") != "assistant":
            continue
        content = msg.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        texts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                t = c.get("text", "").strip()
                if t:
                    texts.append(t)
        if texts:
            return "\n\n".join(texts)
    return None


def poll_until_done(sid, baseline, timeout=300):
    """Poll until session goes idle and new response appears."""
    start = time.time()
    last_activity = ""
    while time.time() - start < timeout:
        info = get_session(sid)
        status = info.get("status")
        activity = info.get("activity", "")
        count = info.get("messageCount", 0)

        if activity != last_activity:
            elapsed = time.time() - start
            print(f"  {elapsed:.0f}s: status={status} activity={activity} msgs={count}")
            last_activity = activity

        if status not in ("working", "starting") and count > baseline:
            text = get_last_assistant_text(sid, baseline)
            if text:
                return text

        time.sleep(2)

    return None


def run_test(sid, prompt, label, timeout=300):
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"Session: {sid}")
    print(f"Prompt: {prompt[:80]}")
    print(f"{'='*60}")

    info = get_session(sid)
    baseline = info.get("messageCount", 0)
    print(f"Baseline: {baseline} msgs, status={info['status']}")

    if info["status"] in ("working", "starting"):
        print(f"SKIP: session busy ({info['status']})")
        return None

    print("Sending message...")
    result = send_message(sid, prompt)
    error = result.get("error")
    injected = result.get("injected")

    if error and not injected:
        print(f"FAIL: {error}")
        return False

    print(f"Result: injected={injected} error={error}")
    time.sleep(2)

    # Get new baseline after injection
    info2 = get_session(sid)
    new_baseline = max(baseline, info2.get("messageCount", 0))
    print(f"Polling from baseline={new_baseline}...")

    response = poll_until_done(sid, new_baseline, timeout=timeout)

    if response is None:
        print("FAIL: no response (timeout)")
        return False

    print(f"\nResponse ({len(response)} chars):")
    print(response[:600])
    if len(response) > 600:
        print(f"... ({len(response)-600} more chars)")

    print("\nPASS")
    return True


def main():
    session_id = None
    quick = "--quick" in sys.argv

    args = [a for a in sys.argv[1:] if a != "--quick"]
    if "--session" in args:
        idx = args.index("--session")
        if idx + 1 < len(args):
            session_id = args[idx + 1]

    if not session_id:
        sessions = get_sessions()
        idle = [s for s in sessions if s["status"] in ("idle", "error")]
        if not idle:
            print("No idle sessions")
            sys.exit(1)
        session_id = idle[0]["id"]
        print(f"Using: {idle[0]['name']} ({session_id})")

    if quick:
        tests = [("Quick echo", "Reply with exactly: E2E_OK", 60)]
    else:
        tests = [
            ("Simple greeting", "Say 'E2E test passed' and nothing else.", 120),
            ("Code question", "What is 2+2? Reply with just the number.", 120),
            ("File operation", "Run: echo E2E_FILE_TEST. Reply with the output.", 120),
        ]

    results = []
    for label, prompt, timeout in tests:
        ok = run_test(session_id, prompt, label, timeout=timeout)
        if ok is None:
            continue  # skipped
        results.append((label, ok))
        time.sleep(3)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for label, ok in results:
        print(f"  {'✅' if ok else '❌'} {label}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
