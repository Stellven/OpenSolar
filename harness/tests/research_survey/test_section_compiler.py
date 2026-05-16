from __future__ import annotations

import json
import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.evidence_pack import build_evidence_packs
from research.survey.planner import create_survey_plan, write_survey_plan
from research.survey.section_compiler import compile_section, compile_survey
from research.survey.writing_loop import run_ready_sections, run_section_revision_loop, watch_pane_responses


def _append_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _strong_fixture(root):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, root)
    sources = [{"id": f"src_{i}", "source_type": t, "title": t} for i, t in enumerate(["paper", "official_doc", "code", "benchmark"])]
    evidence = [{"id": f"ev_{i}", "source_id": sources[i % len(sources)]["id"], "content": "latent reasoning architecture evaluation deployment"} for i in range(16)]
    claims = [{"id": f"cl_{i}", "claim_text": "latent reasoning architecture requires evaluation evidence"} for i in range(12)]
    links = [{"claim_id": f"cl_{i % 12}", "evidence_id": f"ev_{i}"} for i in range(16)]
    _append_jsonl(root / "sources.jsonl", sources)
    _append_jsonl(root / "evidence.jsonl", evidence)
    _append_jsonl(root / "claims.jsonl", claims)
    _append_jsonl(root / "claim_evidence.jsonl", links)
    build_evidence_packs(root, plan["report_ast"])
    return plan


def test_compile_section_refuses_blocked_pack(tmp_path):
    plan = create_survey_plan("latent reasoning", target_chars=50000)
    write_survey_plan(plan, tmp_path)
    build_evidence_packs(tmp_path, plan["report_ast"])
    result = compile_section(tmp_path, "ch01/sec01")
    assert result["ok"] is False
    assert result["reason"] == "evidence_pack_blocked"


def test_compile_section_and_survey(tmp_path):
    _strong_fixture(tmp_path)
    result = compile_section(tmp_path, "ch01/sec01")
    assert result["ok"] is True
    assert result["rounds"] >= 1
    assert result["writer_backend"] == "deterministic"
    assert (tmp_path / "sections" / "ch01" / "sec01" / "final.md").exists()
    assert (tmp_path / "sections" / "ch01" / "sec01" / "revision_trace.json").exists()
    assert (tmp_path / "sections" / "ch01" / "sec01" / "prompt_packets" / "round_00.json").exists()
    assert (tmp_path / "sections" / "ch01" / "sec01" / "prompt_packets" / "round_00.md").exists()
    compiled = compile_survey(tmp_path)
    assert compiled["ok"] is True
    assert (tmp_path / "final.md").exists()
    assert (tmp_path / "chapters" / "ch01" / "editorial_review.json").exists()


