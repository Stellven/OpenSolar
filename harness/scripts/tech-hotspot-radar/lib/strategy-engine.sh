#!/usr/bin/env bash
# scripts/tech-hotspot-radar/lib/strategy-engine.sh - Machine-readable strategy decisions and task candidates
set -euo pipefail

DB_PATH=""
REPO=""
DRY_RUN="false"
FORCE_DECISION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --db) DB_PATH="$2"; shift 2 ;;
        --repo) REPO="$2"; shift 2 ;;
        --dry-run) DRY_RUN="true"; shift ;;
        --force-decision) FORCE_DECISION="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$DB_PATH" || -z "$REPO" ]]; then
    echo "Usage: strategy-engine.sh --db <path> --repo <owner/name> [--dry-run] [--force-decision <type>]" >&2
    exit 1
fi

GATE_JSON="$(bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hard-gates.sh" --db "$DB_PATH" --repo "$REPO")"

python3 - <<'PY' "$DB_PATH" "$REPO" "$DRY_RUN" "$FORCE_DECISION" "$GATE_JSON"
import datetime as dt
import hashlib
import json
import sqlite3
import sys

db_path, repo, dry_run, force_decision, gate_json = sys.argv[1], sys.argv[2], sys.argv[3].lower() == "true", sys.argv[4], json.loads(sys.argv[5])
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS repo_strategy_decisions (
        decision_id TEXT PRIMARY KEY,
        repo_full_name TEXT NOT NULL,
        decision TEXT NOT NULL,
        confidence REAL NOT NULL,
        recommended_action TEXT NOT NULL,
        technical_entry_point TEXT NOT NULL,
        risks_json TEXT NOT NULL DEFAULT '[]',
        task_candidates_json TEXT NOT NULL DEFAULT '[]',
        evidence_map_json TEXT NOT NULL DEFAULT '{}',
        gate_status_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS task_candidates (
        candidate_id TEXT PRIMARY KEY,
        repo_full_name TEXT NOT NULL,
        decision TEXT NOT NULL,
        title TEXT NOT NULL,
        recommended_action TEXT NOT NULL,
        technical_entry_point TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 50,
        evidence_map_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'proposed',
        created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}'
    )
    """
)

card = conn.execute(
    "SELECT tier, risk_classification, scores_json, evidence_ids_json, positioning, core_technical_idea FROM repo_analysis_cards WHERE repo_full_name=? ORDER BY updated_at DESC LIMIT 1",
    (repo,),
).fetchone()
packet = conn.execute(
    "SELECT scores_json, detector_results_json FROM project_reasoning_packets WHERE repo_full_name=? ORDER BY created_at DESC LIMIT 1",
    (repo,),
).fetchone()
if not card and not packet:
    print(json.dumps({"ok": False, "repo": repo, "error": "missing repo_analysis_cards/project_reasoning_packets"}, ensure_ascii=False))
    sys.exit(1)

scores = {}
detectors = []
evidence_ids = []
positioning = ""
tech_entry = "investigate repo analysis card"
risk_classification = "none"
tier = "B"
if card:
    scores.update(json.loads(card["scores_json"] or "{}"))
    evidence_ids = json.loads(card["evidence_ids_json"] or "[]")
    positioning = card["positioning"] or ""
    tech_entry = card["core_technical_idea"] or tech_entry
    risk_classification = card["risk_classification"] or "none"
    tier = card["tier"] or "B"
if packet:
    scores.update(json.loads(packet["scores_json"] or "{}"))
    detectors = json.loads(packet["detector_results_json"] or "[]")

detector_map = {d.get("name"): bool(d.get("matched")) for d in detectors if isinstance(d, dict)}
decision_types = [
    "monitor_only",
    "research_deep_dive",
    "build_internal_prototype",
    "contribute_upstream",
    "integrate_now",
    "partner_outreach",
    "recruit_talent",
    "legal_review",
    "security_watch",
]
if force_decision:
    decision = force_decision
else:
    if gate_json.get("security_flag"):
        decision = "security_watch"
    elif gate_json.get("license_gate", {}).get("classification") == "forbidden" or gate_json.get("ip_flag"):
        decision = "legal_review"
    elif detector_map.get("foundation_infra_candidate") and tier in {"S", "A"}:
        decision = "build_internal_prototype"
    elif detector_map.get("sudden_hot") and float(scores.get("heat_score") or 0) >= 0.7:
        decision = "integrate_now"
    elif detector_map.get("early_potential"):
        decision = "research_deep_dive"
    elif detector_map.get("steady_compounder"):
        decision = "contribute_upstream"
    elif tier == "S":
        decision = "partner_outreach"
    elif tier == "A":
        decision = "recruit_talent"
    else:
        decision = "monitor_only"
if decision not in decision_types:
    print(json.dumps({"ok": False, "repo": repo, "error": f"unknown decision type: {decision}"}, ensure_ascii=False))
    sys.exit(1)

confidence = round(max(0.51, min(0.98, 0.55 + float(scores.get("potential_score") or 0) * 0.35 + (0.05 if detector_map.get("sudden_hot") else 0))), 3)
risks = list(gate_json.get("notes") or [])
if risk_classification not in {"none", ""}:
    risks.append(f"risk_classification={risk_classification}")
if gate_json.get("license_gate", {}).get("classification") == "restricted":
    risks.append("restricted license requires human review")
if not risks:
    risks.append("no immediate blocking risk detected; keep human review in loop")
evidence_map = {
    "repo": repo,
    "evidence_ids": evidence_ids,
    "detectors": [d for d in detectors if isinstance(d, dict) and d.get("matched")],
    "gate_status": gate_json,
}
recommended_action = {
    "monitor_only": "Keep the repo on the watchlist and refresh metrics daily.",
    "research_deep_dive": "Create a focused internal research brief with explicit evidence-backed questions.",
    "build_internal_prototype": "Prototype the core technical pattern inside Solar-facing workflows.",
    "contribute_upstream": "Prepare a small upstream contribution or doc improvement.",
    "integrate_now": "Test direct integration into one real internal workflow this week.",
    "partner_outreach": "Open a maintainer conversation and evaluate collaboration leverage.",
    "recruit_talent": "Track maintainers and prolific contributors as talent signals.",
    "legal_review": "Escalate to legal/IP review before any productization step.",
    "security_watch": "Route through security review and keep out of default automation paths.",
}[decision]
technical_entry_point = tech_entry or positioning or "review repo analysis card and evidence atoms"
candidate_id = "task_" + hashlib.sha256(f"{repo}\0{decision}".encode()).hexdigest()[:16]
task_candidates = [
    {
        "candidate_id": candidate_id,
        "title": f"{repo} / {decision}",
        "priority": 90 if decision in {"integrate_now", "build_internal_prototype"} else 70 if decision in {"research_deep_dive", "contribute_upstream"} else 50,
        "recommended_action": recommended_action,
        "technical_entry_point": technical_entry_point,
    }
]
payload = {
    "decision": decision,
    "confidence": confidence,
    "recommended_action": recommended_action,
    "technical_entry_point": technical_entry_point,
    "risks": risks,
    "task_candidates": task_candidates,
    "evidence_map": evidence_map,
}
required = ["decision", "confidence", "recommended_action", "technical_entry_point", "risks", "task_candidates", "evidence_map"]
missing = [field for field in required if not payload.get(field)]
if missing:
    print(json.dumps({"ok": False, "repo": repo, "error": f"missing required fields: {missing}"}, ensure_ascii=False))
    sys.exit(1)

now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
if not dry_run:
    decision_id = "dec_" + hashlib.sha256(f"{repo}\0{decision}\0{now[:10]}".encode()).hexdigest()[:18]
    conn.execute(
        """
        INSERT INTO repo_strategy_decisions
        (decision_id, repo_full_name, decision, confidence, recommended_action, technical_entry_point,
         risks_json, task_candidates_json, evidence_map_json, gate_status_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(decision_id) DO NOTHING
        """,
        (decision_id, repo, decision, confidence, recommended_action, technical_entry_point,
         json.dumps(risks, ensure_ascii=False), json.dumps(task_candidates, ensure_ascii=False),
         json.dumps(evidence_map, ensure_ascii=False), json.dumps(gate_json, ensure_ascii=False), now, now),
    )
    for task in task_candidates:
        conn.execute(
            """
            INSERT OR REPLACE INTO task_candidates
            (candidate_id, repo_full_name, decision, title, recommended_action, technical_entry_point,
             priority, evidence_map_json, status, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?)
            """,
            (task["candidate_id"], repo, decision, task["title"], task["recommended_action"], task["technical_entry_point"],
             int(task["priority"]), json.dumps(evidence_map, ensure_ascii=False), now, json.dumps(task, ensure_ascii=False)),
        )
    conn.commit()

print(json.dumps(payload, ensure_ascii=False))
conn.close()
PY
