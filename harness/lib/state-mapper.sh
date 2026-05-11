#!/usr/bin/env bash
# lib/state-mapper.sh — Canonical State Mapper (S1, Coordinator Control Plane v2)
#
# Exports:
#   map_canonical_state <sid>              → JSON on stdout, exit 0
#   validate_transition <from> <to> <event> → exit 0=allow / 1=deny / 2=unknown
#
# Rules:
#   - Pure read-only: never writes to sprint files
#   - Fail-open: unrecognised combos → lifecycle_state=unknown
#   - Parse errors → lifecycle_state=corrupt, exit 0 (not exception)
#   - stderr silent; diagnostics only via mapped_at + error_hint fields

set -euo pipefail

STATE_MACHINE_JSON="${HARNESS_DIR:-$HOME/.solar/harness}/config/coordinator-state-machine.json"
SPRINTS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}/sprints"

# ── internal: read field from status.json via python3 (jq fallback) ──────────

_sm_read_json() {
    local file="$1"
    python3 -c "
import json, sys
try:
    d = json.load(open('$file'))
    sys.stdout.write(json.dumps(d))
except Exception as e:
    sys.stdout.write(json.dumps({'_parse_error': str(e)}))
" 2>/dev/null
}

_sm_get_field() {
    local json="$1" field="$2"
    python3 -c "
import json, sys
try:
    d = json.loads(sys.argv[1])
    v = d.get(sys.argv[2], '')
    print(v if v is not None else '', end='')
except Exception:
    print('', end='')
" "$json" "$field" 2>/dev/null
}

# ── map_canonical_state ───────────────────────────────────────────────────────
#
# Usage: map_canonical_state <sid>
# Output: JSON {lifecycle_state, lifecycle_role, source_status, source_phase,
#               source_handoff_to, mapped_at, error_hint}

map_canonical_state() {
    local sid="$1"
    local sf="${SPRINTS_DIR}/${sid}.status.json"
    local now
    now=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "1970-01-01T00:00:00Z")

    if [[ ! -f "$sf" ]]; then
        python3 -c "
import json, sys
print(json.dumps({
    'lifecycle_state': 'corrupt',
    'lifecycle_role': 'none',
    'source_status': '',
    'source_phase': '',
    'source_handoff_to': '',
    'mapped_at': '$now',
    'error_hint': 'status.json not found: $sf'
}))"
        return 0
    fi

    local raw_json
    raw_json=$(_sm_read_json "$sf")

    # Parse error → corrupt
    if python3 -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if '_parse_error' not in d else 1)" "$raw_json" 2>/dev/null; then
        : # ok
    else
        local err
        err=$(_sm_get_field "$raw_json" "_parse_error")
        python3 -c "
import json
print(json.dumps({
    'lifecycle_state': 'corrupt',
    'lifecycle_role': 'none',
    'source_status': '',
    'source_phase': '',
    'source_handoff_to': '',
    'mapped_at': '$now',
    'error_hint': 'parse error: $err'
}))"
        return 0
    fi

    local st phase handoff_to
    st=$(_sm_get_field "$raw_json" "status")
    phase=$(_sm_get_field "$raw_json" "phase")
    handoff_to=$(_sm_get_field "$raw_json" "handoff_to")

    python3 -c "
import json, sys

raw = json.loads(sys.argv[1])
st = sys.argv[2]
phase = sys.argv[3]
handoff_to = sys.argv[4]
now = sys.argv[5]

lc = 'unknown'
role = 'none'
hint = ''

# ── KEY: legacy combo mapping (order matters — most-specific first) ──────────

if st == 'drafting':
    if phase == 'prd_ready' and handoff_to == 'planner':
        lc = 'prd_ready'
        role = 'planner'
        hint = 'legacy fix: drafting+prd_ready+planner was mis-routed to PM'
    elif phase in ('planning_complete',):
        lc = 'planning_complete'
        role = 'builder_main'
    elif phase in ('prd_ready',):
        lc = 'prd_ready'
        role = 'planner'
    else:
        lc = 'intake'
        role = 'pm'

