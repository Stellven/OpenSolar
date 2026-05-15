from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.cli import build_parser, main


def test_survey_cli_commands_registered():
    subs = build_parser()._subparsers._group_actions[0].choices
    for name in ["survey-plan", "survey-pack", "survey-write-section", "survey-run-sections", "survey-review", "survey-compile", "survey-eval"]:
        assert name in subs


def test_survey_plan_cli(tmp_path, capsys):
    assert main([
        "survey-plan",
        "--brief", "隐空间推理技术架构和演进方向",
        "--target-chars", "50000",
        "--output-dir", str(tmp_path),
        "--json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["chapter_count"] >= 8
    assert payload["section_count"] >= 30
    assert (tmp_path / "survey_report_ast.json").exists()


def test_survey_eval_cli_require_complete_fails_plan_only(tmp_path, capsys):
    assert main([
        "survey-plan",
        "--brief", "隐空间推理技术架构和演进方向",
        "--target-chars", "50000",
        "--output-dir", str(tmp_path),
        "--json",
    ]) == 0
    capsys.readouterr()
    rc = main([
        "survey-eval",
        "--output-dir", str(tmp_path),
        "--strict",
        "--require-complete",
        "--json",
    ])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any(item.startswith("finalized_sections_low:0<") for item in payload["scorecard"]["issues"])
