import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "lib" / "intent_gateway.py"
CONSUMER = ROOT / "lib" / "intent_consumer.py"


def _env(tmp_path):
    env = dict(os.environ)
    env["SOLAR_HARNESS_DIR"] = str(ROOT)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    env["SOLAR_INTENT_CONSUMER_WORKSPACE_ROOT"] = str(tmp_path / "workspace")
    return env


def _capture(env, text="新增 intent consumer，把 RawIntent 自动编译成 PM/Planner sprint package。", channel="test"):
    cap = subprocess.run(
        [
            sys.executable,
            str(GATEWAY),
            "capture",
            "--text",
            text,
            "--source-channel",
            channel,
            "--source-trust",
            channel,
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    return json.loads(cap.stdout)["intent_id"]


def test_consumer_compiles_rawintent_to_sprint_package(tmp_path):
    env = _env(tmp_path)
    intent_id = _capture(env)

    proc = subprocess.run(
        [sys.executable, str(CONSUMER), "consume", "--intent-id", intent_id, "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    result = payload["results"][0]
    sprint_id = result["sprint_id"]

    assert result["status"] == "consumed"
    assert result["direct_pane_dispatch"] is False
    assert result["planner_runtime_submit"] is False
    assert result["planner_handoff"]["requested"] is False
    assert result["planner_handoff"]["reason"] == "untrusted_channel"
    assert (tmp_path / "intents" / intent_id / "consumer.json").exists()
    assert (tmp_path / "intents" / intent_id / "binding.json").exists()
    assert (tmp_path / "sprints" / f"{sprint_id}.status.json").exists()
    assert (tmp_path / "sprints" / f"{sprint_id}.product-brief.md").exists()
    assert (tmp_path / "sprints" / f"{sprint_id}.prd.md").exists()
    assert (tmp_path / "sprints" / f"{sprint_id}.contract.md").exists()
    assert (tmp_path / "sprints" / f"{sprint_id}.task_graph.json").exists()
    ir = json.loads((tmp_path / "sprints" / f"{sprint_id}.requirement_ir.json").read_text())
    assert ir["intent_id"] == intent_id
    assert ir["sprint_id"] == sprint_id


def test_consumer_dry_run_marks_trusted_pm_dispatch_for_planner_handoff(tmp_path):
    env = _env(tmp_path)
    intent_id = _capture(env, text="可信 PM 入口应该自动进入 Planner handoff。", channel="pm_dispatch")

    proc = subprocess.run(
        [sys.executable, str(CONSUMER), "consume", "--intent-id", intent_id, "--dry-run", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    result = json.loads(proc.stdout)["results"][0]
    handoff = result["planner_handoff"]
    assert handoff["requested"] is True
    assert handoff["reason"] == "trusted_channel"
    assert handoff["source_channel"] == "pm_dispatch"


def test_consumer_no_auto_dispatch_planner_disables_trusted_handoff(tmp_path):
    env = _env(tmp_path)
    intent_id = _capture(env, text="显式关闭 auto handoff 时只编译。", channel="pm_dispatch")

    proc = subprocess.run(
        [sys.executable, str(CONSUMER), "consume", "--intent-id", intent_id, "--dry-run", "--no-auto-dispatch-planner", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    handoff = json.loads(proc.stdout)["results"][0]["planner_handoff"]
    assert handoff["requested"] is False
    assert handoff["reason"] == "auto_dispatch_disabled"


def test_consumer_status_lists_pending(tmp_path):
    env = _env(tmp_path)
    subprocess.run(
        [sys.executable, str(GATEWAY), "capture", "--text", "pending intent", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    proc = subprocess.run(
        [sys.executable, str(CONSUMER), "status", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["pending_count"] == 1


def test_consumer_blocks_when_research_artifact_is_required_but_missing(tmp_path):
    env = _env(tmp_path)
    cap = subprocess.run(
        [
            sys.executable,
            str(GATEWAY),
            "capture",
            "--text",
            "前门研究必须存在，否则不得 compile-ready。",
            "--require-research-artifact",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    intent_id = json.loads(cap.stdout)["intent_id"]
    proc = subprocess.run(
        [sys.executable, str(CONSUMER), "consume", "--intent-id", intent_id, "--json"],
        text=True,
        capture_output=True,
        env=env,
    )
    assert proc.returncode == 1
    result = json.loads(proc.stdout)["results"][0]
    assert result["ok"] is False
    assert result["status"] == "blocked_missing_research_artifact"


def test_consumer_includes_enhanced_requirement_context(tmp_path):
    from importlib.machinery import SourceFileLoader

    consumer = SourceFileLoader("intent_consumer_under_test", str(CONSUMER)).load_module()
    raw = {
        "intent_id": "intent-test",
        "source": {"channel": "test"},
        "raw": {"text": "先研究再实现一个功能。"},
    }
    rewritten = {
        "title": "DeepDive entry",
        "objective": "Build isolated entry",
        "constraints": [],
        "acceptance": [],
    }
    ir = {
        "intent_id": "intent-test",
        "source_inputs": {
            "enhanced_requirement": {
                "content": "## 功能需求\n- DeepDive 先扩展 brief，再进入 evidence/chapter/chief-editor。"
            }
        },
    }
    text = consumer.build_consumer_text(raw, rewritten, ir)
    assert "## Enhanced Requirement Design" in text
    assert "先扩展 brief" in text


def test_consumer_injects_research_artifact_refs_into_compiled_package(tmp_path):
    from importlib.machinery import SourceFileLoader

    consumer = SourceFileLoader("intent_consumer_annotate_under_test", str(CONSUMER)).load_module()
    consumer.SPRINTS_DIR = tmp_path / "sprints"
    consumer.SPRINTS_DIR.mkdir()
    sprint_id = "sprint-test-research-artifact"
    (consumer.SPRINTS_DIR / f"{sprint_id}.requirement_ir.json").write_text(
        json.dumps({"source_inputs": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (consumer.SPRINTS_DIR / f"{sprint_id}.product-brief.md").write_text("# Product\n", encoding="utf-8")
    (consumer.SPRINTS_DIR / f"{sprint_id}.prd.md").write_text("# PRD\n", encoding="utf-8")

    consumer.annotate_compiled_package_with_research_artifact(
        sprint_id,
        {
            "path": "/tmp/frontdoor-research.json",
            "project_name": "需求研究-2026-05",
            "conversation_id": "conv-frontdoor-002",
            "source_url": "https://chatgpt.com/c/conv-frontdoor-002",
        },
    )

    ir = json.loads((consumer.SPRINTS_DIR / f"{sprint_id}.requirement_ir.json").read_text())
    product_brief = (consumer.SPRINTS_DIR / f"{sprint_id}.product-brief.md").read_text()
    prd = (consumer.SPRINTS_DIR / f"{sprint_id}.prd.md").read_text()
    assert ir["source_inputs"]["research_artifact"]["path"] == "/tmp/frontdoor-research.json"
    assert "## Research Artifact Inputs" in product_brief
    assert "conv-frontdoor-002" in product_brief
    assert "## Research Artifact Inputs" in prd
