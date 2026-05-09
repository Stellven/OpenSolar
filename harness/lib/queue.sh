#!/usr/bin/env bash
# lib/queue.sh — Per-sprint dispatch queue (S2, Coordinator Control Plane v2)
#
# Exports:
#   queue_enqueue <sid> <intent> [priority] → enqueue; prints "ok" or "duplicate"
#   queue_pop     <sid>           → dequeue first item; prints JSON or nothing
#   queue_peek    <sid>           → peek first item; prints JSON or nothing
#   queue_depth   <sid>           → prints integer count of pending items
#
# Rules:
#   - One JSONL file per sid: run/queue/<sid>.jsonl
#   - Priority FIFO semantics; each item: {id, sid, intent, priority, retry_count, intent_hash, enqueued_at, consumed}
#   - Dedup: same (sid, intent_hash) within 24h blocks re-enqueue
#   - Crash recovery: peek/pop rely only on file content, not in-memory state
#   - Atomic mutations via Python fcntl.flock + atomic rename

_QUEUE_DIR="${HARNESS_DIR:-$HOME/.solar/harness}/run/queue"

_queue_file() { echo "${_QUEUE_DIR}/${1}.jsonl"; }

# ── queue_enqueue ─────────────────────────────────────────────────────────────
queue_enqueue() {
    local sid="${1:?queue_enqueue: sid required}"
    local intent="${2:?queue_enqueue: intent required}"
    local priority="${3:-0}"
    local qf
    qf=$(_queue_file "$sid")

    python3 -c "
import json, datetime, hashlib, fcntl, os, sys, secrets

sid      = sys.argv[1]
intent   = sys.argv[2]
priority = int(sys.argv[3])
qf       = sys.argv[4]

intent_hash = hashlib.sha256(intent.encode()).hexdigest()[:12]
now         = datetime.datetime.utcnow()
now_str     = now.strftime('%Y-%m-%dT%H:%M:%SZ')
cutoff      = (now - datetime.timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')

os.makedirs(os.path.dirname(qf), exist_ok=True)

# Read existing items under lock
existing = []
lock_path = qf + '.lock'
with open(lock_path, 'a') as lf:
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if os.path.exists(qf):
            with open(qf) as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try: existing.append(json.loads(line))
                    except Exception: pass

        # Dedup check: same intent_hash within 24h, not consumed
        for item in existing:
            if (item.get('intent_hash') == intent_hash
                    and not item.get('consumed', False)
                    and item.get('enqueued_at', '') >= cutoff):
                print('duplicate')
                sys.exit(0)

        # Append new item
        item_id = 'q-' + now.strftime('%Y%m%dT%H%M%SZ') + '-' + secrets.token_hex(3)
        new_item = {
            'id': item_id, 'sid': sid, 'intent': intent,
            'priority': priority, 'retry_count': 0,
            'intent_hash': intent_hash, 'enqueued_at': now_str, 'consumed': False,
        }
        with open(qf, 'a') as f:
            f.write(json.dumps(new_item, ensure_ascii=False) + '\n')
        print('ok')
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
" "$sid" "$intent" "$priority" "$qf" 2>/dev/null
}

# ── queue_peek ────────────────────────────────────────────────────────────────
queue_peek() {
    local sid="${1:?queue_peek: sid required}"
    local qf
    qf=$(_queue_file "$sid")
    [[ -f "$qf" ]] || return 0

    python3 -c "
import json, sys
qf = sys.argv[1]
pending = []
with open(qf) as f:
    for idx, line in enumerate(f):
        line = line.strip()
        if not line: continue
        try: item = json.loads(line)
        except Exception: continue
        if not item.get('consumed', False):
            pending.append((idx, item))
if pending:
    pending.sort(key=lambda pair: (-int(pair[1].get('priority', 0)), pair[0]))
    print(json.dumps(pending[0][1]))
" "$qf" 2>/dev/null
}

# ── queue_pop ─────────────────────────────────────────────────────────────────
queue_pop() {
    local sid="${1:?queue_pop: sid required}"
    local qf
    qf=$(_queue_file "$sid")
    [[ -f "$qf" ]] || return 0

    python3 -c "
import json, fcntl, os, sys

qf = sys.argv[1]
lock_path = qf + '.lock'

with open(lock_path, 'a') as lf:
    try:
        fcntl.flock(lf, fcntl.LOCK_EX)
        if not os.path.exists(qf):
            sys.exit(0)

        items = []
        with open(qf) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: items.append(json.loads(line))
                except Exception: pass

        candidates = [(i, item) for i, item in enumerate(items) if not item.get('consumed', False)]
        candidates.sort(key=lambda pair: (-int(pair[1].get('priority', 0)), pair[0]))

        popped = None
        if candidates:
            i, item = candidates[0]
            popped = item
            items[i] = dict(item, consumed=True)

        if popped is None:
            sys.exit(0)

        # Atomic rewrite: write to temp then rename
        tmp = qf + '.tmp'
        with open(tmp, 'w') as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        os.replace(tmp, qf)

        print(json.dumps(popped))
    finally:
        fcntl.flock(lf, fcntl.LOCK_UN)
" "$qf" 2>/dev/null
}

# ── queue_depth ───────────────────────────────────────────────────────────────
queue_depth() {
    local sid="${1:?queue_depth: sid required}"
    local qf
    qf=$(_queue_file "$sid")
    [[ -f "$qf" ]] || { echo 0; return 0; }

    python3 -c "
import json, sys
count = 0
with open(sys.argv[1]) as f:
    for line in f:
        line = line.strip()
        if not line: continue
        try:
            item = json.loads(line)
            if not item.get('consumed', False):
                count += 1
        except Exception: pass
print(count)
" "$qf" 2>/dev/null || echo 0
}
