#!/bin/bash
# Proactive Agent — One-time setup
# Sets up Google Calendar API access and creates the OpenClaw calendar

set -e

SKILL_DIR="$HOME/.openclaw/workspace/skills/proactive-agent"
CONFIG="$SKILL_DIR/config.json"
CREDS="$SKILL_DIR/credentials.json"

echo "🦞 Proactive Agent Setup"
echo "========================"

# Check Python 3.8+
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Please install Python 3.8+ first."
  exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info >= (3,8))")
if [ "$PYTHON_VER" != "True" ]; then
  echo "❌ Python 3.8+ required."
  exit 1
fi
echo "✅ Python 3 found"

# Check credentials.json
if [ ! -f "$CREDS" ]; then
  echo ""
  echo "❌ credentials.json not found at $CREDS"
  echo ""
  echo "To create it:"
  echo "  1. Go to https://console.cloud.google.com"
  echo "  2. Create project 'OpenClaw'"
  echo "  3. Enable Google Calendar API"
  echo "  4. Create OAuth 2.0 credentials (Desktop app)"
  echo "  5. Download and move: mv ~/Downloads/credentials.json $CREDS"
  echo ""
  exit 1
fi
echo "✅ credentials.json found"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install -q --upgrade google-api-python-client google-auth-oauthlib google-auth-httplib2
echo "✅ Dependencies installed"

# Initialize config.json if missing
if [ ! -f "$CONFIG" ]; then
  echo ""
  echo "📝 Creating default config.json..."
  cat > "$CONFIG" << 'EOF'
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
EOF
  echo "✅ config.json created"
fi

# Authenticate and create OpenClaw calendar
echo ""
echo "🔐 Authenticating with Google Calendar (browser will open)..."
python3 - << 'PYEOF'
import json, os, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SKILL_DIR = Path.home() / ".openclaw/workspace/skills/proactive-agent"
CREDS_FILE = SKILL_DIR / "credentials.json"
TOKEN_FILE = SKILL_DIR / "token.json"
CONFIG_FILE = SKILL_DIR / "config.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]

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

service = build("calendar", "v3", credentials=creds)

# Check if OpenClaw calendar already exists
calendars = service.calendarList().list().execute().get("items", [])
openclaw_id = None
for cal in calendars:
    if cal.get("summary") == "OpenClaw":
        openclaw_id = cal["id"]
        print(f"✅ OpenClaw calendar already exists (id: {openclaw_id})")
        break

if not openclaw_id:
    cal = service.calendars().insert(body={"summary": "OpenClaw"}).execute()
    openclaw_id = cal["id"]
    print(f"✅ OpenClaw calendar created (id: {openclaw_id})")

# Save to config
with open(CONFIG_FILE) as f:
    config = json.load(f)
config["openclaw_cal_id"] = openclaw_id
with open(CONFIG_FILE, "w") as f:
    json.dump(config, f, indent=2)

print("✅ OPENCLAW_CAL_ID saved to config.json")
print("\n🦞 Setup complete! Run scan_calendar.py to test.")
PYEOF
