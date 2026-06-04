#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "lib"))

import chatgpt_browser_agent_task_operator as cto  # noqa: E402
from browser.profile_lease import ProfileLease  # noqa: E402


def test_build_request_reads_prompt_file(tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hello chatgpt", encoding="utf-8")
    payload = cto.build_request({"prompt_file": str(prompt_file)}, task_dir=tmp_path)
    assert payload["prompt"] == "hello chatgpt"
    assert payload["project_name"] == "杂项"
    assert payload["expected_output"] == "markdown"
    assert payload["model"] == "chatgpt-5.5"
    assert payload["reasoning_effort"] == "high"
    assert payload["model_mode"] == "thinking"
    assert payload["tool_mode"] == "none"
    assert payload["require_ui_mode"] is True


def test_run_request_writes_result(monkeypatch, tmp_path, capsys):
    class Result:
        returncode = 0

    monkeypatch.setattr(cto, "_wrapper_cmd", lambda: ["fake-wrapper"])
    seen_env = {}

    def _fake_run(*args, **kwargs):
        seen_env.update(kwargs.get("env") or {})
        kwargs["stdout"].write("final answer")
        return Result()

    monkeypatch.setattr(cto.subprocess, "run", _fake_run)
    result = cto.run_request({"prompt": "hello", "project_name": "杂项"}, task_dir=tmp_path)
    assert result["ok"] is True
    assert seen_env["CHATGPT_MODEL"] == "chatgpt-5.5"
    assert seen_env["CHATGPT_REASONING_EFFORT"] == "high"
    assert seen_env["BROWSER_AGENT_CHATGPT_MODEL_MODE"] == "thinking"
    assert seen_env["BROWSER_AGENT_CHATGPT_REQUIRE_UI_MODE"] == "true"
    assert (tmp_path / "chatgpt-browser-agent-request.json").exists()
    assert (tmp_path / "chatgpt-browser-agent-result.json").exists()
    assert (tmp_path / "chatgpt-browser-agent-stdout.txt").read_text(encoding="utf-8") == "final answer"
    assert "ChatGPT Browser Agent Result" in capsys.readouterr().out


def test_run_request_allows_collect_without_prompt_and_sets_conversation_url(monkeypatch, tmp_path):
    class Result:
        returncode = 0

    monkeypatch.setattr(cto, "_wrapper_cmd", lambda: ["fake-wrapper"])
    seen_env = {}

    def _fake_run(*args, **kwargs):
        seen_env.update(kwargs.get("env") or {})
        kwargs["stdout"].write("final answer")
        return Result()

    monkeypatch.setattr(cto.subprocess, "run", _fake_run)
    result = cto.run_request(
        {
            "action": "collect",
            "conversation_url": "https://chatgpt.com/c/demo",
            "request_dir": str(tmp_path / "request"),
            "project_name": "杂项",
        },
        task_dir=tmp_path,
    )
    assert result["ok"] is True
    assert seen_env["BROWSER_AGENT_CHATGPT_ACTION"] == "collect"
    assert seen_env["BROWSER_AGENT_CHATGPT_CONVERSATION_URL"] == "https://chatgpt.com/c/demo"


def test_main_applies_success_cooldown(monkeypatch, tmp_path):
    envelope = {"task_id": "T1", "operator_id": "mini-browser-chatgpt", "prompt": "hello"}
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setenv("SOLAR_OPERATOR_ENVELOPE_JSON", str(envelope_path))
    monkeypatch.setenv("TASK_DIR", str(tmp_path / "task"))
    monkeypatch.setenv("SOLAR_CHATGPT_SUCCESS_COOLDOWN_SECONDS", "222")
    monkeypatch.setattr(cto.ofc, "ensure_operator_available", lambda operator_id: None)
    monkeypatch.setattr(cto, "run_request", lambda request, task_dir: {"ok": True})
    calls: list[tuple[str, int]] = []
    monkeypatch.setattr(
        cto.ofc,
        "apply_success_cooldown",
        lambda operator_id, *, success_cooldown_seconds: calls.append((operator_id, success_cooldown_seconds)) or {},
    )
    assert cto.main() == 0
    assert calls == [("mini-browser-chatgpt", 222)]


def test_main_applies_failure_flow_control(monkeypatch, tmp_path):
    envelope = {"task_id": "T2", "operator_id": "mini-browser-chatgpt", "prompt": "hello"}
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setenv("SOLAR_OPERATOR_ENVELOPE_JSON", str(envelope_path))
    monkeypatch.setenv("TASK_DIR", str(tmp_path / "task"))
    monkeypatch.setattr(cto.ofc, "ensure_operator_available", lambda operator_id: None)

    def _boom(request, task_dir):
        raise RuntimeError("429 rate limit")

    monkeypatch.setattr(cto, "run_request", _boom)
    calls: list[tuple[str, int, int, bool, bool]] = []
    monkeypatch.setattr(
        cto.ofc,
        "apply_failure_flow_control",
        lambda task_dir, *, operator_id, failure_text, rate_limit_cooldown_seconds, auth_cooldown_seconds, defer_on_cooldown, defer_on_auth: calls.append(
            (operator_id, rate_limit_cooldown_seconds, auth_cooldown_seconds, defer_on_cooldown, defer_on_auth)
        ) or {"runtime_state": "cooldown"},
    )
    assert cto.main() == 1
    assert calls == [("mini-browser-chatgpt", 3600, 21600, True, True)]


def test_main_collect_bypasses_flow_control(monkeypatch, tmp_path):
    envelope = {
        "task_id": "T3",
        "operator_id": "mini-browser-chatgpt",
        "chatgpt_browser_agent_request": {
            "action": "collect",
            "conversation_url": "https://chatgpt.com/c/demo",
            "request_dir": str(tmp_path / "request"),
        },
    }
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setenv("SOLAR_OPERATOR_ENVELOPE_JSON", str(envelope_path))
    monkeypatch.setenv("TASK_DIR", str(tmp_path / "task"))
    ensure_calls: list[str] = []
    failure_calls: list[str] = []
    success_calls: list[str] = []
    monkeypatch.setattr(
        cto.ofc,
        "ensure_operator_available",
        lambda operator_id: ensure_calls.append(operator_id),
    )
    monkeypatch.setattr(
        cto.ofc,
        "apply_failure_flow_control",
        lambda *args, **kwargs: failure_calls.append("called"),
    )
    monkeypatch.setattr(
        cto.ofc,
        "apply_success_cooldown",
        lambda *args, **kwargs: success_calls.append("called"),
    )
    monkeypatch.setattr(cto, "run_request", lambda request, task_dir: {"ok": True})
    assert cto.main() == 0
    assert ensure_calls == []
    assert failure_calls == []
    assert success_calls == []


def test_main_browser_agent_session_bypasses_flow_control(monkeypatch, tmp_path):
    envelope = {
        "task_id": "T4",
        "logical_operator": "DeepResearchChatGPT",
        "chatgpt_browser_agent_request": {
            "action": "submit",
            "prompt": "hello",
        },
    }
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setenv("SOLAR_OPERATOR_ENVELOPE_JSON", str(envelope_path))
    monkeypatch.setenv("TASK_DIR", str(tmp_path / "task"))
    ensure_calls: list[str] = []
    failure_calls: list[str] = []
    success_calls: list[str] = []
    monkeypatch.setattr(cto.ofc, "ensure_operator_available", lambda operator_id: ensure_calls.append(operator_id))
    monkeypatch.setattr(cto.ofc, "apply_failure_flow_control", lambda *args, **kwargs: failure_calls.append("called"))
    monkeypatch.setattr(cto.ofc, "apply_success_cooldown", lambda *args, **kwargs: success_calls.append("called"))
    monkeypatch.setattr(cto, "run_request", lambda request, task_dir: {"ok": True})
    assert cto.main() == 0
    assert ensure_calls == []
    assert failure_calls == []
    assert success_calls == []


def test_operator_id_defaults_to_browser_agent_session_for_session_control_chatgpt():
    assert cto._operator_id({"logical_operator": "DeepResearchChatGPT"}) == "browser_agent_session"
    assert cto._operator_id({"logical_operator": "GPTRequirementWriter"}) == "browser_agent_session"
    assert cto._operator_id({}) == "mini-chatgpt-deep-research"


def test_apply_profile_policy_skips_leased_primary_profile(monkeypatch, tmp_path):
    lease_root = tmp_path / "leases"
    lease = ProfileLease(root=lease_root)
    acquired = lease.acquire(
        "chatgpt/browser-agent",
        task_id="occupied-task",
        runtime="browser_use",
        mode="exclusive",
    )
    assert acquired["acquired"] is True
    policy = tmp_path / "browser-agent-chatgpt-local.json"
    policy.write_text(
        json.dumps(
            {
                "version": 1,
                "policies": {
                    "default": {
                        "expected_account_email": "browser-agent@example.com",
                        "allowed_profiles": ["Profile 1", "Profile 2"],
                        "selection": "first",
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BROWSER_AGENT_CHATGPT_PROFILE_POLICY_DISABLED", "0")
    monkeypatch.setenv("BROWSER_AGENT_CHATGPT_PROFILE_POLICY_FILE", str(policy))
    monkeypatch.setenv("BROWSER_PROFILE_LEASE_DIR", str(lease_root))
    env: dict[str, str] = {}
    meta = cto.apply_profile_policy(env, {"purpose": "github-trend-report-demo"})
    assert env["BROWSER_AGENT_PROFILE_DIRECTORY"] == "Profile 2"
    assert env["BROWSER_AGENT_PROFILE_ID"] == "chatgpt/browser-agent-profile-2"
    assert meta["lease_blocked_profiles"] == ["Profile 1"]
    assert meta["selected_profile_directory"] == "Profile 2"
