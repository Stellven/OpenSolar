#!/usr/bin/env bash
# scripts/tech-hotspot-radar/lib/hard-gates.sh - License/IP/security gates before strategy decision
set -euo pipefail

DB_PATH=""
REPO=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db) DB_PATH="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$DB_PATH" || -z "$REPO" ]]; then
    echo "Usage: hard-gates.sh --db <path> --repo <owner/name>" >&2
    exit 1
fi

LICENSE_JSON="$(bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/license-policy.sh" "$(python3 - <<'PY' "$DB_PATH" "$REPO"
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
row = conn.execute("SELECT license FROM github_repos WHERE full_name=?", (sys.argv[2],)).fetchone()
print((row[0] if row else "") or "")
conn.close()
PY
)")"

python3 - <<'PY' "$DB_PATH" "$REPO" "$LICENSE_JSON"
import json, sqlite3, sys

db_path, repo, license_json = sys.argv[1], sys.argv[2], sys.argv[3]
license_gate = json.loads(license_json)
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT description, readme_text, archived, license FROM github_repos WHERE full_name=?",
    (repo,),
).fetchone()
if not row:
    print(json.dumps({"ok": False, "repo": repo, "error": "repo not found"}, ensure_ascii=False))
    sys.exit(1)
text = " ".join([(row["description"] or ""), (row["readme_text"] or "")]).lower()
security_terms = ("vulnerability", "exploit", "malware", "ransomware", "cve-", "red team")
ip_terms = ("all rights reserved", "proprietary", "commercial license", "source available only")
security_flag = any(term in text for term in security_terms)
ip_flag = any(term in text for term in ip_terms)
archived_flag = bool(int(row["archived"] or 0))
blocked = bool(license_gate.get("auto_block_default")) or security_flag
if license_gate.get("copy_left_flag") and (sys.argv[0:1] or True):
    blocked = blocked or False

payload = {
    "ok": True,
    "repo": repo,
    "license_gate": license_gate,
    "ip_flag": ip_flag,
    "security_flag": security_flag,
    "archived_flag": archived_flag,
    "blocked": blocked,
    "notes": [
        note for note, enabled in [
            ("copy-left flagged but configurable", bool(license_gate.get("copy_left_flag"))),
            ("IP-sensitive wording detected", ip_flag),
            ("security-sensitive wording detected", security_flag),
            ("archived repository", archived_flag),
        ] if enabled
    ],
}
print(json.dumps(payload, ensure_ascii=False))
conn.close()
PY
