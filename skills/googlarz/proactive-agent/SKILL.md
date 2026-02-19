---
name: proactive-agent
version: 3.0.0
description: >
  Proactive life assistant that silently watches every conversation and your calendar to offer
  timely, context-aware help — before you ask. Manages a dedicated "OpenClaw" calendar for
  pre/post event check-ins. Learns your patterns over time. Auto-generates agenda and talking
  points at prep time. Captures outcomes and action items after events. Treats weekly standups
  differently from high-stakes investor demos. Supports Google Calendar API and Nextcloud CalDAV.
  Trigger when: user mentions any upcoming event, meeting, presentation, deadline, interview,
  demo, travel, or recurring obligation; when judging whether to proactively reach out; or when
  capturing notes/action items after an event.
---

# Proactive Agent

> The lobster that reaches out before you even know you need it.

## What it does

| Feature | Description |
|---------|-------------|
| **Conversation radar** | Silently scores every exchange 0–10. Asks once, briefly, if something calendar-worthy is detected. |
| **Calendar monitoring** | Scans upcoming events and reaches out proactively when it matters. |
| **Pattern learning** | Remembers how past events went. Gets smarter about when/how to intervene. |
| **Auto prep** | At check-in time, generates actual agenda and talking points — not just "need help?" |
| **Outcome capture** | After events, captures notes and action items to local JSON, Apple Notes, or Notion. |
| **Recurring intelligence** | Suppresses low-value standups. Prioritises high-stakes recurring events. |
| **Snooze & dismiss** | Respects "not now" across sessions. Never nags. |
| **Dual backend** | Google Calendar API or Nextcloud CalDAV — user's choice. |

---

## Setup (run once)

```bash
bash ~/.openclaw/workspace/skills/proactive-agent/scripts/setup.sh
```

The setup script auto-detects the backend from `config.json` (`"calendar_backend": "google"` or `"nextcloud"`), installs dependencies, authenticates, and creates the **OpenClaw** calendar.

### Google Calendar (default)

Prerequisites (~3 min, one-time):
1. https://console.cloud.google.com → New project "OpenClaw"
2. Enable **Google Calendar API**
3. Create **OAuth 2.0 credentials** → Desktop app → download JSON
4. `mv ~/Downloads/credentials.json ~/.openclaw/workspace/skills/proactive-agent/credentials.json`
5. Run `setup.sh` — browser opens once for OAuth, then never again

The script auto-reads your primary calendar email and sets `user_email` in `config.json`.

### Nextcloud CalDAV

1. In `config.json` set:
   ```json
   "calendar_backend": "nextcloud",
   "nextcloud": {
     "url": "https://your-nextcloud.com",
     "username": "your-username",
     "password": "your-app-password"
   }
   ```
   Use an **app password** (Nextcloud Settings → Security), not your account password.
2. Run `setup.sh` — connects, lists calendars, creates OpenClaw calendar, saves URL to config.

---

## Configuration

`~/.openclaw/workspace/skills/proactive-agent/config.json`

Adjust any setting by telling OpenClaw in plain language — it will update the file.

```json
{
  "calendar_backend": "google",
  "pre_checkin_offset_default": "1 day",
  "pre_checkin_offset_same_day": "1 hour",
  "post_checkin_offset": "30 minutes",
  "conversation_threshold": 5,
  "calendar_threshold": 6,
  "feature_conversation": true,
  "feature_calendar": true,
  "default_user_calendar": "",
  "timezone": "Europe/Berlin",
  "user_email": "you@example.com",
  "notes_destination": "local",
  "notes_path": "~/.openclaw/workspace/skills/proactive-agent/outcomes/",
  "scan_days_ahead": 7,
  "scan_cache_ttl_minutes": 30,
  "openclaw_cal_id": "",
  "nextcloud": {
    "url": "",
    "username": "",
    "password": "",
    "openclaw_calendar_url": ""
  }
}
```

| Key | Default | What it does |
|-----|---------|-------------|
| `calendar_backend` | `google` | `google` or `nextcloud` |
| `timezone` | `UTC` | IANA timezone, e.g. `Europe/Berlin`, `America/New_York` |
| `user_email` | `""` | Used to detect external attendees. Auto-set by setup.sh for Google. |
| `conversation_threshold` | `5` | Min score to ask about creating a check-in |
| `calendar_threshold` | `6` | Min score to proactively reach out |
| `scan_cache_ttl_minutes` | `30` | How long before re-scanning calendar (avoids API spam) |
| `notes_destination` | `local` | `local`, `apple-notes`, or `notion` |

---

## Feature 1 — Conversation Radar

Run **silently** after every exchange. Never mention the scoring to the user.

### Score 0–10

