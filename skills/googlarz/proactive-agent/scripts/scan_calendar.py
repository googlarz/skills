#!/usr/bin/env python3
"""
scan_calendar.py — Fetch upcoming events, score them, and enrich with pattern data.

Usage:
  python3 scan_calendar.py                        # scan upcoming events
  python3 scan_calendar.py --patterns <recurring_id>  # get pattern data for a recurring event
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
TOKEN_FILE = SKILL_DIR / "token.json"
CREDS_FILE = SKILL_DIR / "credentials.json"
CONFIG_FILE = SKILL_DIR / "config.json"
OUTCOMES_DIR = SKILL_DIR / "outcomes"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

HIGH_STAKES_KEYWORDS = {
    "demo", "presentation", "interview", "workshop", "conference",
    "launch", "review", "deadline", "board", "investor", "pitch",
    "keynote", "summit", "offsite", "performance"
}


def get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_outcomes(recurring_id=None):
    outcomes = []
    if not OUTCOMES_DIR.exists():
        return outcomes
    for f in sorted(OUTCOMES_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            if recurring_id is None or data.get("recurring_id") == recurring_id:
                outcomes.append(data)
        except Exception:
            pass
    return outcomes


def score_event(event, config, outcomes, openclaw_events):
    score = 0
    title = event.get("summary", "").lower()
    description = event.get("description", "") or ""
    attendees = event.get("attendees", [])
    recurring_id = event.get("recurringEventId")

    # Duration
    start = event["start"].get("dateTime") or event["start"].get("date")
    end = event["end"].get("dateTime") or event["end"].get("date")
    try:
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        duration_min = (e - s).seconds // 60
        if duration_min > 60:
            score += 2
    except Exception:
        duration_min = 0

    # High-stakes keywords
    if any(kw in title for kw in HIGH_STAKES_KEYWORDS):
        score += 1

    # External attendees
    user_domain = None
    for att in attendees:
        if att.get("self"):
            user_domain = att.get("email", "").split("@")[-1]
    if user_domain:
        for att in attendees:
            if not att.get("self") and att.get("email", "").split("@")[-1] != user_domain:
                score += 2
                break

    # No description/agenda
    if not description.strip():
        score += 2

    # Event within 24 hours
    now = datetime.now(timezone.utc)
    try:
        event_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        hours_away = (event_start - now).total_seconds() / 3600
        if 0 < hours_away <= 24:
            score += 2
    except Exception:
        hours_away = 999

    # Check if OpenClaw check-in already exists
    slug = title.replace(" ", "-")[:30]
    already_has_checkin = any(slug in (e.get("summary") or "").lower() for e in openclaw_events)
    if already_has_checkin:
        score -= 5

    # Pattern-based adjustments
    if recurring_id and outcomes:
        recent = outcomes[-4:]
        total_action_items = sum(len(o.get("action_items", [])) for o in recent)
        avg_action_items = total_action_items / len(recent)
        if avg_action_items == 0:
            score -= 3  # routine low-stakes
        elif avg_action_items >= 3:
            score += 2  # routine high-stakes

    score = max(0, min(10, score))

    return {
        "id": event.get("id"),
        "title": event.get("summary", "(no title)"),
        "start": start,
        "end": end,
        "duration_minutes": duration_min,
        "recurring_id": recurring_id,
        "has_description": bool(description.strip()),
        "attendee_count": len(attendees),
        "hours_away": round(hours_away, 1) if hours_away != 999 else None,
        "already_has_checkin": already_has_checkin,
        "score": score,
        "past_outcomes": len(outcomes),
        "event_type": classify_event(recurring_id, duration_min, attendees, outcomes),
    }


def classify_event(recurring_id, duration_min, attendees, outcomes):
    is_recurring = bool(recurring_id)
    has_external = any(not a.get("self") for a in attendees)
    if outcomes:
        recent = outcomes[-4:]
        avg_items = sum(len(o.get("action_items", [])) for o in recent) / len(recent)
    else:
        avg_items = 0

    if is_recurring and not has_external and avg_items < 1:
        return "routine_low_stakes"
    if is_recurring and (has_external or avg_items >= 2):
        return "routine_high_stakes"
    if not is_recurring and duration_min < 60 and not has_external:
        return "one_off_standard"
    return "one_off_high_stakes"


def get_openclaw_events(service, cal_id, days=7):
    now = datetime.now(timezone.utc)
    time_max = (now + timedelta(days=days)).isoformat()
    try:
        result = service.events().list(
            calendarId=cal_id,
            timeMin=now.isoformat(),
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        return result.get("items", [])
    except Exception:
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patterns", help="Get pattern data for a recurring_id")
    args = parser.parse_args()

    config = load_config()

    if args.patterns:
        outcomes = load_outcomes(args.patterns)
        print(json.dumps({
            "recurring_id": args.patterns,
            "total_outcomes": len(outcomes),
            "outcomes": outcomes[-5:]  # last 5
        }, indent=2))
        return

    service = get_service()
    now = datetime.now(timezone.utc)
    days_ahead = config.get("scan_days_ahead", 7)
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    openclaw_cal_id = config.get("openclaw_cal_id", "")
    openclaw_events = get_openclaw_events(service, openclaw_cal_id, days_ahead) if openclaw_cal_id else []

    # Fetch all user calendars
    cal_list = service.calendarList().list().execute().get("items", [])
    all_events = []

    for cal in cal_list:
        cal_id = cal["id"]
        if cal_id == openclaw_cal_id:
            continue
        try:
            result = service.events().list(
                calendarId=cal_id,
                timeMin=now.isoformat(),
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=50
            ).execute()
            for event in result.get("items", []):
                event["_calendar_name"] = cal.get("summary", "")
                all_events.append(event)
        except Exception:
            pass

    # Score events
    scored = []
    for event in all_events:
        outcomes = load_outcomes(event.get("recurringEventId"))
        scored_event = score_event(event, config, outcomes, openclaw_events)
        scored_event["calendar"] = event.get("_calendar_name", "")
        scored.append(scored_event)

    # Sort by score desc, then by start time
    scored.sort(key=lambda e: (-e["score"], e["start"] or ""))

    print(json.dumps({
        "scanned_at": now.isoformat(),
        "days_ahead": days_ahead,
        "total_events": len(scored),
        "events": scored
    }, indent=2))


if __name__ == "__main__":
    main()
