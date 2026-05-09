#!/usr/bin/env python3
"""Solar evolution engine: score, evaluate, promote, and demote capabilities."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
HARNESS_DIR = Path(os.environ.get("HARNESS_DIR", HOME / ".solar" / "harness"))
STATE_DB = Path(os.environ.get("HARNESS_STATE_DB", HARNESS_DIR / "run" / "state.db"))

sys.path.insert(0, str(HARNESS_DIR / "lib"))
from capability_registry import LEVEL_REVERSE, _open_db as open_capability_db  # type: ignore  # noqa: E402
from eval_runner import run_pack  # type: ignore  # noqa: E402
from failure_miner import mine as mine_failures  # type: ignore  # noqa: E402


def _now() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _conn() -> sqlite3.Connection:
    conn = open_capability_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS capability_scorecards (
        capability TEXT NOT NULL,
        provider TEXT NOT NULL,
        score REAL NOT NULL,
        level TEXT NOT NULL,
        status TEXT NOT NULL,
        eval_passed INTEGER NOT NULL DEFAULT 0,
        regression_passed INTEGER NOT NULL DEFAULT 0,
        failures INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        payload TEXT,
        PRIMARY KEY (capability, provider)
    );
    CREATE TABLE IF NOT EXISTS evolution_experiments (
        id TEXT PRIMARY KEY,
        capability TEXT NOT NULL,
        hypothesis TEXT NOT NULL,
        before_score REAL NOT NULL,
        after_score REAL NOT NULL,
        verdict TEXT NOT NULL,
        rollback TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        payload TEXT
    );
    """)
    conn.commit()
    return conn


def scorecard(write: bool = True) -> dict[str, Any]:
    conn = _conn()
    rows = conn.execute(
        "SELECT capability, provider, level, status FROM plugin_capabilities WHERE status='active'"
    ).fetchall()
    failures = mine_failures(limit=20)
    failure_count = int(failures.get("failures", 0))
    entries = []
    for row in rows:
        level_int = int(row["level"])
        level = LEVEL_REVERSE.get(level_int, "dead_end")
        penalty = min(1.0, failure_count / 200.0)
        score = max(1.0, round(float(level_int) - penalty, 2))
        status = "active" if score >= 2 else "degraded"
        item = {
            "capability": row["capability"],
            "provider": row["provider"],
            "score": score,
            "level": level,
            "status": status,
            "failures": failure_count,
        }
        entries.append(item)
        if write:
            conn.execute(
                """INSERT INTO capability_scorecards
                   (capability, provider, score, level, status, failures, updated_at, payload)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(capability, provider) DO UPDATE SET
                     score=excluded.score, level=excluded.level, status=excluded.status,
                     failures=excluded.failures, updated_at=excluded.updated_at, payload=excluded.payload""",
                (item["capability"], item["provider"], score, level, status, failure_count, _now(), json.dumps(item)),
            )
    conn.commit()
    conn.close()
    weighted = round(sum(item["score"] for item in entries) / max(len(entries), 1), 2)
    return {"ok": True, "total": len(entries), "weighted_score": weighted, "scorecards": entries}


def promote(capability: str, eval_pass: bool, regression_pass: bool) -> dict[str, Any]:
    if not eval_pass or not regression_pass:
        return {
            "ok": False,
            "promoted": False,
            "capability": capability,
            "reason": "promotion_requires_eval_pass_and_regression_pass",
        }
    conn = _conn()
    conn.execute(
        """UPDATE capability_scorecards
           SET status='promoted', eval_passed=1, regression_passed=1, updated_at=?
           WHERE capability=?""",
        (_now(), capability),
    )
    changed = conn.total_changes
    conn.commit()
    conn.close()
    return {"ok": True, "promoted": changed > 0, "capability": capability}


def demote_degraded(threshold: float = 2.0) -> dict[str, Any]:
    conn = _conn()
    rows = conn.execute(
        "SELECT capability, provider, score, level FROM capability_scorecards WHERE score < ?",
        (threshold,),
    ).fetchall()
    demoted = []
    for row in rows:
        conn.execute(
            "UPDATE capability_scorecards SET status='demoted', updated_at=? WHERE capability=? AND provider=?",
            (_now(), row["capability"], row["provider"]),
        )
        demoted.append({"capability": row["capability"], "provider": row["provider"], "score": row["score"]})
    conn.commit()
    conn.close()
    return {"ok": True, "demoted": demoted, "count": len(demoted)}


def run_loop(pack: str) -> dict[str, Any]:
    before = scorecard(write=True)
    clusters = mine_failures(limit=1)
    eval_result = run_pack(pack)
    regression_passed = bool(eval_result.get("ok"))
    eval_passed = bool(eval_result.get("ok"))
    cap = "vfs.search"
    promotion = promote(cap, eval_pass=eval_passed, regression_pass=regression_passed)
    after = scorecard(write=True)
    exp_id = f"exp-{_now().replace(':', '').replace('-', '')}-s5"
    hypothesis = "If S4 extension and Mirage regressions pass, promote vfs.search as a stable default capability."
    rollback = "solar-harness integrations disable mirage; restore previous product snapshot if regression fails."
    conn = _conn()
    conn.execute(
        """INSERT OR REPLACE INTO evolution_experiments
           (id, capability, hypothesis, before_score, after_score, verdict, rollback, updated_at, payload)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            exp_id,
            cap,
            hypothesis,
            float(before.get("weighted_score", 0)),
            float(after.get("weighted_score", 0)),
            "promoted" if promotion.get("promoted") else "evaluated",
            rollback,
            _now(),
            json.dumps({"clusters": clusters, "eval": eval_result, "promotion": promotion}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "ok": bool(eval_result.get("ok")) and bool(promotion.get("ok")),
        "experiment_id": exp_id,
        "clusters": clusters,
        "eval": eval_result,
        "promotion": promotion,
        "before": before,
        "after": after,
    }


def status() -> dict[str, Any]:
    conn = _conn()
    rows = conn.execute(
        "SELECT capability, provider, score, level, status, failures, updated_at FROM capability_scorecards ORDER BY score DESC, capability LIMIT 50"
    ).fetchall()
    experiments = conn.execute(
        "SELECT id, capability, verdict, updated_at FROM evolution_experiments ORDER BY updated_at DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {
        "ok": True,
        "scorecards": [dict(r) for r in rows],
        "experiments": [dict(r) for r in experiments],
        "total_scorecards": len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser(prog="evolution_engine.py")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("scorecard").add_argument("--json", action="store_true")
    p = sub.add_parser("run-loop")
    p.add_argument("--pack", default=str(HARNESS_DIR / "evals" / "packs" / "s5-basic" / "eval.json"))
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("promote")
    p.add_argument("--capability", required=True)
    p.add_argument("--eval-pass", action="store_true")
    p.add_argument("--regression-pass", action="store_true")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("demote-degraded")
    p.add_argument("--threshold", type=float, default=2.0)
    p.add_argument("--json", action="store_true")
    sub.add_parser("status").add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "scorecard":
        data = scorecard(write=True)
    elif args.cmd == "run-loop":
        data = run_loop(args.pack)
    elif args.cmd == "promote":
        data = promote(args.capability, args.eval_pass, args.regression_pass)
    elif args.cmd == "demote-degraded":
        data = demote_degraded(args.threshold)
    elif args.cmd == "status":
        data = status()
    else:
        ap.print_help()
        return 1
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))
    return 0 if data.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
