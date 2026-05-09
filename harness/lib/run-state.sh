#!/usr/bin/env bash
# lib/run-state.sh — Solar Harness 统一 state helper (Phase A)
# Phase A.2: extend rs_transition to also manage phase field
[[ -n "${RS_LOADED:-}" ]] && return 0
RS_LOADED=1
SPRINTS_DIR="${SPRINTS_DIR:-$HOME/.solar/harness/sprints}"

# ─── 读 ───

rs_exists() {
  local sid="$1"
  [[ -f "$SPRINTS_DIR/${sid}.status.json" ]]
}

rs_read_status() {
  local sid="$1"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || return 1
  python3 -c "import json; print(json.load(open('$sf')).get('status',''))" 2>/dev/null
}

rs_read_field() {
  local sid="$1" field="$2"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || return 1
  python3 -c "import json; print(json.load(open('$sf')).get('$field',''))" 2>/dev/null
}

# ─── 写 ───

# 状态推进: 读旧 status, 写新 status, 追加 history, 原子 rename
# 用法: rs_transition <sid> <new_status> <event> <by> [extra_json]
# extra_json 是可选 dict 字符串, 合并到 history entry
rs_transition() {
  local sid="$1" new_status="$2" event="$3" by="$4"
  local extra_json="${5:-}"
  [[ -z "$extra_json" ]] && extra_json="{}"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || { echo "rs_transition: sprint not found: $sid" >&2; return 1; }

  python3 - "$sf" "$new_status" "$event" "$by" "$extra_json" <<'PY'
import json, sys, os, tempfile, datetime
sf, new_status, event, by, extra_json = sys.argv[1:]
d = json.load(open(sf))
old_status = d.get('status', '')
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
d['status'] = new_status
d['updated_at'] = now
hist = {'ts': now, 'event': event, 'by': by}
try:
    extra = json.loads(extra_json) if extra_json else {}
    hist.update(extra)
except json.JSONDecodeError:
    pass
d.setdefault('history', []).append(hist)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(sf))
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2)
os.rename(tmp, sf)
print(f'OK: {os.path.basename(sf).replace(".status.json","")} {old_status} -> {new_status} (round={d.get("round",0)})')
PY
}

# 状态推进 + round 递增 (handoff/eval-fail 专用)
rs_transition_with_round_bump() {
  local sid="$1" new_status="$2" event="$3" by="$4"
  local extra_json="${5:-}"
  [[ -z "$extra_json" ]] && extra_json="{}"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || { echo "rs_transition_with_round_bump: sprint not found: $sid" >&2; return 1; }

  python3 - "$sf" "$new_status" "$event" "$by" "$extra_json" <<'PY'
import json, sys, os, tempfile, datetime
sf, new_status, event, by, extra_json = sys.argv[1:]
d = json.load(open(sf))
old_status = d.get('status', '')
old_round = d.get('round', 0)
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
d['status'] = new_status
d['round'] = old_round + 1
d['updated_at'] = now
hist = {'ts': now, 'event': event, 'by': by}
try:
    extra = json.loads(extra_json) if extra_json else {}
    hist.update(extra)
except json.JSONDecodeError:
    pass
d.setdefault('history', []).append(hist)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(sf))
with os.fdopen(fd, 'w') as f:
    json.dump(d, f, indent=2)
os.rename(tmp, sf)
print(f'OK: {os.path.basename(sf).replace(".status.json","")} {old_status} -> {new_status} (round={old_round}->{old_round+1})')
PY
}

# ─── 工具 ───

rs_validate_status() {
  case "$1" in
    drafting|active|planning|approved|reviewing|ready_for_review|\
    failed_review|needs_human_review|passed|done|eval_pass|failed|\
    architect_reviewing|architect_failed|building_parallel)
      return 0 ;;
    *) echo "rs_validate_status: invalid status: $1" >&2; return 1 ;;
  esac
}

rs_list_recent() {
  local n="${1:-20}"
  for f in "$SPRINTS_DIR"/sprint-*.status.json; do
    [[ -f "$f" ]] || continue
    local mt
    mt=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)
    echo "$mt $(basename "$f" .status.json)"
  done | sort -rn | head -n "$n" | awk '{print $2}'
}

rs_summary() {
  local sid="$1"
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || { echo "not found: $sid" >&2; return 1; }
  python3 -c "
import json
d = json.load(open('$sf'))
print(f\"id: {d.get('id','')}\")
print(f\"status: {d.get('status','')}\")
print(f\"round: {d.get('round',0)}\")
print(f\"updated_at: {d.get('updated_at','')}\")
print(f\"history: {len(d.get('history',[]))} entries\")
"
}

# ─── 三维状态机 (D4: topology + mode) ───

rs_set_topology() {
  local sid="$1" topology="$2"
  case "$topology" in standard|deliberation|research|mixture) ;; *) return 1 ;; esac
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || return 1
  python3 - "$sf" "$topology" <<'PY'
import json, sys, os, tempfile, datetime
sf, topology = sys.argv[1:]
d = json.load(open(sf))
old = d.get('topology', 'standard')
d['topology'] = topology
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
d['updated_at'] = now
d.setdefault('history', []).append({'ts': now, 'event': 'topology_changed', 'by': 'coordinator', 'old': old, 'new': topology})
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(sf))
with os.fdopen(fd, 'w') as f: json.dump(d, f, indent=2)
os.rename(tmp, sf)
PY
}

rs_set_mode() {
  local sid="$1" mode="$2"
  case "$mode" in fast|balanced|deep) ;; *) return 1 ;; esac
  local sf="$SPRINTS_DIR/${sid}.status.json"
  [[ -f "$sf" ]] || return 1
  python3 - "$sf" "$mode" <<'PY'
import json, sys, os, tempfile, datetime
sf, mode = sys.argv[1:]
d = json.load(open(sf))
old = d.get('mode', 'balanced')
d['mode'] = mode
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
d['updated_at'] = now
d.setdefault('history', []).append({'ts': now, 'event': 'mode_changed', 'by': 'coordinator', 'old': old, 'new': mode})
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(sf))
with os.fdopen(fd, 'w') as f: json.dump(d, f, indent=2)
os.rename(tmp, sf)
PY
}
