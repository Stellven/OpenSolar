import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "chatgpt_requirement_writer_operator.py"
CONFIG_DIR = ROOT / "config"


def run_operator(
    tmp_path,
    *,
    stdin_text="rewrite from upstream",
    env_extra=None,
    write_mode_proof=True,
    check=True,
):
    wrapper = tmp_path / "fake_wrapper.py"
    wrapper.write_text(
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "prompt=sys.stdin.read()\n"
        f"write_mode_proof={str(write_mode_proof)!r} == 'True'\n"
        "request_dir=os.environ.get('BROWSER_AGENT_REQUEST_DIR')\n"
        "if write_mode_proof and request_dir:\n"
        "    Path(request_dir).mkdir(parents=True, exist_ok=True)\n"
        "    (Path(request_dir)/'chatgpt-mode-state.json').write_text(json.dumps({'ok': True, 'test': True}), encoding='utf-8')\n"
        "out={'model':os.environ.get('CHATGPT_MODEL'),"
        "'effort':os.environ.get('CHATGPT_REASONING_EFFORT'),"
        "'model_mode':os.environ.get('BROWSER_AGENT_CHATGPT_MODEL_MODE'),"
        "'tool_mode':os.environ.get('BROWSER_AGENT_CHATGPT_TOOL_MODE'),"
        "'require_ui_mode':os.environ.get('BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE'),"
        "'prompt':prompt[:4000]}\n"
        "print(json.dumps(out, ensure_ascii=False))\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "BROWSER_AGENT_CHATGPT_WRAPPER_CMD": f"{sys.executable} {wrapper}",
            "BROWSER_AGENT_REQUEST_DIR": str(tmp_path / "request"),
            "BROWSER_AGENT_CHATGPT_PROFILE_POLICY_DISABLED": "1",
        }
    )
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=check,
    )


def test_requirement_writer_prefers_raw_file_over_stdin(tmp_path):
    raw_file = tmp_path / "raw.txt"
    raw_file.write_text("用户原始需求：请按章节输出系统化需求设计", encoding="utf-8")
    proc = run_operator(
        tmp_path,
        stdin_text="上游改写稿：错误信息，仅用于回退",
        env_extra={"SOLAR_RAW_REQUIREMENT_FILE": str(raw_file)},
    )
    payload = json.loads(proc.stdout)
    assert "用户原始需求：请按章节输出系统化需求设计" in payload["prompt"]
    assert "上游改写稿" not in payload["prompt"]


def test_requirement_writer_config_has_logical_and_physical_and_actor_links():
    logical = json.loads((CONFIG_DIR / "logical-operators.json").read_text(encoding="utf-8"))
    physical = json.loads((CONFIG_DIR / "physical-operators.json").read_text(encoding="utf-8"))
    actors = json.loads((CONFIG_DIR / "agent-actors.json").read_text(encoding="utf-8"))
    registry = json.loads((CONFIG_DIR / "operator_registry.json").read_text(encoding="utf-8"))
    schedules = json.loads((CONFIG_DIR / "operator_schedules.json").read_text(encoding="utf-8"))

    logical_entry = logical["logical_operators"]["GPTRequirementWriter"]
    assert logical_entry["operator_type"] == "GPTRequirementWriter"
    binding = logical["bindings"]["GPTRequirementWriter"]
    assert any(
        c.get("actor_id") == "mini-chatgpt-requirement-writer"
        for c in binding.get("candidates", [])
    )

    assert "mini-chatgpt-requirement-writer" in physical["operators"]
    actor_cfg = actors["actors"]["mini-chatgpt-requirement-writer"]
    assert actor_cfg["operator_alias"] == "mini-chatgpt-requirement-writer"
    assert actor_cfg["role"] == "planner"

    line_cfg = registry["lines"]["chatgpt_requirement_writer"]
    assert line_cfg["primary"] == "tools/chatgpt_requirement_writer_operator.py"
    assert schedules["bindings"]["chatgpt_requirement_writer"]["type"] == "manual"
    assert schedules["bindings"]["chatgpt_requirement_writer"]["source_schedule"] == "on_demand"


def test_requirement_writer_uses_thinking_high(tmp_path):
    proc = run_operator(tmp_path, stdin_text="为 DeepDive 设计一个需求编译器")
    payload = json.loads(proc.stdout)
    assert payload["model_mode"] == "thinking"
    assert payload["effort"] == "high"
    assert payload["tool_mode"] == "none"
    assert payload["require_ui_mode"] == "true"
    assert "GPTRequirementWriter 固化执行协议" in payload["prompt"]
    assert "功能需求清单" in payload["prompt"]
    meta = json.loads((tmp_path / "request" / "requirement-writer-request.json").read_text())
    assert meta["operator_kind"] == "GPTRequirementWriter"
    assert meta["raw_requirement_source"] == "stdin"
    assert meta["upstream_input_ignored"] is False


def test_requirement_writer_prefers_raw_requirement_env(tmp_path):
    proc = run_operator(
        tmp_path,
        stdin_text="上游改写稿：请写一个简单摘要",
        env_extra={"SOLAR_RAW_REQUIREMENT": "用户原始需求：开发一个完整的章节化 PRD 编译前设计算子"},
    )
    payload = json.loads(proc.stdout)
    assert "用户原始需求：开发一个完整的章节化 PRD 编译前设计算子" in payload["prompt"]
    assert "上游改写稿" not in payload["prompt"]
    meta = json.loads((tmp_path / "request" / "requirement-writer-request.json").read_text())
    assert meta["raw_requirement_source"] == "env:SOLAR_RAW_REQUIREMENT"
    assert meta["upstream_input_present"] is True
    assert meta["upstream_input_ignored"] is True


def test_requirement_writer_can_read_raw_intent_file(tmp_path):
    raw_intent = tmp_path / "raw_intent.json"
    raw_intent.write_text(
        json.dumps(
            {
                "schema_version": "solar.raw_intent.v1",
                "raw": {"text": "用户原始需求：把需求写作算子做成章节化、系统化输出"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proc = run_operator(
        tmp_path,
        stdin_text="rewrite from upstream",
        env_extra={"SOLAR_RAW_INTENT_FILE": str(raw_intent)},
    )
    payload = json.loads(proc.stdout)
    assert "章节化、系统化输出" in payload["prompt"]
    meta = json.loads((tmp_path / "request" / "requirement-writer-request.json").read_text())
    assert meta["raw_requirement_source"] == "raw_intent:SOLAR_RAW_INTENT_FILE"
    assert meta["raw_requirement_source_path"] == str(raw_intent)


def test_requirement_writer_requires_mode_proof(tmp_path):
    proc = run_operator(
        tmp_path,
        stdin_text="为浏览器任务设计规格",
        write_mode_proof=False,
        check=False,
    )
    assert proc.returncode == 1
    assert "chatgpt-mode-state.json" in proc.stderr
