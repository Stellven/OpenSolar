from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.chief_editor import run_chief_editor


def _write_human_final(root):
    (root / "human_final.md").write_text(
        """# Professor-Grade Survey: Test

## 核心结论

Agentic Runtime is an execution system.

## 证据基础

Sources cover papers and official docs.

## 架构范式

### 本章判断

- Runtime requires durable execution and state.

### 风险与争议

- Official docs are not independent proof.

## 评估体系

### 本章判断

- Benchmarks must test end-to-end execution.

### 未解问题

- Cross-runtime comparability remains open.

## 证据脚注

[^1]: Test source (paper) https://arxiv.org/abs/2501.00001
""",
        encoding="utf-8",
    )


def test_chief_editor_deterministic_writes_quality_payload(tmp_path):
    _write_human_final(tmp_path)
    payload = run_chief_editor(tmp_path, backend="deterministic", min_chars=100)

    assert payload["ok"] is True
    assert (tmp_path / "chief_editor_final.md").exists()
    assert (tmp_path / "survey_chief_editor_backend.json").exists()
    assert payload["quality_gate"]["ok"] is True
    text = (tmp_path / "chief_editor_final.md").read_text(encoding="utf-8")
    assert "## 架构范式" in text
    assert "## 评估体系" in text
    assert "[claim:" not in text


def test_chief_editor_can_require_hitl_approval(tmp_path):
    _write_human_final(tmp_path)
    payload = run_chief_editor(tmp_path, backend="deterministic", min_chars=100, require_hitl=True)

    assert payload["ok"] is False
    assert payload["reason"] == "hitl_approval_required"
    assert (tmp_path / "survey_chief_editor_hitl.md").exists()

    (tmp_path / "chief_editor_approval.txt").write_text("APPROVED", encoding="utf-8")
    approved = run_chief_editor(tmp_path, backend="deterministic", min_chars=100, require_hitl=True)
    assert approved["ok"] is True
    saved = json.loads((tmp_path / "survey_chief_editor_backend.json").read_text(encoding="utf-8"))
    assert saved["hitl_approved"] is True
