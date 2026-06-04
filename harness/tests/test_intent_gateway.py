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


def test_browser_agent_operator_intent_mode_prefers_strategy_over_research(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "实现 Browser Agent 物理执行算子，调用 ChatGPT Deep Research 和 Gemini Deep Research，但必须接入 operator runtime/schema。",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    ir = json.loads((tmp_path / "intents" / payload["intent_id"] / "requirement_ir.json").read_text())
    assert ir["lane"] == "strategy"


def test_capture_embeds_research_artifact_into_requirement_ir(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "通过 Browser Agent 前门做需求研究并继续编译。",
            "--require-research-artifact",
            "--research-artifact",
            "/tmp/frontdoor-research.json",
            "--research-project-name",
            "需求研究-2026-05",
            "--research-conversation-id",
            "conv-frontdoor-001",
            "--research-source-url",
            "https://chatgpt.com/c/conv-frontdoor-001",
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
    ir = json.loads((base / "requirement_ir.json").read_text())
    assert raw["routing_hints"]["require_research_artifact"] is True
    assert raw["research"]["path"] == "/tmp/frontdoor-research.json"
    assert ir["source_inputs"]["research_artifact"]["conversation_id"] == "conv-frontdoor-001"


def test_capture_triggers_gpt_requirement_writer_for_complex_research_intent(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = (
        f"{sys.executable} -c \"print('# 增强需求设计\\\\n\\\\n## 功能需求\\\\n- 先做证据边界，再拆实现任务。')\""
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "先研究再实现 DeepDive 需求编译入口，避免污染普通需求管道。",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    base = tmp_path / "intents" / payload["intent_id"]
    raw = json.loads((base / "raw_intent.json").read_text())
    rewritten = json.loads((base / "rewritten_intent.json").read_text())
    ir = json.loads((base / "requirement_ir.json").read_text())
    trace = json.loads((base / "requirement_trace.json").read_text())

    assert raw["routing_hints"]["requirement_enhancement"]["enabled"] is True
    assert rewritten["rewrite_method"] == "gpt_requirement_writer"
    assert "enhanced_requirement" in ir["source_inputs"]
    assert "先做证据边界" in ir["source_inputs"]["enhanced_requirement"]["content"]
    assert (base / "gpt_requirement_writer_output.json").exists()
    assert (base / "gpt_requirement_writer_output.md").exists()
    assert any(stage["stage"] == "requirement_enhancement" and stage["status"] == "ok" for stage in trace["stages"])


def test_capture_does_not_trigger_requirement_writer_for_plain_intent(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = f"{sys.executable} -c \"raise SystemExit(99)\""
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "修复一个普通状态页按钮样式问题。",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    base = tmp_path / "intents" / payload["intent_id"]
    raw = json.loads((base / "raw_intent.json").read_text())
    ir = json.loads((base / "requirement_ir.json").read_text())

    assert raw["routing_hints"]["requirement_enhancement"]["enabled"] is False
    assert "enhanced_requirement" not in ir["source_inputs"]
    assert not (base / "gpt_requirement_writer_output.json").exists()