def test_revision_loop_requires_enough_detail(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", min_chars=2600, max_rounds=3)
    assert result["ok"] is True
    assert result["rounds"] > 1
    review = json.loads((tmp_path / "sections" / "ch01" / "sec01" / "review.json").read_text(encoding="utf-8"))
    assert review["verdict"] == "PASS"


def test_run_ready_sections_batches_without_manual_continue(tmp_path):
    _strong_fixture(tmp_path)
    result = run_ready_sections(tmp_path, limit=2, max_rounds=3, min_chars=1200)
    assert result["ok"] is True
    assert result["processed"] == 2
    assert result["passed"] == 2


def test_human_packet_backend_waits_for_response(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="human-packet")
    assert result["ok"] is False
    assert result["reason"] == "human_response_missing"
    assert result["expected_response"].endswith("human_responses/round_00.md")
    assert (tmp_path / "sections" / "ch01" / "sec01" / "prompt_packets" / "round_00.md").exists()
    review = json.loads((tmp_path / "sections" / "ch01" / "sec01" / "review.json").read_text(encoding="utf-8"))
    assert review["verdict"] == "WAITING_FOR_HUMAN"


def test_human_packet_backend_consumes_response(tmp_path):
    _strong_fixture(tmp_path)
    section_dir = tmp_path / "sections" / "ch01" / "sec01"
    pack = json.loads((section_dir / "evidence_pack.json").read_text(encoding="utf-8"))
    claim_ids = pack["claim_ids"][:3]
    evidence_ids = pack["evidence_ids"][:4]
    response = section_dir / "human_responses" / "round_00.md"
    response.parent.mkdir(parents=True)
    response.write_text(
        "# Human Section\n\n"
        "## Architecture Synthesis\n\n"
        f"Human response with [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}].\n\n"
        "## Evaluation And Risk Boundary\n\n"
        f"Evaluation response with [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}].\n\n"
        "## Contradiction Slots\n\n"
        f"Contradiction response with [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}] [evidence:{evidence_ids[3]}].\n\n"
        "## Source Map\n\n"
        "Sources are preserved.\n\n"
        "## Claim Map\n\n"
        "Claims are preserved.\n\n"
        "## Open Problems\n\n"
        "Open problems are preserved.\n",
        encoding="utf-8",
    )
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="human-packet", min_chars=100)
    assert result["ok"] is True
    assert result["writer_backend"] == "human-packet"
    assert "Human response" in (section_dir / "final.md").read_text(encoding="utf-8")


def test_human_packet_fallback_keeps_automation_running(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="human-packet-fallback")
    assert result["ok"] is True
    assert result["writer_backend"] == "human-packet-fallback"


def test_local_command_backend_consumes_stdout(tmp_path):
    _strong_fixture(tmp_path)
    section_dir = tmp_path / "sections" / "ch01" / "sec01"
    pack = json.loads((section_dir / "evidence_pack.json").read_text(encoding="utf-8"))
    claim_ids = pack["claim_ids"][:3]
    evidence_ids = pack["evidence_ids"][:4]
    script = tmp_path / "writer.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.read()\n"
        "print('# Local Command Section')\n"
        "print('\\n## Architecture Synthesis\\n')\n"
        f"print('Local command with [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}].')\n"
        "print('\\n## Evaluation And Risk Boundary\\n')\n"
        f"print('Evaluation with [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}].')\n"
        "print('\\n## Contradiction Slots\\n')\n"
        f"print('Contradiction with [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}] [evidence:{evidence_ids[3]}].')\n"
        "print('\\n## Source Map\\nSources preserved.')\n"
        "print('\\n## Claim Map\\nClaims preserved.')\n"
        "print('\\n## Open Problems\\nOpen problems preserved.')\n",
        encoding="utf-8",
    )
    result = run_section_revision_loop(
        tmp_path,
        "ch01/sec01",
        writer_backend="local-command",
        writer_command=f"{sys.executable} {script}",
        min_chars=100,
    )
    assert result["ok"] is True
    assert result["writer_backend"] == "local-command"
    assert "Local command" in (section_dir / "final.md").read_text(encoding="utf-8")


def test_local_command_backend_reports_missing_command(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="local-command")
    assert result["ok"] is False
    assert result["reason"] == "writer_failed"
    assert result["writer_error"] == "missing_command"


