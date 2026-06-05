#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-${SOLAR_REPO:-$HOME/Solar}/harness}"
PYTHON="${PYTHON:-python3}"
ACCOUNTS="${AI_INFLUENCE_ACCOUNTS:-$HARNESS_DIR/ai-influence-digest/references/accounts_extended.txt}"
STATE_DIR="${AI_INFLUENCE_STATE_DIR:-$HOME/.solar/harness/state/ai-influence-digest}"
RAW_DIR="${AI_INFLUENCE_RAW_DIR:-$HOME/Knowledge/_raw/ai-influence-daily-digest}"
SLEEP_SECONDS="${AI_INFLUENCE_SLEEP_SECONDS:-1.0}"
LOCAL_TZ="${LOCAL_TZ:-America/Toronto}"
REPORT_DATE="${AI_INFLUENCE_REPORT_DATE:-$("$PYTHON" - <<'PY'
import datetime as dt
import os
from zoneinfo import ZoneInfo

today = dt.datetime.now(ZoneInfo(os.environ.get("LOCAL_TZ", "America/Toronto"))).date()
print((today - dt.timedelta(days=1)).isoformat())
PY
)}"
MAIL_TO_CONFIG="${AI_INFLUENCE_MAIL_CONFIG:-${SOLAR_HOME:-$HOME/.solar}/harness/state/ai-influence-mail-config.json}"
if [[ -z "${AI_INFLUENCE_MAIL_TO:-}" && -f "$MAIL_TO_CONFIG" ]]; then
  AI_INFLUENCE_MAIL_TO="$("$PYTHON" - "$MAIL_TO_CONFIG" <<'PY'
import json, sys
try:
    print(json.load(open(sys.argv[1], encoding="utf-8")).get("to", ""))
except Exception:
    print("")
PY
)"
  export AI_INFLUENCE_MAIL_TO
fi
export AI_INFLUENCE_SEND_MAIL="${AI_INFLUENCE_SEND_MAIL:-true}"

exec "$PYTHON" "$HARNESS_DIR/scripts/ai_influence_daily.py" \
  --date "$REPORT_DATE" \
  --accounts "$ACCOUNTS" \
  --state-dir "$STATE_DIR" \
  --raw-dir "$RAW_DIR" \
  --sleep-between-accounts "$SLEEP_SECONDS" \
  "$@" \
  run
