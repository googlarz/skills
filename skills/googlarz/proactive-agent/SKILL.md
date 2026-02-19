---
name: proactive-agent
description: >
  Proactive assistant that watches conversations and calendar events to offer timely, context-aware help.
  Manages its own "OpenClaw" Google Calendar to schedule pre/post check-ins.
  Use this skill when: the user mentions an upcoming event, meeting, presentation, deadline, or travel;
  when rating whether a new calendar entry is warranted; when deciding whether to proactively reach out
  before or after a scheduled event; or when scanning the user's calendar for upcoming items that may
  need preparation or follow-up.
---

# Proactive Agent

## Purpose

This skill turns OpenClaw into a proactive partner rather than a reactive tool. It does two things:

1. **Conversation monitoring** — after every exchange, silently rate whether the user mentioned something calendar-worthy. If the score is high enough, ask once, briefly.
2. **Calendar monitoring** — periodically scan the user's Google Calendars for upcoming events and decide whether to reach out ahead of time or follow up afterward.

All scheduled check-ins are written to the dedicated **OpenClaw** calendar.

---

## Setup (run once)

### 1. Authenticate with Google Calendar

```bash
# Install the Google Calendar CLI helper
pip install gcalcli

# Authenticate (opens browser)
gcalcli --noauth_local_webserver init
```

Verify access:
```bash
gcalcli list
```

### 2. Create the OpenClaw calendar (if it doesn't exist)

```bash
# List existing calendars
gcalcli list

# If "OpenClaw" is not listed, create it via the Google Calendar web UI or API:
curl -s -X POST \
  "https://www.googleapis.com/calendar/v3/calendars" \
  -H "Authorization: Bearer $(gcalcli --noauth_local_webserver get_access_token 2>/dev/null)" \
  -H "Content-Type: application/json" \
  -d '{"summary": "OpenClaw"}' | python3 -m json.tool
```

Save the returned `id` as the `OPENCLAW_CAL_ID` — you'll use it in every write command below.

---

## Feature 1 — Conversation Monitoring

### When to activate

After **every** user message and every assistant reply, silently run this mental checklist:

| Signal | Examples |
|--------|----------|
| Upcoming event or deadline | "I have a presentation Friday", "meeting tomorrow", "flight next week", "demo on the 23rd" |
| Preparation work | "I need to prepare", "working on slides", "getting ready for" |
| Post-event reflection | "just got back from", "the meeting went", "my talk is done" |
| Recurring obligation | "weekly sync", "quarterly review", "standup" |

Score the likelihood that a calendar entry + check-in pair would be useful: **0–10**.

- **0–4**: Say nothing. Continue the conversation normally.
- **5–7**: Ask once, at the end of your reply. One sentence, one question.
- **8–10**: Ask before anything else.

### Asking the user

Keep it minimal. Examples:

> "Sounds like you have a presentation on Friday — want me to add a reminder and schedule a prep check-in?"

> "Should I block time before your meeting so we can prep together?"

Never ask twice about the same event in the same conversation unless the user revisits it.

### If the user says yes — create check-ins

Collect (or infer from context):
- Event title
- Event date/time
- Which of the user's calendars to write the event to (ask if unclear)

Then create two OpenClaw entries:

**Pre check-in** (default: 1 day before, or 1 hour before for same-day events):
```bash
gcalcli --calendar "OpenClaw" add \
  --title "🦞 Prep check-in: <event title>" \
  --when "<date> <time>" \
  --duration 15 \
  --description "Ask: Do you need help preparing for <event title>? Slides, talking points, research, practice run?"
```

**Post check-in** (default: 30 minutes after the event ends):
```bash
gcalcli --calendar "OpenClaw" add \
  --title "🦞 Follow-up: <event title>" \
  --when "<date> <time>" \
  --duration 15 \
  --description "Ask: How did <event title> go? Notes to capture? Action items? Anything to improve for next time?"
```

Confirm to the user with the exact times chosen. Offer to adjust.

---

## Feature 2 — Calendar Monitoring

### Scanning for upcoming events

Run this to fetch the next 7 days of events across all calendars:
```bash
gcalcli agenda --details all --tsv "now" "7 days"
```

For each event, apply the same 0–10 scoring above. Factors that raise the score:
- Duration > 45 minutes
- Title contains: meeting, review, demo, presentation, interview, workshop, conference, deadline, launch, standup, sync
- Event is external (attendees from other domains)
- Event has no description/agenda (user may need help preparing)
- Event is in < 24 hours and no OpenClaw check-in already exists

### Deciding to reach out

If score ≥ 6 and **no OpenClaw check-in already exists for this event**, proactively message the user:

> "You have a [event title] in [X hours/days]. Want me to help you prepare, or shall I schedule a quick check-in?"

Check for existing OpenClaw entries to avoid duplicate outreach:
```bash
gcalcli --calendar "OpenClaw" agenda --tsv "<event date -1 day>" "<event date +1 day>" | grep -i "<event title>"
```

### Post-event follow-up

After an event's end time passes, if an OpenClaw post check-in exists, trigger the follow-up message when the user next opens a conversation:

> "How did your [event title] go? Anything to capture — notes, action items, lessons learned?"

---

## Configuration (user-adjustable)

Users can tell OpenClaw to change these defaults at any time by saying e.g. "change the prep check-in to 2 hours before":

| Setting | Default | Description |
|---------|---------|-------------|
| `pre_checkin_offset` | 1 day (same-day: 1 hour) | How far before the event to schedule the prep check-in |
| `post_checkin_offset` | 30 minutes after end | How long after the event to schedule the follow-up |
| `conversation_threshold` | 5 | Minimum score to ask about creating a check-in |
| `calendar_threshold` | 6 | Minimum score to proactively reach out about a calendar event |
| `feature_1_enabled` | true | Enable/disable conversation monitoring |
| `feature_2_enabled` | true | Enable/disable calendar monitoring |
| `default_user_calendar` | (ask) | Default calendar to suggest for new user events |

Store user preferences as plain text in `~/.openclaw/workspace/skills/proactive-agent/config.txt`:
```
pre_checkin_offset=1 day
post_checkin_offset=30 minutes
conversation_threshold=5
calendar_threshold=6
feature_1_enabled=true
feature_2_enabled=true
default_user_calendar=
```

Read config before acting:
```bash
cat ~/.openclaw/workspace/skills/proactive-agent/config.txt 2>/dev/null || echo "(no config, using defaults)"
```

---

## Tone & Rules

- **One question at a time.** Never stack multiple asks.
- **Never repeat yourself** about the same event in the same conversation.
- **Always confirm** before creating any calendar entry. Show the exact title, date, and time.
- **Respect "no".** If the user declines, drop it entirely for that event.
- **Be brief.** The check-in prompts during conversation should be ≤ 2 sentences.
- The OpenClaw calendar is internal — never suggest the user look at it directly; surface its data through conversation only.