def test_local_command_backend_reports_nonzero_exit(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(
        tmp_path,
        "ch01/sec01",
        writer_backend="local-command",
        writer_command=f"{sys.executable} -c 'import sys; print(\"bad\", file=sys.stderr); sys.exit(7)'",
    )
    assert result["ok"] is False
    assert result["reason"] == "writer_failed"
    assert result["writer_error"].startswith("exit_7:")


def test_pane_packet_backend_prepares_dispatch_and_waits(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="pane-packet")
    assert result["ok"] is False
    assert result["reason"] == "pane_response_missing"
    assert result["pane_submitted"] is False
    assert result["pane_dispatch"].endswith("pane_dispatch/round_00.md")
    assert result["expected_response"].endswith("human_responses/round_00.md")
    assert (tmp_path / "sections" / "ch01" / "sec01" / "pane_dispatch" / "round_00.md").exists()
    review = json.loads((tmp_path / "sections" / "ch01" / "sec01" / "review.json").read_text(encoding="utf-8"))
    assert review["verdict"] == "WAITING_FOR_PANE"


def test_pane_packet_backend_consumes_response(tmp_path):
    _strong_fixture(tmp_path)
    section_dir = tmp_path / "sections" / "ch01" / "sec01"
    pack = json.loads((section_dir / "evidence_pack.json").read_text(encoding="utf-8"))
    claim_ids = pack["claim_ids"][:3]
    evidence_ids = pack["evidence_ids"][:4]
    response = section_dir / "human_responses" / "round_00.md"
    response.parent.mkdir(parents=True)
    response.write_text(
        "# Pane Section\n\n"
        "## Architecture Synthesis\n\n"
        f"Pane response with [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}].\n\n"
        "## Evaluation And Risk Boundary\n\n"
        f"Evaluation response with [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}].\n\n"
        "## Contradiction Slots\n\n"
        f"Contradiction response with [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}] [evidence:{evidence_ids[3]}].\n\n"
        "## Source Map\n\n"
        "Sources are preserved.\n\n"
        "## Claim Map\n\n"
        "Claims are preserved.\n\n"
        "## Open Problems\n\n"
        "Open problems are preserved.\n",
        encoding="utf-8",
    )
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="pane-packet", min_chars=100)
    assert result["ok"] is True
    assert result["writer_backend"] == "pane-packet"
    assert "Pane response" in (section_dir / "final.md").read_text(encoding="utf-8")


def test_pane_packet_fallback_keeps_automation_running(tmp_path):
    _strong_fixture(tmp_path)
    result = run_section_revision_loop(tmp_path, "ch01/sec01", writer_backend="pane-packet-fallback")
    assert result["ok"] is True
    assert result["writer_backend"] == "pane-packet-fallback"


def test_watch_pane_responses_reports_pending(tmp_path):
    _strong_fixture(tmp_path)
    result = watch_pane_responses(tmp_path)
    assert result["ok"] is False
    assert result["processed"] == 0
    assert result["pending_responses"] >= 30
    assert (tmp_path / "pane_response_watch.json").exists()


def test_watch_pane_responses_finalizes_existing_response(tmp_path):
    _strong_fixture(tmp_path)
    section_dir = tmp_path / "sections" / "ch01" / "sec01"
    pack = json.loads((section_dir / "evidence_pack.json").read_text(encoding="utf-8"))
    claim_ids = pack["claim_ids"][:3]
    evidence_ids = pack["evidence_ids"][:4]
    response = section_dir / "human_responses" / "round_00.md"
    response.parent.mkdir(parents=True)
    response.write_text(
        "# Watched Pane Section\n\n"
        "## Architecture Synthesis\n\n"
        f"Watched response with [claim:{claim_ids[0]}] [evidence:{evidence_ids[0]}].\n\n"
        "## Evaluation And Risk Boundary\n\n"
        f"Evaluation response with [claim:{claim_ids[1]}] [evidence:{evidence_ids[1]}].\n\n"
        "## Contradiction Slots\n\n"
        f"Contradiction response with [claim:{claim_ids[2]}] [evidence:{evidence_ids[2]}] [evidence:{evidence_ids[3]}].\n\n"
        "## Source Map\n\n"
        "Sources are preserved.\n\n"
        "## Claim Map\n\n"
        "Claims are preserved.\n\n"
        "## Open Problems\n\n"
        "Open problems are preserved.\n",
        encoding="utf-8",
    )
    result = watch_pane_responses(tmp_path, limit=1, min_chars=100)
    assert result["ok"] is True
    assert result["processed"] == 1
    assert result["passed"] == 1
    assert "Watched response" in (section_dir / "final.md").read_text(encoding="utf-8")
