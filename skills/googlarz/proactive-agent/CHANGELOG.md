# Changelog — proactive-agent

## [2.0.0] — 2025-02-19

### Added
- `daemon.py`: background process (launchd/systemd), scans every 15 min, sends system/Telegram notifications, queues nudges to `pending_nudges.json`
- `install_daemon.sh`: one-command launchd (macOS) or systemd user timer (Linux) install
- `memory.py`: SQLite-backed outcome store with TF-IDF semantic search, pattern analysis, open action items, quarterly summary, user rules storage
- `conflict_detector.py`: detects overlapping events, overloaded days (4+ events), back-to-back runs (3+ with <10 min gaps)
- `cross_skill.py`: live GitHub PR/issue context and Notion page lookup at prep time; pending_nudges consumer
- `rules_engine.py`: natural language rule parser — converts "never bother me about standups" to structured JSON rules applied at scoring time
- `intelligence_loop.py`: stale action item detection, auto-schedule follow-up calendar events, weekly Monday digest, quarterly summary trigger
- clawhub OAuth setup path in `setup.sh` — downloads Google credentials automatically from `clawhub_token` in config, no Google Cloud Console required
- `config.json`: `feature_*` flags for all new subsystems, `daemon_interval_minutes`, `notification_channels`, `telegram`, `clawhub_token`
- `pending_nudges.json`: daemon → conversation bridge for surfacing background-detected nudges

### Changed
- SKILL.md rewritten for v2.0 with v1.x vs v2.0 comparison table
- Memory layer: `scan_calendar.py` and `capture_outcome.py` now call `memory.py` for pattern data instead of reading flat JSON directly
- Rules applied automatically by scan_calendar.py via `memory.apply_rules()`

---

All notable changes to this skill are documented here.
Format: [version] — date — summary

---

## [3.0.1] — 2025-02-19

### Fixed
- `snoozed.json` now auto-purges expired (non-dismissed) entries on every load — file no longer grows unboundedly
- Python 3.8+ version guard added to all scripts — clear error message with fix URL instead of cryptic traceback
- `capture_outcome.py` AppleScript injection: body content now written to a temp file and read via `POSIX file` — no user data interpolated into script string
- `capture_outcome.py` pipe-in-action-items: added `--action-items-json` flag accepting a JSON array for items that contain pipe characters

---

## [3.0.0] — 2025-02-18

### Added
- `cal_backend.py`: unified calendar abstraction supporting Google Calendar API and Nextcloud CalDAV
- Nextcloud CalDAV backend via `caldav` + `icalendar` Python packages
- `setup.sh`: auto-detects backend, installs dependencies, verifies API end-to-end, auto-sets `user_email`
- Scan cache (`last_scan.json`) with configurable TTL — avoids redundant API calls
- Snooze & dismiss memory (`snoozed.json`) — persists across sessions
- Full timezone support: all datetimes preserved with tz offset, displayed in user's configured timezone
- Declined event filtering — skips events user has declined
- All-day event detection and handling
- Graceful error JSON on all script failure paths, with user-facing next steps in SKILL.md
- `.skillignore` to prevent credentials/tokens from being uploaded
- Auto agenda by event type: demo, interview, 1:1, standup, board/investor, workshop, external meeting
- Edge case handling: all-day events, untitled calendar blocks, events with detailed descriptions
- Calibrated scoring table with 7 concrete examples

### Changed
- Replaced `gcalcli` dependency with native Google Calendar API (`google-api-python-client`)
- `config.txt` replaced by `config.json` with full schema
- `scan_calendar.py` now outputs `actionable` list pre-filtered to threshold + not snoozed

---

## [2.0.0] — 2025-02-17

### Added
- Pattern learning: outcome history stored as JSON files, used to adjust scoring and personalise prep
- Auto agenda and talking points at prep check-in time
- Outcome capture to local JSON, Apple Notes, or Notion
- Recurring event intelligence: 4-tier classification (routine low/high-stakes, one-off standard/high-stakes)
- `scripts/` directory with `setup.sh`, `scan_calendar.py`, `create_checkin.py`, `capture_outcome.py`
- `config.json` replacing `config.txt`

### Changed
- Replaced `gcalcli` with Google Calendar API for calendar reads and writes

---

## [1.0.0] — 2025-02-16

### Added
- Initial release
- Conversation monitoring with 0–10 scoring
- Google Calendar integration via `gcalcli`
- Pre/post event check-in creation in OpenClaw calendar
- Configurable thresholds and time offsets via `config.txt`
