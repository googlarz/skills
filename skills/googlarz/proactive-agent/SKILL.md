---
name: proactive-agent
description: >
  Proactive assistant that watches every conversation and scans Google Calendar to offer timely,
  context-aware help. Manages a dedicated "OpenClaw" Google Calendar for pre/post check-ins.
  Learns patterns from past events to improve timing and relevance. Generates agenda suggestions
  and talking points at prep time. Captures outcomes and action items after events. Treats
  recurring events differently from one-off high-stakes occasions.
  Trigger this skill when: the user mentions any upcoming event, meeting, presentation, deadline,
  interview, demo, travel, or recurring obligation; when deciding whether to proactively reach out
  before or after a calendar event; or when the user asks to capture notes or action items.
---

# Proactive Agent

## Purpose

Turn OpenClaw from a reactive tool into a proactive partner that:

1. **Monitors conversations** — silently scores every exchange for calendar-worthiness, asks once if threshold is met
2. **Monitors calendar** — scans upcoming events and decides when to reach out proactively
3. **Learns patterns** — remembers how past events went to get smarter about future interventions
4. **Prepares you** — generates actual agenda suggestions and talking points at prep time
5. **Captures outcomes** — writes follow-up notes/action items to your preferred notes destination
6. **Handles recurrence intelligently** — treats weekly standups differently from one-off high-stakes events

All check-ins are written to the dedicated **OpenClaw** Google Calendar.

---

## Setup (run once)

```bash
bash ~/.openclaw/workspace/skills/proactive-agent/scripts/setup.sh
```

This script will:
- Check for Python 3.8+ and install `google-api-python-client`, `google-auth-oauthlib`
- Walk through Google OAuth (opens browser once)
- Create the **OpenClaw** calendar if it doesn't exist
- Save `OPENCLAW_CAL_ID` to `config.json`

**Google Cloud prerequisites** (one-time, ~3 minutes):
1. Go to https://console.cloud.google.com → New project → "OpenClaw"
2. Enable **Google Calendar API**
3. Create **OAuth 2.0 credentials** (Desktop app) → download as `credentials.json`
4. Move file: `mv ~/Downloads/credentials.json ~/.openclaw/workspace/skills/proactive-agent/credentials.json`
5. Run `setup.sh`

---

## Configuration

Stored in `~/.openclaw/workspace/skills/proactive-agent/config.json`. Edit directly or tell OpenClaw in plain language.

```json
{
  "pre_checkin_offset_default": "1 day",
  "pre_checkin_offset_same_day": "1 hour",
  "post_checkin_offset": "30 minutes",
  "conversation_threshold": 5,
  "calendar_threshold": 6,
  "feature_conversation": true,
  "feature_calendar": true,
  "default_user_calendar": "",
  "notes_destination": "local",
  "notes_path": "~/.openclaw/workspace/skills/proactive-agent/outcomes/",
  "scan_days_ahead": 7,
  "openclaw_cal_id": ""
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `pre_checkin_offset_default` | 1 day | How far before event to schedule prep check-in |
| `pre_checkin_offset_same_day` | 1 hour | Offset when event is today |
| `post_checkin_offset` | 30 min | How long after event end to schedule follow-up |
| `conversation_threshold` | 5 | Min score (0–10) to ask about creating check-in |
| `calendar_threshold` | 6 | Min score (0–10) to proactively reach out |
| `notes_destination` | local | Where to save outcomes: `local`, `apple-notes`, `notion` |
| `scan_days_ahead` | 7 | How many days ahead to scan calendar |

---

## Feature 1 — Conversation Monitoring

### Scoring (run silently after every exchange)

Score 0–10 whether this conversation warrants a calendar entry + check-in pair.

| Score | Meaning | Action |
|-------|---------|--------|
| 0–4 | No signal | Say nothing |
| 5–7 | Possible event | Ask once, briefly, at end of reply |
| 8–10 | Clear event signal | Ask before anything else |

**Signals that raise the score:**

| +Points | Signal | Examples |
|---------|--------|---------|
| +3 | Explicit future event | "I have a presentation Friday", "demo on the 23rd", "interview next week" |
| +3 | Preparation language | "I need to prep", "working on slides", "getting ready for" |
| +2 | Stress or importance markers | "really important", "nervous about", "big client", "first time" |
| +2 | Deadline language | "due by", "needs to be done before", "deadline is" |
| +1 | Recurring obligation | "weekly standup", "quarterly review", "1:1 tomorrow" |
| +1 | Post-event reflection | "just got out of", "the meeting went", "my talk is done" |
| −2 | Hypothetical / past / general | "what if I had a meeting", "last year's conference" |

**Calibrated examples:**
- "I have a big product demo with investors next Thursday" → **9** (explicit event + importance)
- "I should probably prep for my weekly standup" → **5** (recurring + prep language)
- "How do you structure a good presentation?" → **3** (general, no specific event)
- "My talk yesterday went really well" → **2** (post-event reflection, already happened)
- "I just booked flights for the conference next month" → **7** (explicit future + travel)

### Asking the user

One sentence, one question, at the end of your reply. Never stack asks.

> "Sounds like you have a big investor demo on Thursday — want me to schedule a prep check-in and follow-up?"

> "Should I set up a prep reminder for your interview next week?"

Never ask again about the same event in the same conversation unless the user brings it up.

### If the user says yes

1. Confirm inferred details (title, date/time) — ask only what's missing
2. Ask which calendar to write the event to (skip if `default_user_calendar` is set)
3. Run:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/create_checkin.py \
  --title "<event title>" \
  --event-datetime "<ISO datetime>" \
  --event-duration <minutes> \
  --user-calendar "<calendar name>"
```

