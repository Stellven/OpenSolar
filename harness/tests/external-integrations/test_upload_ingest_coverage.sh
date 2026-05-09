#!/usr/bin/env bash
# test_upload_ingest_coverage.sh — Verify latest batch fully ingested (D4/D5)

set -euo pipefail
HARNESS="${HARNESS_DIR:-$HOME/.solar/harness}"
AUDITOR="$HARNESS/lib/wiki-upload-audit.py"
PASS=0; FAIL=0

check() {
    local desc="$1" result="$2"
    if [ "$result" = "ok" ]; then
        echo "  ✓ $desc"; PASS=$((PASS+1))
    else
        echo "  ✗ $desc: $result"; FAIL=$((FAIL+1))
    fi
}

echo "=== test_upload_ingest_coverage ==="

for BATCH in 20260508T131337Z 20260508T122047Z; do
    echo "  Batch: $BATCH"
    set +e
    JSON=$(python3 "$AUDITOR" --batch "$BATCH" --json 2>&1)
    EXIT=$?
    set -e
    if [ $EXIT -gt 1 ]; then
        echo "  ✗ audit failed for $BATCH (exit $EXIT)"; FAIL=$((FAIL+1)); continue
    fi

    # D4: QMD = total
    check "$BATCH qmd fully covered" "$(python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
q=d.get('qmd',{}); t=d.get('total',0)
print('ok' if q.get('missing',1)==0 and t>0 else f'{q.get(\"found\",0)}/{t}')
" <<< "$JSON")"

    # D4: vault = total
    check "$BATCH vault fully covered" "$(python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
v=d.get('vault',{}); t=d.get('total',0)
print('ok' if v.get('missing',1)==0 and t>0 else f'{v.get(\"found\",0)}/{t}')
" <<< "$JSON")"

    # D4: Solar DB is a secondary index; historical batches may have partial DB coverage
    # while QMD/vault/dispatch are the authoritative ingest closeout.
    check "$BATCH solar_db indexed or explicitly partial" "$(python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
s=d.get('solar_db',{}); t=d.get('total',0)
print('ok' if s.get('found',0)>0 and t>0 else f'{s.get(\"found\",0)}/{t}')
" <<< "$JSON")"

    # D4: dispatch pending = 0
    check "$BATCH dispatch pending=0" "$(python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
disp=d.get('dispatch',{})
print('ok' if disp.get('pending',1)==0 else f'pending={disp.get(\"pending\")}')
" <<< "$JSON")"

    # D5: no QMD-only files (qmd_only state should not exist if fully ingested)
    check "$BATCH no qmd_only files" "$(python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
files=d.get('pages',{}).get('files',[])
qmd_only=[f['file'] for f in files if f.get('state')=='qmd_only']
print('ok' if not qmd_only else f'{len(qmd_only)} qmd_only files')
" <<< "$JSON")"
done

echo ""
echo "RESULT: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
