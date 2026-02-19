---
name: proactive-agent
version: 2.0.0
description: >
  Proactive life assistant that acts even when you're not in a conversation. Background daemon
  scans your calendar every 15 minutes and sends push notifications (system, Telegram) before
  you even open OpenClaw. SQLite memory with TF-IDF semantic search replaces flat JSON files.
  Detects calendar conflicts, back-to-back runs, and overloaded days. Pulls context from GitHub,
  Notion, and other active skills at prep time. Natural language rules engine: say "never bother
  me about standups" and it just works. Closes the loop: open action items auto-schedule follow-up
  events, weekly digest surfaces at Monday conversation open. One-command setup with clawhub OAuth
  (no Google Cloud Console required when connected via clawhub.ai).
  Trigger when: user mentions any upcoming event, meeting, presentation, deadline, interview, demo,
  travel, or recurring obligation; when judging whether to proactively reach out; when capturing
  notes or action items; when user asks about patterns, summaries, rules, or open action items.
---

# Proactive Agent v2.0

> The lobster that acts before you even open a conversation.

## What's new in v2.0

| Feature | v1.x | v2.0 |
|---------|------|------|
| Runs when | Conversation open | Every 15 min, background |
| Memory | Flat JSON files | SQLite + TF-IDF search |
| Notifications | In-conversation only | System push + Telegram |
| Conflict detection | None | Overlaps, back-to-back, overloaded days |
| Cross-skill | Aspirational | GitHub PRs, Notion pages, live at prep time |
| Rules | Edit JSON | Plain English: "never bother me about standups" |
| Action items | Saved only | Auto-schedule follow-up events |
| Weekly insights | None | Monday digest + quarterly summary |
| Setup | 7 manual steps | 1 command (clawhub OAuth) |

---

## Setup (run once)

```bash
bash ~/.openclaw/workspace/skills/proactive-agent/scripts/setup.sh
```

### Option A — clawhub OAuth (recommended, mobile-friendly)

1. Go to https://clawhub.ai/settings/integrations → Connect Google Calendar → copy your token
2. In `config.json` set `"clawhub_token": "your-token-here"`
3. Run `setup.sh` — credentials download automatically, no Google Cloud Console needed

### Option B — Manual Google credentials

1. https://console.cloud.google.com → New project → Enable Google Calendar API
2. Create OAuth 2.0 credentials (Desktop app) → download JSON
3. `mv ~/Downloads/credentials.json ~/.openclaw/workspace/skills/proactive-agent/credentials.json`
4. Run `setup.sh`

### Option C — Nextcloud CalDAV

```json
"calendar_backend": "nextcloud",
"nextcloud": { "url": "https://your-nextcloud.com", "username": "...", "password": "app-password" }
```
Run `setup.sh` — connects, creates OpenClaw calendar, saves URL.

### Install background daemon

```bash
bash ~/.openclaw/workspace/skills/proactive-agent/scripts/install_daemon.sh
```

- **macOS**: installs launchd plist, runs every 15 min automatically
- **Linux**: installs systemd user timer
- Logs: `~/.openclaw/workspace/skills/proactive-agent/daemon.log`

### Migrate existing outcomes to SQLite

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/memory.py --import-outcomes
```

---

## Configuration

`~/.openclaw/workspace/skills/proactive-agent/config.json`

Change any setting in plain English — OpenClaw updates the file.

| Key | Default | Description |
|-----|---------|-------------|
| `calendar_backend` | `google` | `google`, `nextcloud` |
| `timezone` | `UTC` | IANA tz e.g. `Europe/Berlin` |
| `daemon_interval_minutes` | `15` | How often daemon scans (set in plist/systemd) |
| `notification_channels` | `["openclaw","system"]` | `openclaw`, `system`, `telegram` |
| `telegram.bot_token` | `""` | Telegram bot token for push notifications |
| `telegram.chat_id` | `""` | Your Telegram chat ID |
| `clawhub_token` | `""` | Token from clawhub.ai/settings/integrations |
| `feature_daemon` | `true` | Enable background daemon notifications |
| `feature_memory` | `true` | Use SQLite memory (vs flat JSON) |
| `feature_conflicts` | `true` | Detect calendar conflicts |
| `feature_cross_skill` | `true` | Pull GitHub/Notion context at prep time |
| `feature_rules` | `true` | Natural language rules engine |
| `feature_intelligence_loop` | `true` | Auto follow-up events + weekly digest |

---

## Feature 1 — Conversation Radar

*(unchanged from v1.x — see scoring table and thresholds below)*

Score 0–10 silently after every exchange. Ask once, briefly, at threshold.

| +Points | Signal |
|---------|--------|
| +3 | Explicit future event |
| +3 | Active preparation language |
| +2 | Importance / stress markers |
| +2 | Hard deadline |
| +1 | Recurring obligation |
| +1 | Post-event reflection |
| −2 | Hypothetical or historical |

**Before asking**, check pending nudges from daemon:
```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/cross_skill.py --pending-nudges
```
If nudges exist, surface the most urgent one first instead of a new ask.

---

## Feature 2 — Calendar Monitoring + Conflict Detection

### Scan
```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/scan_calendar.py
```
Cache-aware (TTL from config). Returns `actionable` list pre-filtered to threshold + not snoozed.

### Conflict detection
```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/scan_calendar.py | \
  python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/conflict_detector.py
