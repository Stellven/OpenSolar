#!/usr/bin/env bash
# Regression: compiled KB layers outrank raw evidence in default context routers.
set -euo pipefail

HARNESS="${HARNESS_DIR:-$HOME/.solar/harness}"

python3 - <<'PY'
import importlib.util
import sys
from pathlib import Path

harness = Path.home() / ".solar" / "harness"
sys.path.insert(0, str(harness / "lib"))

def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

unified = load("solar_unified_context", harness / "lib" / "solar-unified-context.py")
kb = load("solar_knowledge_context", harness / "lib" / "solar-knowledge-context.py")
mirage = load("mirage_search", harness / "lib" / "mirage_search.py")

unified_hits = [
    {"source": "qmd", "path": "qmd://solar-wiki/raw/a.md", "title": "raw", "score": 999},
    {"source": "solar_db", "path": "obsidian:/Users/sihaoli/Knowledge/references/a.md", "title": "ref", "score": 0.1},
    {"source": "qmd", "path": "qmd://solar-wiki/concepts/a.md", "title": "concept", "score": 0.2},
    {"source": "qmd", "path": "qmd://solar-wiki/synthesis/a.md", "title": "synthesis", "score": 0.3},
]
ordered = unified._sort_context_hits(unified_hits)
assert [h["layer"] for h in ordered] == ["synthesis", "concepts", "references", "raw-evidence"], ordered

kb_hits = [
    {"path": "qmd://solar-wiki/raw/a.md", "id": "raw", "title": "raw", "snippet": "", "score": 999},
    {"path": "/Users/sihaoli/Knowledge/references/a.md", "id": "ref", "title": "ref", "snippet": "", "score": 0.1},
    {"path": "/Users/sihaoli/Knowledge/concepts/a.md", "id": "concept", "title": "concept", "snippet": "", "score": 0.2},
    {"path": "/Users/sihaoli/Knowledge/synthesis/a.md", "id": "synthesis", "title": "synthesis", "snippet": "", "score": 0.3},
]
ordered = kb._rank_hits(kb_hits, "a")
assert [h["layer"] for h in ordered] == ["synthesis", "concepts", "references", "raw-evidence"], ordered

mirage_hits = [
    {"source_type": "qmd", "path": "qmd://solar-wiki/raw/a.md", "score_or_rank": 999},
    {"source_type": "solar_db", "path": "/Users/sihaoli/Knowledge/references/a.md", "score_or_rank": 0.1},
]
assert mirage._layer_priority(mirage_hits[1]) < mirage._layer_priority(mirage_hits[0])

print("PASS context router layer ranking")
PY

live_json="$("$HARNESS/solar-harness.sh" context inject \
  --query "Solar-Harness Skills Readiness Certify" \
  --json --max-hits 8 --max-chars 5000)"

LIVE_JSON="$live_json" python3 - <<'PY'
import json, os
d = json.loads(os.environ["LIVE_JSON"])
hits = d.get("hits") or []
layers = [h.get("layer") for h in hits]
assert "references" in layers, layers
assert "raw-evidence" in layers, layers
assert layers.index("references") < layers.index("raw-evidence"), layers
print("PASS live context references before raw")
PY
