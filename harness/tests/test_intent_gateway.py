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


def test_capture_research_implementation_trigger_invokes_requirement_writer(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    fake = tmp_path / "fake_requirement_writer.py"
    fake.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "raw=os.environ.get('SOLAR_RAW_REQUIREMENT','').strip()\n"
        "request_dir=Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
        "request_dir.mkdir(parents=True, exist_ok=True)\n"
        "(request_dir/'chatgpt-mode-state.json').write_text(json.dumps({'ok': True}), encoding='utf-8')\n"
        "print('# 需求概述\\n\\n基于原始需求扩写：' + raw)\n",
        encoding="utf-8",
    )
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = f"{sys.executable} {fake}"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--text",
            "研究实现 一个基于论文分析并自动落地的需求编译链路。",
            "--json",
        ],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    base = tmp_path / "intents" / payload["intent_id"]
    rewritten = json.loads((base / "rewritten_intent.json").read_text())
    ir = json.loads((base / "requirement_ir.json").read_text())
    trace = json.loads((base / "requirement_trace.json").read_text())
    assert payload["requirement_enhancement"]["ok"] is True
    assert rewritten["rewrite_method"] == "gpt_requirement_writer"
    assert rewritten["requirement_enhancement"]["trigger_phrase"] == "研究实现"
    assert ir["source_inputs"]["enhanced_requirement"]["operator"] == "GPTRequirementWriter"
    assert "基于原始需求扩写" in ir["source_inputs"]["enhanced_requirement"]["content"]
    assert ir["source_inputs"]["enhanced_requirement"]["sections"][0]["heading"] == "需求概述"
    assert ir["source_inputs"]["enhanced_requirement"]["compile_segments"][0]["heading"] == "需求概述"
    assert trace["stages"][1]["stage"] == "requirement_enhancement"
    assert (base / "gpt_requirement_writer_output.md").exists()


def test_requirement_writer_trigger_phrases_are_configurable(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    env["SOLAR_GPT_REQUIREMENT_WRITER_TRIGGER_PHRASES"] = "实验实现,研究落地"
    fake = tmp_path / "fake_requirement_writer.py"
    fake.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "request_dir=Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
        "request_dir.mkdir(parents=True, exist_ok=True)\n"
        "(request_dir/'chatgpt-mode-state.json').write_text(json.dumps({'ok': True}), encoding='utf-8')\n"
        "print('# 需求概述\\n\\n配置化触发词命中。')\n",
        encoding="utf-8",
    )
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = f"{sys.executable} {fake}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "capture", "--text", "实验实现 一个新链路。", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    payload = json.loads(proc.stdout)
    base = tmp_path / "intents" / payload["intent_id"]
    rewritten = json.loads((base / "rewritten_intent.json").read_text())
    assert rewritten["requirement_enhancement"]["trigger_phrase"] == "实验实现"
    assert "实验实现" in rewritten["requirement_enhancement"]["configured_phrases"]


def test_bind_copies_requirement_writer_artifacts_when_present(tmp_path):
    env = dict(os.environ)
    env["SOLAR_INTENT_GATEWAY_DIR"] = str(tmp_path / "intents")
    env["SOLAR_HARNESS_SPRINTS_DIR"] = str(tmp_path / "sprints")
    fake = tmp_path / "fake_requirement_writer.py"
    fake.write_text(
        "import json, os\n"
        "from pathlib import Path\n"
        "request_dir=Path(os.environ['BROWSER_AGENT_REQUEST_DIR'])\n"
        "request_dir.mkdir(parents=True, exist_ok=True)\n"
        "(request_dir/'chatgpt-mode-state.json').write_text(json.dumps({'ok': True}), encoding='utf-8')\n"
        "print('# 标题\\n\\n章节化需求设计')\n",
        encoding="utf-8",
    )
    env["SOLAR_GPT_REQUIREMENT_WRITER_CMD"] = f"{sys.executable} {fake}"
    capture = subprocess.run(
        [sys.executable, str(SCRIPT), "capture", "--text", "研究实现 一个新编译器。", "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    intent_id = json.loads(capture.stdout)["intent_id"]
    sprint_id = "sprint-20990101-000001"
    subprocess.run(
        [sys.executable, str(SCRIPT), "bind", "--intent-id", intent_id, "--sprint-id", sprint_id, "--json"],
        text=True,
        capture_output=True,
        env=env,
        check=True,
    )
    sprints = tmp_path / "sprints"
    assert (sprints / f"{sprint_id}.gpt_requirement_writer_output.json").exists()
    assert (sprints / f"{sprint_id}.gpt_requirement_writer_output.md").exists()
