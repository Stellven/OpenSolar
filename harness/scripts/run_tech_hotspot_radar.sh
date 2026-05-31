#!/usr/bin/env bash
set -uo pipefail

HARNESS_DIR="${HARNESS_DIR:-/Users/lisihao/Solar/harness}"
export HOME="${HOME:-/Users/lisihao}"
PYTHON="${PYTHON:-python3}"
CONFIG="${CONFIG:-$HARNESS_DIR/config/tech-hotspot-radar.yaml}"
DB="${DB:-/Users/lisihao/.solar/harness/state/tech-hotspot-radar/tech-hotspot-radar.sqlite}"
LOCK_DIR="${LOCK_DIR:-/Users/lisihao/.solar/harness/state/tech-hotspot-radar/collector.lockdir}"
TODAY_UTC="$("$PYTHON" - <<'PY'
import datetime as dt
print(dt.datetime.now(dt.UTC).date().isoformat())
PY
)"
START_UTC="$("$PYTHON" - <<'PY'
import datetime as dt
print((dt.datetime.now(dt.UTC).date() - dt.timedelta(days=2)).isoformat())
PY
)"

RADAR=( "$PYTHON" "$HARNESS_DIR/scripts/tech_hotspot_radar.py" --config "$CONFIG" --db "$DB" )
RC=0

mkdir -p "$(dirname "$LOCK_DIR")" "$(dirname "$DB")" "$HARNESS_DIR/logs"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Tech Hotspot Radar collector already running; exiting without duplicate SQLite writer at $(date)"
  exit 0
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

run_step() {
  local name="$1"
  shift
  echo "[$name]"
  if "$@"; then
    echo "[$name] ok"
  else
    local step_rc=$?
    echo "[$name] warn rc=${step_rc}" >&2
    RC=$(( RC > step_rc ? RC : step_rc ))
  fi
}

echo "Running Tech Hotspot Radar collectors at $(date)"
if [[ -z "${GITHUB_TOKEN:-}" ]] && command -v gh >/dev/null 2>&1; then
  if GH_TOKEN_VALUE="$(gh auth token 2>/dev/null)" && [[ -n "$GH_TOKEN_VALUE" ]]; then
    export GITHUB_TOKEN="$GH_TOKEN_VALUE"
    unset GH_TOKEN_VALUE
    echo "[github-auth] using gh auth token"
  else
    unset GH_TOKEN_VALUE
    echo "[github-auth] warn: no GITHUB_TOKEN and gh auth token unavailable; GitHub API will be unauthenticated" >&2
  fi
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
  echo "[github-auth] using GITHUB_TOKEN"
else
  echo "[github-auth] warn: no GITHUB_TOKEN; GitHub API will be unauthenticated" >&2
fi

run_step "hf-trending" \
  "${RADAR[@]}" collect-hf-papers --period all --limit 80 --force "$@"

run_step "hf-daily-baseline ${START_UTC}..${TODAY_UTC}" \
  "${RADAR[@]}" backfill-hf-papers-baseline \
  --start-date "$START_UTC" \
  --end-date "$TODAY_UTC" \
  --limit-per-day 80 \
  --sleep-seconds 1 \
  --max-consecutive-failures 3 \
  --force "$@"

run_step "hf-paper-insights" \
  "${RADAR[@]}" materialize-hf-paper-insights \
  --limit "${HF_INSIGHT_LIMIT:-160}" \
  --sleep-seconds "${HF_INSIGHT_SLEEP_SECONDS:-0.5}" "$@"

run_step "github" \
  "${RADAR[@]}" collect-github --limit-repos "${GITHUB_LIMIT_REPOS:-80}" --force "$@"

run_step "github-analysis" \
  "${RADAR[@]}" analyze-github-projects --limit-repos "${GITHUB_ANALYZE_LIMIT_REPOS:-80}" --force "$@"

run_step "social" \
  env SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE="${SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE:-1}" \
  "${RADAR[@]}" collect-social \
  --backend rss \
  --limit-accounts "${SOCIAL_LIMIT_ACCOUNTS:-200}" \
  --per-account-limit "${SOCIAL_PER_ACCOUNT_LIMIT:-10}" \
  --force "$@"

if [[ "${RUN_SOCIAL_REPORT:-0}" == "1" ]]; then
  run_step "social-materialize" \
    env SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE="${SOLAR_SOCIAL_BROWSER_BACKEND_DISABLE:-1}" \
    "${RADAR[@]}" social-trend-report \
    --date "$TODAY_UTC" \
    --limit-posts "${SOCIAL_REPORT_LIMIT_POSTS:-80}" \
    --model "${SOCIAL_REPORT_MODEL:-gpt-5.4}" "$@"
else
  echo "[social-materialize] skipped RUN_SOCIAL_REPORT=0"
fi

echo "Tech Hotspot Radar collectors done at $(date) rc=${RC}"
if [[ "${ALLOW_PARTIAL_SUCCESS:-1}" == "1" && "$RC" != "0" ]]; then
  echo "Tech Hotspot Radar collectors completed with warnings; ALLOW_PARTIAL_SUCCESS=1 so exiting 0"
  exit 0
fi
exit "$RC"