```

Detects and messages:
- **Overlaps** — two events at the same time: *"⚠️ Conflict: Demo and 1:1 overlap by 20 min Thursday. Which should move?"*
- **Overloaded days** — 4+ events in a day: *"📅 Heavy day Thursday: 5 events. Want to reschedule anything?"*
- **Back-to-back runs** — 3+ events with < 10 min gaps: *"🔴 4 meetings with no breaks Tuesday. Want to add buffer time?"*

Surface the highest-priority conflict first at conversation open. One message, one question.

---

## Feature 3 — Background Daemon

The daemon runs every 15 minutes independently. It:
1. Scans calendar (force-refresh)
2. Sends system / Telegram notifications for actionable events not yet notified today
3. Runs conflict detection and notifies on new conflicts
4. Checks for stale action items needing follow-up (7-day nudge)
5. Writes unshown nudges to `pending_nudges.json` for OpenClaw to surface

**Check status:**
```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/daemon.py --status
```

**View logs:**
```bash
tail -50 ~/.openclaw/workspace/skills/proactive-agent/daemon.log
```

**Notification channels** (set in config):
- `openclaw` — queued in `pending_nudges.json`, shown at next conversation open
- `system` — macOS/Linux desktop notification
- `telegram` — direct message via Telegram bot

---

## Feature 4 — SQLite Memory + Semantic Search

All outcomes stored in `memory.db`. Automatically migrated from flat JSON on first run.

**Save outcome:**
```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/memory.py \
  --save '{"event_title":"Demo","event_datetime":"2025-03-15T14:00:00+01:00","action_items":["Send deck"],"sentiment":"positive","follow_up_needed":true}'
```

**Semantic search:**
```bash
python3 memory.py --search "times I felt underprepared"
python3 memory.py --search "investor meetings that went well"
```

**Pattern lookup for recurring event:**
```bash
python3 memory.py --patterns "<recurring_event_id>"
```
Returns: avg action items, prep rate, sentiment distribution, recommendation.

**Open action items:**
```bash
python3 memory.py --open-actions
```

**Mark action resolved:**
```bash
python3 memory.py --resolve-action <action_id>
```

**Quarterly summary:**
```bash
python3 memory.py --summary --days 90
```
Returns: event type breakdown, sentiment trends, avg action items, insight string.

---

## Feature 5 — Cross-Skill Intelligence

At prep check-in time, enrich the agenda with live context from other active skills:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/cross_skill.py \
  --event-title "Sprint Review" \
  --event-type "one_off_high_stakes"
```

| Skill | What's pulled |
|-------|--------------|
| `github` | Open PRs and issues updated in last 3 days |
| `notion` | Pages matching the event title |
| *(more skills auto-detected)* | |

Append `context_block` to the prep agenda. Example:

> "Your Sprint Review is tomorrow at 10:00 CET.
>
> **Starting agenda:** ...
>
> **From GitHub:** 2 open PRs: *Fix auth flow*, *Update pricing page*
> **From Notion:** Related page: *Q1 Sprint Goals*
>
> Want to work on any of these?"

Only included if `feature_cross_skill: true` and the skill is installed.

---

## Feature 6 — Natural Language Rules

Users state rules in plain English. OpenClaw calls the rules engine to parse and save:

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/rules_engine.py \
  --parse "Never bother me about standups unless I haven't spoken in 2 weeks"

