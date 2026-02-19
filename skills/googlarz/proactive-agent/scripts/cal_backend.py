#!/usr/bin/env python3
"""
cal_backend.py — Unified calendar backend supporting Google Calendar API and Nextcloud (CalDAV).

Import this module in other scripts rather than calling the API directly.
Backend is selected from config.json: "calendar_backend": "google" | "nextcloud"
"""

import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
CONFIG_FILE = SKILL_DIR / "config.json"
TOKEN_FILE = SKILL_DIR / "token.json"
CREDS_FILE = SKILL_DIR / "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ─── Google Calendar Backend ───────────────────────────────────────────────────

def _get_google_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None  # force re-auth
        if not creds or not creds.valid:
            if not CREDS_FILE.exists():
                raise FileNotFoundError(
                    "credentials.json not found. Run setup.sh first.\n"
                    "See SKILL.md Setup section for Google Cloud steps."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def google_list_events(cal_id: str, time_min: datetime, time_max: datetime) -> list:
    service = _get_google_service()
    result = service.events().list(
        calendarId=cal_id,
        timeMin=time_min.isoformat(),
        timeMax=time_max.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=100,
    ).execute()
    return result.get("items", [])


def google_list_calendars() -> list:
    service = _get_google_service()
    return service.calendarList().list().execute().get("items", [])


def google_create_calendar(summary: str) -> str:
    service = _get_google_service()
    cal = service.calendars().insert(body={"summary": summary}).execute()
    return cal["id"]


def google_create_event(cal_id: str, title: str, start: datetime, end: datetime,
                         description: str = "", timezone_str: str = "UTC") -> dict:
    service = _get_google_service()
    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_str},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_str},
    }
    return service.events().insert(calendarId=cal_id, body=body).execute()


# ─── Nextcloud CalDAV Backend ──────────────────────────────────────────────────

def _get_caldav_client(config: dict):
    try:
        import caldav
    except ImportError:
        raise ImportError(
            "caldav package not installed. Run: pip3 install caldav"
        )
    nc = config.get("nextcloud", {})
    url = nc.get("url", "").rstrip("/")
    username = nc.get("username", "")
    password = nc.get("password", "")
    if not all([url, username, password]):
        raise ValueError(
            "Nextcloud config incomplete. Set nextcloud.url, nextcloud.username, "
            "nextcloud.password in config.json"
        )
    client = caldav.DAVClient(
        url=f"{url}/remote.php/dav",
        username=username,
        password=password,
    )
    return client


def nextcloud_list_calendars(config: dict) -> list:
    client = _get_caldav_client(config)
    principal = client.principal()
    calendars = principal.calendars()
    return [{"id": str(cal.url), "summary": cal.name} for cal in calendars]


def nextcloud_find_or_create_calendar(config: dict, summary: str) -> str:
    client = _get_caldav_client(config)
    principal = client.principal()
    for cal in principal.calendars():
        if cal.name == summary:
            return str(cal.url)
    # Create it
    new_cal = principal.make_calendar(name=summary)
    return str(new_cal.url)


def nextcloud_list_events(config: dict, cal_url: str,
                           time_min: datetime, time_max: datetime) -> list:
    import caldav
    client = _get_caldav_client(config)
    cal = caldav.Calendar(client=client, url=cal_url)
    events = cal.date_search(start=time_min, end=time_max, expand=True)
    result = []
    for event in events:
        try:
            comp = event.vobject_instance.vevent
            summary = str(comp.summary.value) if hasattr(comp, "summary") else "(no title)"
            dtstart = comp.dtstart.value
            dtend = comp.dtend.value if hasattr(comp, "dtend") else dtstart
            # Normalise to datetime with UTC
            if hasattr(dtstart, "date") and not isinstance(dtstart, datetime):
                dtstart = datetime.combine(dtstart, datetime.min.time()).replace(tzinfo=timezone.utc)
            if dtstart.tzinfo is None:
                dtstart = dtstart.replace(tzinfo=timezone.utc)
            if hasattr(dtend, "date") and not isinstance(dtend, datetime):
                dtend = datetime.combine(dtend, datetime.min.time()).replace(tzinfo=timezone.utc)
            if dtend.tzinfo is None:
                dtend = dtend.replace(tzinfo=timezone.utc)
            description = str(comp.description.value) if hasattr(comp, "description") else ""
            uid = str(comp.uid.value) if hasattr(comp, "uid") else str(uuid.uuid4())
            attendees = []
            if hasattr(comp, "attendee"):
                raw = comp.attendee.value if hasattr(comp.attendee, "value") else []
                if isinstance(raw, str):
                    raw = [raw]
                for a in raw:
                    email = a.replace("mailto:", "")
                    attendees.append({"email": email})
            result.append({
                "id": uid,
                "summary": summary,
                "description": description,
                "start": {"dateTime": dtstart.isoformat()},
                "end": {"dateTime": dtend.isoformat()},
                "attendees": attendees,
                "_caldav_url": str(event.url),
            })
        except Exception:
            pass
    return result


def nextcloud_create_event(config: dict, cal_url: str, title: str,
                            start: datetime, end: datetime,
                            description: str = "") -> dict:
    import caldav
    from icalendar import Calendar as ICalendar, Event as IEvent
    client = _get_caldav_client(config)
    cal = caldav.Calendar(client=client, url=cal_url)

    event_uid = str(uuid.uuid4())
    ical = ICalendar()
    ical.add("prodid", "-//OpenClaw//ProactiveAgent//EN")
    ical.add("version", "2.0")
    vevent = IEvent()
    vevent.add("summary", title)
    vevent.add("dtstart", start)
    vevent.add("dtend", end)
    vevent.add("description", description)
    vevent.add("uid", event_uid)
    vevent.add("dtstamp", datetime.now(timezone.utc))
    ical.add_component(vevent)

    cal.add_event(ical.to_ical().decode())
    return {"id": event_uid, "summary": title}


# ─── Unified API ──────────────────────────────────────────────────────────────

class CalendarBackend:
    def __init__(self):
        self.config = load_config()
        self.backend = self.config.get("calendar_backend", "google")

    def list_user_calendars(self) -> list:
        if self.backend == "nextcloud":
            return nextcloud_list_calendars(self.config)
        return google_list_calendars()

    def get_openclaw_cal_id(self) -> str:
        cal_id = self.config.get("openclaw_cal_id", "")
        if not cal_id:
            raise ValueError("openclaw_cal_id not set in config.json. Run setup.sh first.")
        return cal_id

    def list_events(self, cal_id: str, time_min: datetime, time_max: datetime) -> list:
        if self.backend == "nextcloud":
            return nextcloud_list_events(self.config, cal_id, time_min, time_max)
        return google_list_events(cal_id, time_min, time_max)

    def create_event(self, cal_id: str, title: str, start: datetime, end: datetime,
                     description: str = "") -> dict:
        tz_str = self.config.get("timezone", "UTC")
        if self.backend == "nextcloud":
            return nextcloud_create_event(self.config, cal_id, title, start, end, description)
        return google_create_event(cal_id, title, start, end, description, tz_str)

    def resolve_user_calendar_id(self, calendar_name: str) -> Optional[str]:
        """Find a calendar ID by name."""
        calendars = self.list_user_calendars()
        for cal in calendars:
            if cal.get("summary", "").lower() == calendar_name.lower():
                return cal["id"]
        return None