4. Confirm back with exact titles and times. Offer to adjust.

---

## Feature 2 — Calendar Monitoring

### Scanning upcoming events

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/scan_calendar.py
```

Returns JSON list of upcoming events with pre-computed scores and pattern data. Run at conversation start if last scan was > 30 minutes ago.

### Scoring calendar events (same 0–10 scale)

Additional factors beyond conversation signals:

| +Points | Factor |
|---------|--------|
| +2 | Duration > 60 minutes |
| +2 | External attendees (different email domain) |
| +2 | No description or agenda attached |
| +2 | Event within 24 hours, no OpenClaw check-in exists |
| +1 | Title contains: demo, presentation, interview, workshop, conference, launch, review, deadline |
| −3 | Recurring event AND pattern shows low historical stakes (e.g. routine standup) |
| +2 | Recurring event AND pattern shows high historical stakes (e.g. quarterly board review) |

### Reaching out

If score ≥ `calendar_threshold` and no OpenClaw check-in exists for this event:

> "You have a [event title] in [X hours/days]. Want me to help you prepare?"

If it's a **recurring event with history**, be specific:

> "Your weekly 1:1 with Sarah is tomorrow. Last time you wanted to follow up on the Q3 roadmap — want to prep talking points?"

### Post-event follow-up

When user opens conversation after a past-due OpenClaw follow-up event exists:

> "How did [event title] go? Want to capture any notes or action items?"

---

## Feature 3 — Pattern Learning

All event outcomes are stored in:
```
~/.openclaw/workspace/skills/proactive-agent/outcomes/<YYYY-MM-DD>_<slug>.json
```

Each outcome file contains:
```json
{
  "event_title": "...",
  "event_datetime": "...",
  "recurring_id": "...",
  "prep_done": true,
  "outcome_notes": "...",
  "action_items": [],
  "sentiment": "positive|neutral|negative",
  "follow_up_needed": false,
  "tags": []
}
```

### How patterns are used

Before scheduling check-ins or reaching out, read past outcomes for the same `recurring_id` (or similar title):

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/scan_calendar.py --patterns "<recurring_id>"
```

Use patterns to:
- **Adjust check-in timing** — if user consistently ignores prep check-ins 1 day before, try 2 hours before
- **Skip low-value recurring events** — if last 4 standups had no action items and user said "fine", lower score by 3
- **Raise stakes on recurring events with history** — if last board review had 6 action items, raise score by 2
- **Personalize prep prompts** — reference what was important last time

---

## Feature 4 — Auto Agenda & Talking Points

At prep check-in time, don't just ask "need help?" — generate a starting point based on:
- Event title and description
- Attendee list (if available)
- Past outcomes for recurring events
- Any context from recent conversations about this event

**Prep prompt template:**

> "Your [event title] is [in X hours / tomorrow]. Here's a starting point:
>
> **Suggested agenda:**
> 1. [inferred from title/description/past outcomes]
> 2. ...
>
> **Talking points to consider:**
> - [from recent conversation context]
> - [from last time's action items if recurring]
>
> Want to work on any of these, or is there something else you want to prep?"

For **interviews**: suggest STAR-format story prompts based on role/company if mentioned.
For **presentations**: suggest structure (hook, problem, solution, demo, CTA).
For **1:1s**: surface open action items from last session's outcome file.
For **standups**: pull any GitHub activity or recent work context if available.

---

## Feature 5 — Outcome Capture

After the follow-up conversation, write the outcome:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/capture_outcome.py \
  --event-title "<title>" \
  --event-datetime "<ISO datetime>" \
  --recurring-id "<id or empty>" \
  --notes "<captured notes>" \
  --action-items "<item1>|<item2>" \
  --sentiment "positive|neutral|negative" \
  --follow-up-needed "true|false"
```

Then sync to the user's preferred notes destination based on `notes_destination` config:

- **`local`**: writes JSON to `outcomes/` folder (always done regardless)
- **`apple-notes`**: `osascript -e 'tell app "Notes" to make new note with properties {name:"...", body:"..."}'`
- **`notion`**: calls Notion API if `notion-skill` is active

Always confirm with the user before writing: *"Want me to save these notes? Here's what I'll capture: [summary]"*

---

## Recurring Event Intelligence

Classify every event on first encounter:

| Type | Detection | Behavior |
|------|-----------|---------|
| **Routine low-stakes** | Recurring + short + internal + history shows no action items | Suppress until pattern changes. Check in only every 4th occurrence. |
| **Routine high-stakes** | Recurring + external OR history shows frequent action items | Always check in. Use last outcomes to personalize. |
| **One-off standard** | Not recurring, internal, < 60 min | Standard scoring |
| **One-off high-stakes** | Not recurring + external OR importance markers | Max prep attention. Offer full agenda prep. |

Store classification in outcome files under `"event_type"`.

---

## Tone & Rules

- **One question at a time.** Never stack multiple asks in one message.
- **Never repeat** — don't ask about the same event twice in the same conversation.
- **Always confirm** before creating calendar entries. Show exact title, date, time.
- **Always confirm** before writing outcome notes. Show a summary of what will be saved.
- **Respect "no"** — if user declines, drop it for that event entirely.
- **Be brief** — check-in prompts ≤ 2 sentences. Agenda suggestions are a starting point, not a wall of text.
- **Surface, don't overwhelm** — if multiple events need attention, address the most urgent one first.
- The OpenClaw calendar is internal — never tell the user to look at it; surface its data through conversation only.
