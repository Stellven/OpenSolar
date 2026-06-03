import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "lib" / "intent_gateway.py"
CONSUMER = ROOT / "lib" / "intent_consumer.py"
sys.path.insert(0, str(ROOT / "lib"))
import intent_consumer  # noqa: E402


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


def test_consumer_injects_research_artifact_refs_into_compiled_package(tmp_path):
    env = _env(tmp_path)
    cap = subprocess.run(
        [
            sys.executable,
            str(GATEWAY),
            "capture",
            "--text",
            "通过 Browser Agent 前门研究后，收口成统一 convergence package，并继续编译 requirement package、蓝图、追踪矩阵和 rollout。",
            "--source-channel",
            "pm_dispatch",
            "--source-trust",
            "pm_dispatch",
            "--research-artifact",
            "/tmp/frontdoor-research.json",
            "--research-project-name",
            "需求研究-2026-05",
            "--research-conversation-id",
            "conv-frontdoor-002",
            "--research-source-url",
            "https://chatgpt.com/c/conv-frontdoor-002",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    intent_id = json.loads(cap.stdout)["intent_id"]
    sprint_id = "sprint-test-research-artifact"
    sprints = tmp_path / "sprints"
    sprints.mkdir(parents=True, exist_ok=True)
    intent_consumer.SPRINTS_DIR = sprints
    (sprints / f"{sprint_id}.requirement_ir.json").write_text(
        json.dumps({"schema_version": "solar.requirement_ir.v1", "source_inputs": {}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (sprints / f"{sprint_id}.product-brief.md").write_text("# Product Brief\n", encoding="utf-8")
    (sprints / f"{sprint_id}.prd.md").write_text("# PRD\n", encoding="utf-8")
    raw = json.loads((tmp_path / "intents" / intent_id / "raw_intent.json").read_text())
    ir = json.loads((tmp_path / "intents" / intent_id / "requirement_ir.json").read_text())
    research = intent_consumer.extract_research_artifact(raw, ir)
    assert research is not None
    intent_consumer.annotate_compiled_package_with_research_artifact(sprint_id, research)

    ir = json.loads((sprints / f"{sprint_id}.requirement_ir.json").read_text())
    product_brief = (sprints / f"{sprint_id}.product-brief.md").read_text()
    prd = (sprints / f"{sprint_id}.prd.md").read_text()
    assert ir["source_inputs"]["research_artifact"]["path"] == "/tmp/frontdoor-research.json"
    assert "## Research Artifact Inputs" in product_brief
    assert "conv-frontdoor-002" in product_brief
    assert "## Research Artifact Inputs" in prd


def test_consumer_includes_enhanced_requirement_design_when_present(tmp_path):
    env = _env(tmp_path)
    fake = tmp_path / "fake_requirement_writer.py"
    fake.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "request_dir=Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
        "request_dir.mkdir(parents=True, exist_ok=True)\n"
        "(request_dir/'chatgpt-mode-state.json').write_text(json.dumps({'ok': True}), encoding='utf-8')\n"
        "print('# 需求概述\\n\\n这是增强版章节化需求设计。')\n",
        encoding="utf-8",
    )
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = f"{sys.executable} {fake}"
    intent_id = _capture(env, text="研究实现 一个自动需求编译链路。", channel="pm_dispatch")
    base = tmp_path / "intents" / intent_id
    raw = json.loads((base / "raw_intent.json").read_text())
    rewritten = json.loads((base / "rewritten_intent.json").read_text())
    ir = json.loads((base / "requirement_ir.json").read_text())
    rendered = intent_consumer.build_consumer_text(raw, rewritten, ir)
    assert "## Enhanced Requirement Design" in rendered
    assert "这是增强版章节化需求设计" in rendered
