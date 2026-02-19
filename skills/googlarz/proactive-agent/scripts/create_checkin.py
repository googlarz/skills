#!/usr/bin/env python3
"""
create_checkin.py — Create pre and post check-in events in the OpenClaw calendar.

Usage:
  python3 create_checkin.py \
    --title "Investor Demo" \
    --event-datetime "2025-03-15T14:00:00" \
    --event-duration 60 \
    --user-calendar "Work"
"""

import argparse
import json
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
SCOPES = ["https://www.googleapis.com/auth/calendar"]


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


def parse_offset(offset_str):
    """Parse '1 day', '2 hours', '30 minutes' into timedelta."""
    parts = offset_str.strip().lower().split()
    value = int(parts[0])
    unit = parts[1]
    if "day" in unit:
        return timedelta(days=value)
    if "hour" in unit:
        return timedelta(hours=value)
    if "minute" in unit:
        return timedelta(minutes=value)
    return timedelta(hours=1)


def create_event(service, cal_id, title, start_dt, duration_min, description):
    end_dt = start_dt + timedelta(minutes=duration_min)
    tz = "UTC"
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
    }
    event = service.events().insert(calendarId=cal_id, body=body).execute()
    return event


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--event-datetime", required=True)
    parser.add_argument("--event-duration", type=int, default=60)
    parser.add_argument("--user-calendar", default="")
    args = parser.parse_args()

    config = load_config()
    service = get_service()
    openclaw_cal_id = config.get("openclaw_cal_id", "primary")

    # Parse event start
    event_start = datetime.fromisoformat(args.event_datetime)
    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=timezone.utc)
    event_end = event_start + timedelta(minutes=args.event_duration)

    # Determine pre check-in offset
    now = datetime.now(timezone.utc)
    same_day = event_start.date() == now.date()
    if same_day:
        pre_offset = parse_offset(config.get("pre_checkin_offset_same_day", "1 hour"))
    else:
        pre_offset = parse_offset(config.get("pre_checkin_offset_default", "1 day"))

    post_offset = parse_offset(config.get("post_checkin_offset", "30 minutes"))

    pre_start = event_start - pre_offset
    post_start = event_end + post_offset

    # Create pre check-in
    pre_title = f"🦞 Prep: {args.title}"
    pre_desc = (
        f"Prep check-in for: {args.title}\n\n"
        f"Suggested prompts:\n"
        f"- Do you need help preparing? Slides, talking points, research, practice run?\n"
        f"- What's the most important outcome you want from this?\n"
        f"- Any open questions or concerns to address beforehand?"
    )
    pre_event = create_event(service, openclaw_cal_id, pre_title, pre_start, 15, pre_desc)

    # Create post check-in
    post_title = f"🦞 Follow-up: {args.title}"
    post_desc = (
        f"Follow-up check-in for: {args.title}\n\n"
        f"Suggested prompts:\n"
        f"- How did it go? What worked, what didn't?\n"
        f"- Any action items to capture?\n"
        f"- Notes or decisions to record?\n"
        f"- Anything to improve for next time?"
    )
    post_event = create_event(service, openclaw_cal_id, post_title, post_start, 15, post_desc)

    result = {
        "status": "created",
        "event_title": args.title,
        "pre_checkin": {
            "title": pre_title,
            "start": pre_start.isoformat(),
            "calendar": "OpenClaw",
            "event_id": pre_event.get("id"),
        },
        "post_checkin": {
            "title": post_title,
            "start": post_start.isoformat(),
            "calendar": "OpenClaw",
            "event_id": post_event.get("id"),
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