python3 rules_engine.py --parse "Always prep me 2 days before anything with the word board"
python3 rules_engine.py --parse "Suppress all events on weekends"
python3 rules_engine.py --parse "Boost score for investor"
python3 rules_engine.py --parse "Only check in every 4 occurrences of standup"
```

**List active rules:**
```bash
python3 rules_engine.py --list
```

**Delete a rule:**
```bash
python3 rules_engine.py --delete <rule_id>
```

Rules are applied automatically by `scan_calendar.py` and the daemon to adjust event scores.

When user states a new rule in conversation:
1. Parse it: `python3 rules_engine.py --parse "<rule>" --dry-run`
2. Show user what was understood: *"Got it — I'll suppress check-ins for standup events. Save this rule?"*
3. On confirmation: save without `--dry-run`

---

## Feature 7 — Post-Event Intelligence Loop

### Weekly digest (surface at Monday conversation open)

```bash
python3 ~/.openclaw/workspace/skills/proactive-agent/scripts/intelligence_loop.py --weekly-digest
```

If `has_content` is true, open Monday conversations with the digest:

> "Quick weekly recap:
> 📊 Last week: 8 events, 12 action items captured
> ⚠️ 3 open action items from past events
> 📅 Coming up: Board Review in 2 days (score 9/10)"

### Open action item follow-up

Check for stale action items (3+ days old, unresolved):
```bash
python3 intelligence_loop.py --check-followups
```

If items found, offer: *"You have 2 open action items from last week's demo. Want me to schedule time to tackle them?"*

On yes, auto-create calendar events:
```bash
python3 intelligence_loop.py --create-followups
```

### Quarterly summary

```bash
python3 intelligence_loop.py --summary --days 90
```

Surface proactively when 90 days have passed since last summary. Example insight:
> *"Heavy action item load — you averaged 4.2 per event this quarter. Want to set up a weekly review habit?"*

---

## Recurring Event Intelligence

| Type | Detection | Behaviour |
|------|-----------|---------|
| `routine_low_stakes` | Recurring + internal + avg 0 action items | Suppress. Every 4th occurrence only. |
| `routine_high_stakes` | Recurring + external OR avg ≥ 2 action items | Always check in, personalise with history. |
| `one_off_standard` | Not recurring, < 60 min, internal | Standard scoring. |
| `one_off_high_stakes` | Not recurring + external OR importance signals | Max prep. Full agenda + cross-skill context. |

Auto-upgrades classification as history accumulates in memory.db.

---

## Auto Agenda & Talking Points

At prep check-in time (in conversation or via daemon nudge):

| Event type | Auto-generated content |
|-----------|----------------------|
| Presentation / Demo | Hook → Problem → Solution → Demo → CTA |
| Interview | STAR prompts for role/company if mentioned |
| 1:1 | Open action items from `memory.py --open-actions` |
| Standup | GitHub activity from `cross_skill.py` if available |
| Board / Investor | Metrics, narrative arc, likely hard questions |
| Workshop | Desired outcomes, pre-reads |
| External (no history) | Company/attendee context to establish |

Template: 3–5 items max. Starting point, not an essay.

**Edge cases:**
- All-day event → ask "When's the best time to prep?"
- Untitled block → ask "I see a calendar block — what is it?"
- Detailed description → summarise it, don't duplicate it

---

## Error Handling

| Error | User message |
|-------|-------------|
| `calendar_backend_unavailable` | "Can't reach your calendar. Try again, or continue without calendar features?" |
| `failed_to_list_calendars` | "Trouble reading calendars. Check connection and that setup.sh ran." |
| `failed_to_create_events` | "Couldn't create check-in events — [detail]. Try again?" |
| Setup not run | "Calendar not set up yet. Run: `bash ~/.openclaw/workspace/skills/proactive-agent/scripts/setup.sh`" |
| `python_version_too_old` | "Python 3.8+ required. Install at https://www.python.org/downloads/" |
| Daemon not installed | "Background notifications are off. Run install_daemon.sh to enable." |

---

## Tone & Rules

- **One question at a time.** Never stack asks.
- **Daemon nudges first** — check pending_nudges before starting new asks at conversation open.
- **Never repeat** the same event ask twice in one conversation.
- **Always confirm** before writing calendar events (title, date, friendly time + tz).
- **Always confirm** before writing outcome notes (bullet summary).
- **Respect "no"** — dismissed forever; "not now" snoozed.
- **Be brief** — check-in prompts ≤ 2 sentences. Agenda = starting point.
- **Surface, don't overwhelm** — multiple actionable items → highest-scored first.
- **Timezone-aware** — always display in user's `timezone` config, never UTC.
- The OpenClaw calendar is internal — never tell users to look at it directly.
