#!/usr/bin/env python3
"""
capture_outcome.py — Save post-event outcome and sync to notes destination.

Usage:
  python3 capture_outcome.py \
    --event-title "Investor Demo" \
    --event-datetime "2025-03-15T14:00:00" \
    --recurring-id "" \
    --notes "Demo went well. Investors liked the product. Need to send deck." \
    --action-items "Send deck to investors|Schedule follow-up call|Update pricing page" \
    --sentiment "positive" \
    --follow-up-needed "true"
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
CONFIG_FILE = SKILL_DIR / "config.json"
OUTCOMES_DIR = SKILL_DIR / "outcomes"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def save_local(outcome, notes_path):
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    date_str = outcome["event_datetime"][:10]
    slug = slugify(outcome["event_title"])
    filename = OUTCOMES_DIR / f"{date_str}_{slug}.json"
    with open(filename, "w") as f:
        json.dump(outcome, f, indent=2)
    return str(filename)


def save_apple_notes(outcome):
    title = f"🦞 {outcome['event_title']} — {outcome['event_datetime'][:10]}"
    items = "\n".join(f"• {item}" for item in outcome.get("action_items", []))
    body = f"""Event: {outcome['event_title']}
Date: {outcome['event_datetime'][:10]}
Sentiment: {outcome.get('sentiment', 'neutral')}

Notes:
{outcome.get('outcome_notes', '')}

Action Items:
{items if items else 'None'}

Follow-up needed: {outcome.get('follow_up_needed', False)}
Tags: {', '.join(outcome.get('tags', []))}
"""
    script = f'''
tell application "Notes"
    make new note at folder "Notes" with properties {{name:"{title}", body:"{body.replace('"', "'")}"}}
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-title", required=True)
    parser.add_argument("--event-datetime", required=True)
    parser.add_argument("--recurring-id", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--action-items", default="")
    parser.add_argument("--sentiment", choices=["positive", "neutral", "negative"], default="neutral")
    parser.add_argument("--follow-up-needed", choices=["true", "false"], default="false")
    parser.add_argument("--tags", default="")
    args = parser.parse_args()

    config = load_config()

    action_items = [i.strip() for i in args.action_items.split("|") if i.strip()] if args.action_items else []
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    outcome = {
        "event_title": args.event_title,
        "event_datetime": args.event_datetime,
        "recurring_id": args.recurring_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "prep_done": True,
        "outcome_notes": args.notes,
        "action_items": action_items,
        "sentiment": args.sentiment,
        "follow_up_needed": args.follow_up_needed == "true",
        "tags": tags,
    }

    result = {"status": "saved", "destinations": []}

    # Always save locally
    notes_path = os.path.expanduser(config.get("notes_path", str(OUTCOMES_DIR)))
    local_path = save_local(outcome, notes_path)
    result["destinations"].append({"type": "local", "path": local_path})

    # Optional: Apple Notes
    destination = config.get("notes_destination", "local")
    if destination == "apple-notes":
        try:
            save_apple_notes(outcome)
            result["destinations"].append({"type": "apple-notes", "status": "created"})
        except Exception as e:
            result["destinations"].append({"type": "apple-notes", "status": "error", "error": str(e)})

    # Optional: Notion (requires notion-skill to be active and NOTION_API_KEY set)
    elif destination == "notion":
        notion_key = os.environ.get("NOTION_API_KEY")
        notion_db = os.environ.get("NOTION_OUTCOMES_DB_ID")
        if notion_key and notion_db:
            try:
                import urllib.request
                payload = json.dumps({
                    "parent": {"database_id": notion_db},
                    "properties": {
                        "Name": {"title": [{"text": {"content": args.event_title}}]},
                        "Date": {"date": {"start": args.event_datetime[:10]}},
                        "Sentiment": {"select": {"name": args.sentiment}},
                        "Notes": {"rich_text": [{"text": {"content": args.notes}}]},
                    }
                }).encode()
                req = urllib.request.Request(
                    "https://api.notion.com/v1/pages",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {notion_key}",
                        "Content-Type": "application/json",
                        "Notion-Version": "2022-06-28"
                    }
                )
                urllib.request.urlopen(req)
                result["destinations"].append({"type": "notion", "status": "created"})
            except Exception as e:
                result["destinations"].append({"type": "notion", "status": "error", "error": str(e)})

    result["outcome"] = outcome
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