elif st == 'active':
    if phase in ('planning_complete', 'planner_plan', 'plan_reviewed'):
        lc = 'planning_complete'
    elif phase in ('g0_passed',):
        lc = 'building'
    elif phase in ('slices_dispatched', 's1_dispatched', 's2_dispatched', 's6_dispatched'):
        lc = 'building'
    elif phase in ('s0_dispatched', 's0_in_progress'):
        lc = 'building'
    elif phase in ('s0_ready_for_eval', 's1_ready_for_eval', 's2_ready_for_eval',
                   's3_ready_for_eval', 's4_ready_for_eval', 's5_ready_for_eval',
                   's6_ready_for_eval', 's7_ready_for_eval'):
        lc = 'build_complete'
        role = 'evaluator'
    elif phase in ('building', 'build_complete'):
        lc = 'building'
    else:
        # default: active with plan expected
        lc = 'planning_complete'
    if role == 'none':
        role = 'builder_main'

elif st == 'planning':
    lc = 'planning'
    role = 'evaluator'

elif st == 'planning_complete':
    lc = 'planning_complete'
    role = 'builder_main'

elif st == 'approved':
    lc = 'planning_complete'
    role = 'builder_main'

elif st in ('reviewing', 'ready_for_review', 'architect_reviewing'):
    lc = 'build_complete'
    role = 'evaluator'

elif st in ('failed_review', 'architect_failed'):
    lc = 'blocked'
    role = 'builder_main'

elif st == 'building_parallel':
    lc = 'building'
    role = 'builder_main'

elif st == 'needs_human_review':
    lc = 'blocked'
    role = 'planner'

elif st in ('passed', 'done', 'eval_pass', 'finalized', 'superseded'):
    lc = 'done'
    role = 'none'

elif st == 'failed':
    lc = 'failed'
    role = 'none'

elif st == 'queued':
    if phase in ('planning_complete',) or handoff_to in ('builder', 'builder_main'):
        lc = 'building'
        role = 'builder_main'
    elif phase in ('prd_ready', 'contract_ready') or handoff_to == 'planner':
        lc = 'planning'
        role = 'planner'
    elif handoff_to == 'evaluator':
        lc = 'build_complete'
        role = 'evaluator'
    else:
        lc = 'intake'
        role = 'pm'

else:
    lc = 'unknown'
    role = 'none'
    hint = f'unrecognised status: {st!r}'

out = {
    'lifecycle_state': lc,
    'lifecycle_role': role,
    'source_status': st,
    'source_phase': phase,
    'source_handoff_to': handoff_to,
    'mapped_at': now,
}
if hint:
    out['error_hint'] = hint

print(json.dumps(out))
" "$raw_json" "$st" "$phase" "$handoff_to" "$now"
    return 0
}

# ── validate_transition ───────────────────────────────────────────────────────
#
# Usage: validate_transition <from_state> <to_state> <event>
# Exit:  0 = transition allowed
#        1 = transition denied (reason on stdout)
#        2 = transition unknown (not in table)
# Output: JSON {allowed, reason}

validate_transition() {
    local from_state="$1" to_state="$2" event="$3"

    python3 -c "
import json, sys

with open('$STATE_MACHINE_JSON') as f:
    sm = json.load(f)

from_state = sys.argv[1]
to_state   = sys.argv[2]
event      = sys.argv[3]

transitions = sm.get('transitions', [])
matched = []
for t in transitions:
    t_from = t.get('from', '')
    t_to   = t.get('to', '')
    t_ev   = t.get('event', '')
    if (t_from == '*' or t_from == from_state) and (not t_to or t_to == to_state):
        if not t_ev or t_ev == event or event in t_ev.split('|'):
            matched.append(t)

if not matched:
    # Check if reverse direction is known (deny explicitly)
    deny_check = [t for t in transitions if t.get('from') == to_state and t.get('to') == from_state]
    if deny_check:
        print(json.dumps({'allowed': False, 'reason': f'reverse transition {from_state}->{to_state} not in table; only {to_state}->{from_state} is known'}))
        sys.exit(1)
    print(json.dumps({'allowed': None, 'reason': f'no rule for {from_state}->{to_state} via {event}'}))
    sys.exit(2)

# Any match = allowed
t = matched[0]
print(json.dumps({'allowed': True, 'reason': f'matched rule {t.get(\"id\",\"?\")}', 'rule': t}))
sys.exit(0)
" "$from_state" "$to_state" "$event"
    return $?
}

# ── is_terminal_state ─────────────────────────────────────────────────────────
is_terminal_state() {
    local state="$1"
    case "$state" in
        done|failed|quarantined|superseded) return 0 ;;
        *) return 1 ;;
    esac
}

# ── is_corrupt_state ──────────────────────────────────────────────────────────
is_corrupt_state() {
    local state="$1"
    [[ "$state" == "corrupt" ]]
}
