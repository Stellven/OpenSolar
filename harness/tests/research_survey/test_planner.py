from __future__ import annotations

import os
import sys

_HARNESS_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib")
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research.survey.planner import create_survey_plan, write_survey_plan


def test_planner_creates_professor_grade_shape(tmp_path):
    plan = create_survey_plan("隐空间推理技术架构和演进方向", target_chars=50000)
    assert len(plan["report_ast"]["chapters"]) >= 8
    assert len(plan["report_ast"]["sections"]) >= 30
    assert len(plan["source_matrix"]) == len(plan["report_ast"]["sections"])
    assert all(section["min_evidence"] >= 4 for section in plan["report_ast"]["sections"])

    files = write_survey_plan(plan, tmp_path)
    assert (tmp_path / "survey_plan.json").exists()
    assert (tmp_path / "survey_report_ast.json").exists()
    assert files["source_matrix"].endswith("survey_source_matrix.json")
