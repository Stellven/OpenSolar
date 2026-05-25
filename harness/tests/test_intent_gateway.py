import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "lib" / "intent_gateway.py"


def test_capture_writes_raw_rewritten_ir_and_trace(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "修复 Solar-Harness intake 入口，让所有用户原始需求先进入 RawIntent Gateway。",
            "--source-channel",
            "codex_macbook",
            "--repo",
            "/tmp/Solar",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    intent_id = payload["intent_id"]
    base = tmp_path / "intents" / intent_id

    raw = json.loads((base / "raw_intent.json").read_text())
    rewritten = json.loads((base / "rewritten_intent.json").read_text())
    ir = json.loads((base / "requirement_ir.json").read_text())
    trace = json.loads((base / "requirement_trace.json").read_text())

    assert raw["schema_version"] == "solar.raw_intent.v1"
    assert raw["source"]["channel"] == "codex_macbook"
    assert rewritten["schema_version"] == "solar.rewritten_intent.v1"
    assert ir["schema_version"] == "solar.requirement_ir.v1"
    assert ir["compiler_next"] == "pm_planner_task_graph"
    assert trace["stages"][-1]["stage"] == "requirement_ir_compile"


def test_bind_copies_intent_artifacts_to_sprint(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    capture = subprocess.run(
        [sys.executable, str(SCRIPT), "capture", "--text", "新增统一入口。", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    intent_id = json.loads(capture.stdout)["intent_id"]
    sprint_id = "sprint-20990101-000000"
    subprocess.run(
        [sys.executable, str(SCRIPT), "bind", "--intent-id", intent_id, "--sprint-id", sprint_id, "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )

    sprints = tmp_path / "sprints"
    assert (sprints / f"{sprint_id}.raw_intent.json").exists()
    ir = json.loads((sprints / f"{sprint_id}.requirement_ir.json").read_text())
    assert ir["intent_id"] == intent_id
    assert ir["sprint_id"] == sprint_id
