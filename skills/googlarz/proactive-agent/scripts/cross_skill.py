#!/usr/bin/env python3
"""
cross_skill.py — Cross-skill context enrichment for proactive-agent.

Checks which other OpenClaw skills are active and pulls relevant context
to enrich prep check-ins. Read-only — never writes to other skills.

Usage:
  python3 cross_skill.py --event-title "Sprint Review" --event-type "one_off_high_stakes"
  python3 cross_skill.py --list-available
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

if sys.version_info < (3, 8):
    print(json.dumps({"error": "python_version_too_old", "detail": f"Python 3.8+ required."}))
    sys.exit(1)

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
SKILLS_ROOT = Path.home() / ".openclaw/workspace/skills"


def skill_exists(name: str) -> bool:
    return (SKILLS_ROOT / name / "SKILL.md").exists()


def available_skills() -> list:
    """Return list of installed skill names that proactive-agent can integrate with."""
    integrable = ["github", "notion", "slack", "discord", "apple-notes", "summarize"]
    return [s for s in integrable if skill_exists(s)]


def get_github_context(event_title: str) -> dict:
    """Pull recent GitHub activity relevant to the event."""
    try:
        # Recent PRs
        result = subprocess.run(
            ["gh", "pr", "list", "--limit", "5", "--json",
             "title,state,updatedAt,url,reviewDecision"],
            capture_output=True, text=True, timeout=10
        )
        prs = json.loads(result.stdout) if result.returncode == 0 else []

        # Recent issues assigned to me
        result2 = subprocess.run(
            ["gh", "issue", "list", "--assignee", "@me", "--limit", "5",
             "--json", "title,state,updatedAt,url"],
            capture_output=True, text=True, timeout=10
        )
        issues = json.loads(result2.stdout) if result2.returncode == 0 else []

        # Filter to items updated in last 3 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        recent_prs = [p for p in prs if p.get("updatedAt", "") >= cutoff]
        recent_issues = [i for i in issues if i.get("updatedAt", "") >= cutoff]

        if not recent_prs and not recent_issues:
            return {}

        context_lines = []
        if recent_prs:
            context_lines.append(f"**Open PRs ({len(recent_prs)}):** " +
                                  ", ".join(p["title"] for p in recent_prs[:3]))
        if recent_issues:
            context_lines.append(f"**Open Issues ({len(recent_issues)}):** " +
                                  ", ".join(i["title"] for i in recent_issues[:3]))

        return {
            "skill": "github",
            "context": "\n".join(context_lines),
            "prs": recent_prs[:3],
            "issues": recent_issues[:3],
        }
    except Exception:
        return {}


def get_notion_context(event_title: str) -> dict:
    """Search Notion for pages related to the event title."""
    notion_key = os.environ.get("NOTION_API_KEY", "")
    if not notion_key:
        return {}
    try:
        import urllib.request
        query = event_title[:50]
        payload = json.dumps({"query": query, "page_size": 3}).encode()
        req = urllib.request.Request(
            "https://api.notion.com/v1/search",
            data=payload,
            headers={
                "Authorization": f"Bearer {notion_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            }
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=8).read())
        results = resp.get("results", [])
        if not results:
            return {}
        pages = []
        for r in results[:3]:
            title = ""
            props = r.get("properties", {})
            for v in props.values():
                if v.get("type") == "title":
                    texts = v.get("title", [])
                    title = "".join(t.get("plain_text", "") for t in texts)
                    break
            if title:
                pages.append({"title": title, "url": r.get("url", "")})
        if not pages:
            return {}
        return {
            "skill": "notion",
            "context": "**Notion pages:** " + ", ".join(p["title"] for p in pages),
            "pages": pages,
        }
    except Exception:
        return {}


def get_pending_nudges() -> list:
    """Return unshown nudges from daemon — consumed by OpenClaw on conversation open."""
    nudges_file = SKILL_DIR / "pending_nudges.json"
    if not nudges_file.exists():
        return []
    try:
        nudges = json.loads(nudges_file.read_text())
        unshown = [n for n in nudges if not n.get("shown")]
        if unshown:
            # Mark all as shown
            for n in nudges:
                n["shown"] = True
            nudges_file.write_text(json.dumps(nudges, indent=2))
        return unshown
    except Exception:
        return []


def enrich_event(event_title: str, event_type: str) -> dict:
    """Pull context from all available skills for this event."""
    enrichments = []
    available = available_skills()

    if "github" in available:
        ctx = get_github_context(event_title)
        if ctx:
            enrichments.append(ctx)

    if "notion" in available:
        ctx = get_notion_context(event_title)
        if ctx:
            enrichments.append(ctx)

    # Build combined context block
    if not enrichments:
        return {"event_title": event_title, "enrichments": [], "context_block": ""}

    context_block = "\n\n".join(e["context"] for e in enrichments if e.get("context"))

    return {
        "event_title": event_title,
        "event_type": event_type,
        "enrichments": enrichments,
        "context_block": context_block,
        "skills_used": [e["skill"] for e in enrichments],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-title", default="")
    parser.add_argument("--event-type", default="one_off_standard")
    parser.add_argument("--list-available", action="store_true")
    parser.add_argument("--pending-nudges", action="store_true")
    args = parser.parse_args()

    if args.list_available:
        print(json.dumps({"available_integrations": available_skills()}, indent=2))
    elif args.pending_nudges:
        print(json.dumps({"pending_nudges": get_pending_nudges()}, indent=2))
    elif args.event_title:
        print(json.dumps(enrich_event(args.event_title, args.event_type), indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
