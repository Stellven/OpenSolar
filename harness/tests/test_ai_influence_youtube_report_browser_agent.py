import json
import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from ai_influence_youtube_report.browser_agent import (  # noqa: E402
    BrowserAgentClient,
    ChatGPTReportOperatorProvider,
    LocalModelSubstitutionError,
)


class FakeProvider:
    def call(self, stage, payload, *, requested_model, run_id="", chapter_id="", sprint_id=""):
        return {
            "schema_version": f"{stage}.fake",
            "model_call_id": f"{stage}-1",
            "browser_session_id": "session-1",
            "chatgpt_url": "https://chatgpt.com/c/fake",
            "resolved_model": requested_model,
        }


def test_browser_agent_client_writes_ledger_for_each_phase(tmp_path: Path) -> None:
    ledger = tmp_path / "model_call_ledger.jsonl"
    client = BrowserAgentClient(FakeProvider(), ledger_path=ledger, sprint_id="sprint-1")

    client.plan({}, requested_model="chatgpt-5.5-thinking-high", run_id="run-1")
    client.write_chapter({}, requested_model="chatgpt-5.5-thinking-high", run_id="run-1", chapter_id="c1")
    client.synthesize([], requested_model="chatgpt-5.5-thinking-high", run_id="run-1")

    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert [row["stage"] for row in rows] == ["phase1", "phase2", "phase3"]


def test_browser_agent_client_rejects_local_model_substitution(tmp_path: Path) -> None:
    client = BrowserAgentClient(FakeProvider(), ledger_path=tmp_path / "ledger.jsonl", sprint_id="sprint-1")

    with pytest.raises(LocalModelSubstitutionError):
        client.plan({}, requested_model="ThunderOMLX", run_id="run-1")


def test_phase2_duplicate_chapter_call_is_rejected(tmp_path: Path) -> None:
    client = BrowserAgentClient(FakeProvider(), ledger_path=tmp_path / "ledger.jsonl", sprint_id="sprint-1")
    client.write_chapter({}, requested_model="chatgpt-5.5-thinking-high", run_id="run-1", chapter_id="c1")

    with pytest.raises(ValueError, match="duplicate"):
        client.write_chapter({}, requested_model="chatgpt-5.5-thinking-high", run_id="run-1", chapter_id="c1")


def test_chatgpt_report_operator_provider_invokes_production_seam(tmp_path: Path) -> None:
    operator_script = tmp_path / "fake_chatgpt_report_operator.py"
    operator_script.write_text(
        """
import json
import os
import sys
from pathlib import Path

request_dir = Path(os.environ["BROWSER_AGENT_REQUEST_DIR"])
request_dir.mkdir(parents=True, exist_ok=True)
prompt = sys.stdin.read()
(request_dir / "captured-prompt.txt").write_text(prompt, encoding="utf-8")
(request_dir / "captured-env.json").write_text(json.dumps({
    "purpose": os.environ.get("BROWSER_AGENT_PURPOSE"),
    "kind": os.environ.get("CHATGPT_REPORT_OPERATOR_KIND"),
    "expected_output": os.environ.get("BROWSER_AGENT_EXPECTED_OUTPUT"),
    "project_name": os.environ.get("BROWSER_AGENT_CHATGPT_PROJECT_NAME"),
    "model": os.environ.get("CHATGPT_MODEL"),
    "lineage": os.environ.get("BROWSER_AGENT_SESSION_LINEAGE"),
    "account_email": os.environ.get("BROWSER_AGENT_CHATGPT_ACCOUNT_EMAIL"),
    "profile_directory": os.environ.get("BROWSER_AGENT_PROFILE_DIRECTORY"),
}, ensure_ascii=False, indent=2), encoding="utf-8")
(request_dir / "submitted-run.json").write_text(json.dumps({
    "task_id": "task-123",
    "conversation_id": "conv-456",
    "url": "https://chatgpt.com/c/conv-456",
}, ensure_ascii=False, indent=2), encoding="utf-8")
(request_dir / "page.json").write_text(json.dumps({
    "conversation_id": "conv-456",
    "url": "https://chatgpt.com/c/conv-456",
}, ensure_ascii=False, indent=2), encoding="utf-8")
(request_dir / "assistant-response.txt").write_text("phase output\\n", encoding="utf-8")
print("phase output")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    provider = ChatGPTReportOperatorProvider(
        operator_script=operator_script,
        python_executable=sys.executable,
        request_root=tmp_path / "provider-runs",
        target_account_email="browser-agent@example.com",
        profile_directory="Profile 7",
    )

    result = provider.call(
        "phase1",
        {"transcripts": [{"video_id": "abc123"}]},
        requested_model="chatgpt-5.5-thinking-high",
        run_id="run-77",
        sprint_id="sprint-demo",
    )

    assert result["model_call_id"] == "task-123"
    assert result["browser_session_id"] == "conv-456"
    assert result["chatgpt_url"] == "https://chatgpt.com/c/conv-456"
    assert result["resolved_model"] == "chatgpt-5.5-thinking-high"
    assert result["text"] == "phase output"

    request_dir = Path(result["request_dir"])
    env_payload = json.loads((request_dir / "captured-env.json").read_text(encoding="utf-8"))
    prompt_text = (request_dir / "captured-prompt.txt").read_text(encoding="utf-8")
    assert env_payload["kind"] == "planner"
    assert env_payload["expected_output"] == "json"
    assert env_payload["purpose"] == "ai-influence-youtube-report:phase1-plan"
    assert env_payload["project_name"] == "杂项"
    assert env_payload["model"] == "chatgpt-5.5-thinking-high"
    assert env_payload["lineage"].startswith("ai-influence-youtube-report:phase1:run-77")
    assert env_payload["account_email"] == "browser-agent@example.com"
    assert env_payload["profile_directory"] == "Profile 7"
    assert "Return JSON only: trends -> chapters -> subsections -> evidence_refs." in prompt_text
    assert '"video_id": "abc123"' in prompt_text