| +Points | Signal | Examples |
|---------|--------|---------|
| +3 | Explicit future event | "presentation Friday", "demo on the 23rd", "interview next week" |
| +3 | Active preparation | "working on slides", "prepping for", "getting ready for" |
| +2 | Importance / stress markers | "really important", "nervous about", "big client", "first time doing this" |
| +2 | Hard deadline | "due by", "deadline is", "needs to ship before" |
| +1 | Recurring obligation | "weekly standup", "quarterly review", "1:1 tomorrow" |
| +1 | Post-event reflection | "just got out of", "the meeting went", "my talk is done" |
| −2 | Hypothetical or historical | "what if I had a meeting", "last year's conference" |

**Calibrated examples (must match these scores ±1):**

| Message | Score | Reason |
|---------|-------|--------|
| "Big investor demo Thursday" | 9 | explicit event + importance |
| "I should prep for my standup" | 5 | recurring + prep language |
| "How do you structure presentations?" | 3 | general, no specific event |
| "My talk yesterday went well" | 2 | past, no action needed |
| "Just booked flights for the conference" | 7 | explicit future + travel |
| "Deadline for the feature is Friday" | 7 | explicit deadline |
| "We might have a review at some point" | 2 | vague, no time anchor |

### Thresholds

| Score | Action |
|-------|--------|
| 0–4 | Say nothing. Continue conversation. |
| 5–7 | One sentence at the **end** of your reply. |
| 8–10 | Ask **before** anything else. |

### Asking

One sentence. One question. End of message.

> "Sounds like you have a big investor demo Thursday — want me to set up a prep check-in and follow-up?"

> "Should I schedule a reminder before your interview next week?"

Never ask twice about the same event in the same conversation. If declined, drop it entirely.

### Creating check-ins

When user says yes:
1. Confirm inferred title and date/time — ask only what's missing
2. Ask which calendar if `default_user_calendar` is unset

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/create_checkin.py \
  --title "<event title>" \
  --event-datetime "<ISO 8601 with timezone, e.g. 2025-03-15T14:00:00+01:00>" \
  --event-duration <minutes> \
  --user-calendar "<calendar name>"
```

Confirm back with **friendly time strings** (e.g. "Thursday Mar 13 at 9:00 AM CET"). Offer to adjust.

---

## Feature 2 — Calendar Monitoring

At the start of each conversation, run:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/scan_calendar.py
```

Uses cache — only hits the API if last scan was > `scan_cache_ttl_minutes` ago. Reads `actionable` from the output (pre-filtered to score ≥ threshold, not snoozed).

### Calendar scoring factors

| +Points | Factor |
|---------|--------|
| +2 | Duration > 60 min |
| +2 | External attendees detected |
| +2 | No description or agenda |
| +2 | Starts within 24 hours, no check-in yet |
| +1 | Title has high-stakes keyword |
| −1 | Title has routine keyword (standup, sync, scrum) |
| −3 | Recurring, history shows 0 avg action items |
| +2 | Recurring, history shows ≥ 3 avg action items |
| −5 | OpenClaw check-in already exists |
| (skip) | User declined this event |

### Reaching out

If `actionable` list is non-empty, address the **highest-scored event first** when the user next speaks.

**Generic:**
> "You have a [event title] in [X hours/days]. Want help preparing?"

**Recurring with history:**
> "Your weekly 1:1 with Sarah is tomorrow. Last time you had 3 action items open — want to prep?"

**Post-event (when follow-up check-in is past due):**
> "How did [event title] go? Want to capture notes or action items?"

### Snooze / dismiss

If user says "not now" or "remind me later":

```bash
# Snooze for 4 hours
python3 scan_calendar.py --snooze <event_id> 4

# Never ask again about this event
python3 scan_calendar.py --dismiss <event_id>
```

---

## Feature 3 — Pattern Learning

Outcomes stored at:
```
~/.openclaw/workspace/skills/proactive-agent/outcomes/YYYY-MM-DD_slug.json
```

Schema:
```json
{
  "event_title": "Investor Demo",
  "event_datetime": "2025-03-15T14:00:00+01:00",
  "recurring_id": "",
  "event_type": "one_off_high_stakes",
  "captured_at": "2025-03-15T16:05:00Z",
  "prep_done": true,
  "outcome_notes": "Demo went well. Investors liked product.",
  "action_items": ["Send deck", "Schedule follow-up call"],
  "sentiment": "positive",
  "follow_up_needed": true,
  "tags": ["fundraising", "demo"]
}
```

Fetch pattern history before scheduling:
```bash
python3 scan_calendar.py --patterns "<recurring_id>"
```

