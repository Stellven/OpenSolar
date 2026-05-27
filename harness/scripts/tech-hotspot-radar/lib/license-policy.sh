#!/usr/bin/env bash
# scripts/tech-hotspot-radar/lib/license-policy.sh - Normalize SPDX ids and classify policy tier
set -euo pipefail

python3 - <<'PY' "${1:-}"
import json, sys

raw = (sys.argv[1] or "").strip()
normalized = raw.upper().replace(" ", "")
if not normalized:
    normalized = "UNKNOWN"

allowed = {"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC", "UNLICENSE", "CC0-1.0"}
restricted = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "EPL-2.0", "SSPL-1.0"}
forbidden = {"PROPRIETARY", "ALL-RIGHTS-RESERVED", "CUSTOM-NONCOMMERCIAL"}

if normalized in allowed:
    classification = "allowed"
elif normalized in restricted:
    classification = "restricted"
elif normalized in forbidden:
    classification = "forbidden"
elif normalized in {"NOASSERTION", "UNKNOWN", "NONE"}:
    classification = "restricted"
else:
    classification = "restricted"

payload = {
    "license_id": normalized,
    "classification": classification,
    "copy_left_flag": normalized.startswith(("GPL", "AGPL", "LGPL")),
    "auto_block_default": normalized in forbidden,
}
print(json.dumps(payload, ensure_ascii=False))
PY
