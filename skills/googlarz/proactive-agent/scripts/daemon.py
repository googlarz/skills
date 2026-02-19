#!/usr/bin/env python3
"""
daemon.py — Proactive Agent background daemon.

Runs independently of OpenClaw conversations. Scans calendar on a schedule,
detects conflicts, sends notifications via configured channels.

Usage:
  python3 daemon.py                  # run once (called by launchd/systemd)
  python3 daemon.py --loop           # run forever with interval sleep
  python3 daemon.py --status         # print last run info
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.version_info < (3, 8):
    print(json.dumps({"error": "python_version_too_old", "detail": f"Python 3.8+ required. You have {sys.version}."}))
    sys.exit(1)

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
CONFIG_FILE = SKILL_DIR / "config.json"
STATE_FILE = SKILL_DIR / "daemon_state.json"
LOG_FILE = SKILL_DIR / "daemon.log"

sys.path.insert(0, str(SKILL_DIR / "scripts"))


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        # Keep log under 500 lines
        lines = LOG_FILE.read_text().splitlines()
        if len(lines) > 500:
            LOG_FILE.write_text("\n".join(lines[-400:]) + "\n")
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_run": None, "notified_events": {}}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_notification(config: dict, message: str, event_id: str = ""):
    """Send a notification via configured channel(s)."""
    channels = config.get("notification_channels", ["system"])
    sent = False

    for channel in channels:
        try:
            if channel == "system":
                _notify_system(message)
                sent = True
            elif channel == "openclaw":
                # Write to pending_nudges.json — OpenClaw reads this on next conversation open
                nudges_file = SKILL_DIR / "pending_nudges.json"
                nudges = []
                if nudges_file.exists():
                    try:
                        nudges = json.loads(nudges_file.read_text())
                    except Exception:
                        nudges = []
                nudges.append({
                    "message": message,
                    "event_id": event_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "shown": False,
                })
                nudges_file.write_text(json.dumps(nudges, indent=2))
                sent = True
            elif channel == "telegram":
                _notify_telegram(config, message)
                sent = True
        except Exception as e:
            log(f"Notification channel '{channel}' failed: {e}")

    if not sent:
        log(f"WARNING: No notification delivered for: {message[:60]}")
    return sent


def _notify_system(message: str):
    """macOS/Linux system notification."""
    platform = sys.platform
    if platform == "darwin":
        script = f'display notification "{message.replace(chr(34), chr(39))}" with title "🦞 OpenClaw"'
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    elif platform.startswith("linux"):
        subprocess.run(["notify-send", "🦞 OpenClaw", message], check=True, capture_output=True)
    else:
        log(f"System notify not supported on {platform}: {message}")


def _notify_telegram(config: dict, message: str):
    import urllib.request
    tg = config.get("telegram", {})
    token = tg.get("bot_token", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = tg.get("chat_id", "") or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        raise ValueError("telegram.bot_token and telegram.chat_id required in config.json")
    payload = json.dumps({"chat_id": chat_id, "text": f"🦞 {message}", "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=10)


def run_scan() -> dict:
    """Run scan_calendar.py --force and return parsed output."""
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts/scan_calendar.py"), "--force"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"scan_calendar.py failed: {result.stderr[:200]}")
    return json.loads(result.stdout)


def run_conflict_check(scan_output: dict) -> list:
    """Run conflict_detector.py and return list of conflicts."""
    result = subprocess.run(
        [sys.executable, str(SKILL_DIR / "scripts/conflict_detector.py")],
        input=json.dumps(scan_output),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout).get("conflicts", [])
    except Exception:
        return []


def tick(config: dict, state: dict) -> dict:
    """One daemon tick: scan, detect, notify."""
    log("Daemon tick started")
    threshold = config.get("calendar_threshold", 6)
    notified = state.get("notified_events", {})
    now_iso = datetime.now(timezone.utc).isoformat()

    # Scan
    try:
        scan = run_scan()
    except Exception as e:
        log(f"Scan failed: {e}")
        state["last_run"] = now_iso
        return state

    actionable = scan.get("actionable", [])
    log(f"Scan complete: {scan.get('total_events', 0)} events, {len(actionable)} actionable")

    # Notify on actionable events not yet notified in this window
    for event in actionable:
        eid = event.get("id", "")
        title = event.get("title", "")
        hours = event.get("hours_away")
        score = event.get("score", 0)

        if not eid:
            continue

        # Compute a notification window key: event_id + day
        day_key = f"{eid}_{datetime.now(timezone.utc).date()}"
        if day_key in notified:
            continue

        # Build message
        if hours is not None and hours <= 2:
            time_str = f"in {int(hours * 60)} minutes"
        elif hours is not None and hours <= 24:
            time_str = f"in {int(hours)} hours"
        elif hours is not None:
            time_str = f"in {int(hours / 24)} days"
        else:
            time_str = "coming up"

        msg = f"*{title}* is {time_str}. Want to prep? (score: {score}/10)"
        send_notification(config, msg, eid)
        notified[day_key] = now_iso
        log(f"Notified: {title} ({time_str})")

    # Conflict notifications
    try:
        conflicts = run_conflict_check(scan)
        for conflict in conflicts:
            ckey = f"conflict_{conflict.get('key', '')}"
            if ckey not in notified:
                msg = conflict.get("message", "Calendar conflict detected.")
                send_notification(config, msg)
                notified[ckey] = now_iso
                log(f"Conflict notified: {msg[:80]}")
    except Exception as e:
        log(f"Conflict check failed: {e}")

    # Post-event follow-up nudges
    try:
        _check_pending_followups(config, state, notified, now_iso)
    except Exception as e:
        log(f"Follow-up check failed: {e}")

    state["last_run"] = now_iso
    state["notified_events"] = notified

    # Prune notified dict — keep only last 200 entries
    if len(notified) > 200:
        keys = list(notified.keys())
        state["notified_events"] = {k: notified[k] for k in keys[-200:]}

    return state


def _check_pending_followups(config: dict, state: dict, notified: dict, now_iso: str):
    """Check outcomes/ for events needing follow-up that haven't been nudged."""
    outcomes_dir = SKILL_DIR / "outcomes"
    if not outcomes_dir.exists():
        return
    now = datetime.now(timezone.utc)
    for f in outcomes_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if not data.get("follow_up_needed"):
                continue
            # Check if follow-up action items are unresolved
            action_items = data.get("action_items", [])
            if not action_items:
                continue
            event_dt_str = data.get("event_datetime", "")
            if not event_dt_str:
                continue
            event_dt = datetime.fromisoformat(event_dt_str.replace("Z", "+00:00"))
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            days_since = (now - event_dt).days
            # Nudge at 7 days if unresolved
            nudge_key = f"followup_7d_{f.stem}"
            if days_since >= 7 and nudge_key not in notified:
                title = data.get("event_title", "an event")
                n_items = len(action_items)
                msg = (f"*Follow-up reminder:* {title} was {days_since} days ago. "
                       f"You have {n_items} open action item(s). Want to review?")
                send_notification(config, msg)
                notified[nudge_key] = now_iso
                log(f"Follow-up nudge sent for {title}")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in a loop (for manual testing)")
    parser.add_argument("--status", action="store_true", help="Print daemon state and exit")
    args = parser.parse_args()

    if args.status:
        state = load_state()
        print(json.dumps(state, indent=2))
        return

    config = load_config()
    state = load_state()

    if args.loop:
        interval = config.get("daemon_interval_minutes", 15) * 60
        log(f"Running in loop mode, interval={interval}s")
        while True:
            try:
                state = tick(config, state)
                save_state(state)
            except Exception as e:
                log(f"Tick error: {e}")
            time.sleep(interval)
    else:
        # Single run (called by launchd/systemd)
        try:
            state = tick(config, state)
            save_state(state)
        except Exception as e:
            log(f"Fatal tick error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
