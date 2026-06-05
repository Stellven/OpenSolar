#!/usr/bin/env bash
set -euo pipefail

json=false
no_remote=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) json=true; shift ;;
    --no-remote) no_remote=true; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

python3 - "$json" "$no_remote" <<'PY'
import hashlib
import json
import pathlib
import subprocess
import sys
import datetime as dt

emit_json = sys.argv[1] == "true"
no_remote = sys.argv[2] == "true"
home = pathlib.Path.home()
local = home / ".solar" / "harness"
manifest = local / "state" / "mac-mini-sync-required.jsonl"
remote = "lisihao@${SOLAR_REMOTE_IP}"
remote_dir = "${HARNESS_DIR}"
critical = [
    "solar-harness.sh",
    "lib/skill_healthcheck.py",
    "lib/skill_evolution_runner.py",
    "tests/evolution/test-skill-evolution-runner.sh",
    "evals/packs/skill-healthcheck-evolution/eval.json",
]

def run(cmd, timeout=20):
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

entries = []
if manifest.exists():
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            continue

def manifest_key(item):
    return json.dumps({
        "reason": item.get("reason", ""),
        "files": item.get("files", []),
        "sprint_artifacts": item.get("sprint_artifacts", []),
    }, ensure_ascii=False, sort_keys=True)

latest_by_key = {}
for item in entries:
    latest_by_key[manifest_key(item)] = item
effective_entries = list(latest_by_key.values())
open_items = [e for e in effective_entries if e.get("status") in {"required", "blocked"}]
local_shas = {}
for rel in critical:
    p = local / rel
    local_shas[rel] = sha(p) if p.exists() else None

remote_result = {"checked": False, "ok": False, "reason": "disabled"}
drift = []
if not no_remote:
    script = (
        f"cd {remote_dir} || exit 10; "
        "printf 'coord_status_begin\\n'; ./solar-harness.sh coord-status 2>&1 | tail -20; "
        "printf '\\ncoord_status_end\\n'; "
        "printf 'status_count='; ls sprints/*.status.json 2>/dev/null | wc -l; "
        "printf 'sha_begin\\n'; "
        + " ".join([f"if [ -f {rel!r} ]; then shasum -a 256 {rel!r}; else echo MISSING {rel!r}; fi;" for rel in critical])
        + "printf 'sha_end\\n'"
    )
    cp = run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", remote, script], timeout=30)
    remote_result = {
        "checked": True,
        "ok": cp.returncode == 0,
        "returncode": cp.returncode,
        "stdout_tail": cp.stdout[-4000:],
        "stderr_tail": cp.stderr[-1000:],
    }
    if cp.returncode == 0:
        remote_shas = {}
        for line in cp.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) == 2 and len(parts[0]) == 64:
                remote_shas[parts[1]] = parts[0]
            elif len(parts) == 2 and parts[0] == "MISSING":
                remote_shas[parts[1]] = None
        for rel, local_hash in local_shas.items():
            remote_hash = remote_shas.get(rel)
            if local_hash != remote_hash:
                drift.append({"file": rel, "local_sha256": local_hash, "remote_sha256": remote_hash})

severity = "ok"
if open_items:
    severity = "error" if any(e.get("status") == "blocked" for e in open_items) else "warn"
if remote_result["checked"] and not remote_result["ok"]:
    severity = "error"
if drift:
    severity = "warn" if severity == "ok" else severity

data = {
    "ok": severity != "error",
    "severity": severity,
    "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "local": {
        "path": str(local),
        "exists": local.exists(),
        "critical_sha256": local_shas,
    },
    "manifest": {
        "path": str(manifest),
        "exists": manifest.exists(),
        "entries": len(entries),
        "effective_entries": len(effective_entries),
        "open_count": len(open_items),
        "open_items": open_items[-8:],
    },
    "remote": remote_result,
    "drift": drift,
    "current_problem": "remote unreachable or blocked sync manifest exists" if severity == "error" else "open sync manifest or file drift exists" if severity == "warn" else "no blocking Mac mini sync issue detected",
    "next_step": "resolve blocked/required manifest entries before claiming parity" if open_items else "sync changed files with backup if drift is intentional" if drift else "continue routine audit",
}

if emit_json:
    print(json.dumps(data, ensure_ascii=False, indent=2))
else:
    print(f"Solar Mac mini sync auditor: {severity}")
    print(f"current_problem: {data['current_problem']}")
    print(f"next_step: {data['next_step']}")
sys.exit(0 if data["ok"] else 2)
PY