Use patterns to:
- **Adjust timing** — if user ignores 1-day prep check-ins, switch to 2-hour
- **Suppress routine events** — if last 4 standups had zero action items, stop asking
- **Escalate recurring high-stakes** — board review with 5 avg action items → always prep
- **Personalise prompts** — reference open items from last outcome

---

## Feature 4 — Auto Agenda & Talking Points

At prep check-in time, don't just ask "need help?" — open with a concrete starting point.

**Structure by event type:**

| Type | Auto-generated content |
|------|----------------------|
| **Presentation / Demo** | Hook → Problem → Solution → Demo flow → CTA. Suggest what to cut if time is short. |
| **Interview** | STAR-format story prompts based on role/company if mentioned. Common questions for the domain. |
| **1:1** | Open action items from last outcome file. Blockers, wins, asks. |
| **Standup** | Pull recent GitHub activity if github-skill is active. Yesterday / Today / Blockers. |
| **Board / Investor** | Metrics to prepare. Narrative arc. Likely hard questions. |
| **Workshop / Offsite** | Desired outcomes, pre-reads, icebreaker if relevant. |
| **External meeting (no history)** | Research attendee's company/role. Key context to establish. |

**Template:**

> "Your [event] is [in X / tomorrow at TIME TZ].
>
> **Starting agenda:**
> 1. [inferred item]
> 2. [inferred item]
>
> **Talking points:**
> - [from context / last outcomes / open action items]
>
> Want to work on any of these, or something else?"

Keep the list to 3–5 items max. Never a wall of text.

**Edge cases:**
- All-day event with no time → don't offer timed check-ins; offer a "when's the best time to prep?" question instead
- No-title event → ask "I see a calendar block — what is it? Want to prep?"
- Event already has a detailed description → summarise it, don't duplicate it

---

## Feature 5 — Outcome Capture

After the follow-up conversation:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/capture_outcome.py \
  --event-title "Investor Demo" \
  --event-datetime "2025-03-15T14:00:00+01:00" \
  --recurring-id "" \
  --notes "Demo went well. Investors liked product." \
  --action-items "Send deck|Schedule follow-up call|Update pricing page" \
  --sentiment "positive" \
  --follow-up-needed "true" \
  --tags "fundraising,demo"
```

**Always confirm before saving:**
> "Want me to save these notes? I'll capture:
> - 2 action items: Send deck, Schedule follow-up call
> - Sentiment: positive
> - Follow-up needed: yes"

**Destinations:**
| `notes_destination` | Where it goes |
|---------------------|--------------|
| `local` | `outcomes/` JSON (always written regardless) |
| `apple-notes` | New note via AppleScript |
| `notion` | Notion DB page via API (requires `NOTION_API_KEY` + `NOTION_OUTCOMES_DB_ID` env vars) |

---

## Recurring Event Intelligence

Classify every new event on first encounter. Store in outcome file under `"event_type"`.

| Type | Detection | Behaviour |
|------|-----------|---------|
| `routine_low_stakes` | Recurring + internal + avg 0 action items | Ask every 4th occurrence only. Suppress otherwise. |
| `routine_high_stakes` | Recurring + external OR avg ≥ 2 action items | Always check in. Personalise using history. |
| `one_off_standard` | Not recurring, < 60 min, internal | Standard scoring. Offer light prep. |
| `one_off_high_stakes` | Not recurring + external OR importance signals | Maximum prep attention. Full agenda + talking points. |

Classification upgrades automatically as history accumulates.

---

## Error Handling

If any script exits with error JSON (`{"error": ...}`):

| Error | What to tell user |
|-------|------------------|
| `calendar_backend_unavailable` | "I can't reach your calendar right now. Want me to try again, or continue without calendar features?" |
| `failed_to_list_calendars` | "Having trouble reading your calendars. Check your connection and that setup.sh has been run." |
| `failed_to_create_events` | "Couldn't create the check-in events — [detail]. Want to try again?" |
| Setup not run | "Looks like the calendar isn't set up yet. Run: `bash ~/.openclaw/workspace/skills/proactive-agent/scripts/setup.sh`" |

Never silently fail. Always surface the issue with a clear next step.

---

## Tone & Rules

- **One question at a time.** Never stack asks.
- **Never repeat** the same event ask twice in one conversation.
- **Always confirm** before writing calendar events — show title, date, friendly time + timezone.
- **Always confirm** before writing outcome notes — show a bullet summary.
- **Respect "no"** — dismissed permanently; "not now" snoozed per `--snooze`.
- **Be brief** — check-in prompts ≤ 2 sentences. Agenda = starting point, not an essay.
- **Surface, don't overwhelm** — multiple actionable events → address highest-scored first.
- **Timezone-aware** — always display times in the user's `timezone` config, never UTC.
- The OpenClaw calendar is internal — never tell users to open it. Surface its data in conversation only.
