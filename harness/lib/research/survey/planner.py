"""Survey planner for 5-10 万字 DeepResearch reports."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .schemas import (
    ChapterSpec,
    SectionSpec,
    SourceMatrix,
    SurveyQuestion,
    SurveyReportAST,
    SurveyRun,
    to_dict,
)

DEFAULT_CHAPTER_TITLES = [
    "问题定义与研究边界",
    "历史脉络与技术演进",
    "核心架构范式",
    "方法分类与代表系统",
    "评估方法与基准体系",
    "工程实现与部署约束",
    "风险、安全与可解释性",
    "产业生态与开源实现",
    "争议、反证与失败模式",
    "未来路线图与开放问题",
]

DEFAULT_SECTION_TITLES = [
    "研究问题与术语边界",
    "关键机制与设计空间",
    "证据链与代表工作",
    "工程取舍与评价标准",
]

CONFERENCE_CHAPTER_TITLES = [
    "会议信号与中心论点",
    "议题迁移与关键变化",
    "论文热点、分歧与机会",
    "规划、记忆与深度研究信号",
    "协议、规格与多 Agent 协作信号",
    "评测、基准与工程约束信号",
    "行动路线与吸收映射",
    "风险、反证与后续实验",
]

CONFERENCE_SECTION_TITLES = [
    "会议在讨论什么问题",
    "代表论文与议题观点",
    "核心分歧与技术挑战",
    "对 Solar 的启示",
]

INSIGHT_CHAPTER_TITLES = [
    "核心判断与中心论点",
    "信号地图与证据强度",
    "关键变化、分歧与机会",
    "技术、产品与生态影响",
    "行动路线与设计映射",
    "预测、反证与观察指标",
    "风险边界与证据缺口",
    "路线图与下一步",
]

INSIGHT_SECTION_TITLES = [
    "本节判断",
    "证据链",
    "影响与行动",
    "反证和观察",
]


def _suggested_figure_type(chapter_title: str, section_title: str, *, insight_mode: bool) -> str:
    if not insight_mode:
        return ""
    text = f"{chapter_title} {section_title}".lower()
    if re.search(r"路线图|下一步|roadmap|预测|forecast|观察指标|watch", text):
        return "roadmap_timeline"
    if re.search(r"风险|反证|边界|缺口|失败|risk|gap|limit", text):
        return "risk_map"
    if re.search(r"行动|吸收|映射|架构|architecture|runtime|系统|规格|协议|生态|工程", text):
        return "architecture_map"
    if re.search(r"证据|signal|source|强度|质量|链", text):
        return "evidence_map"
    if re.search(r"分歧|机会|比较|对比|取舍|opportunit|difference", text):
        return "comparison_matrix"
    if re.search(r"流程|过程|pipeline|process|工作流", text):
        return "process_flow"
    return "insight_argument_map"


def _stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def _normalize_brief(brief: str) -> str:
    return re.sub(r"\s+", " ", str(brief or "").strip())


def _is_conference_insight_brief(brief: str) -> bool:
    text = _normalize_brief(brief).lower()
    conference_signals = ("会议", "学术会议", "conference", "accepted papers", "workshops", "paper index", "program/")
    intent_signals = ("洞察", "发表问题", "讨论问题", "重大技术挑战", "如何发展")
    return any(token in text for token in conference_signals) and any(token in text for token in intent_signals)


def _is_insight_brief(brief: str, planner_mode_hint: str | None = None) -> bool:
    hint = str(planner_mode_hint or "").lower()
    if hint == "insight" or "insight" in hint:
        return True
    text = _normalize_brief(brief).lower()
    return any(token in text for token in ("deepdive", "deep dive", "深度研究", "深研", "洞察", "insight"))


def _conference_subject(brief: str) -> str:
    text = _normalize_brief(brief)
    match = re.search(r"\b([A-Z]{2,}\s*20\d{2})\b", text)
    if match:
        return re.sub(r"\s+", " ", match.group(1).strip()).upper()
    zh_match = re.search(r"([A-Za-z]{2,}\s*20\d{2}|20\d{2}\s*[A-Za-z]{2,})", text)
    if zh_match:
        return re.sub(r"\s+", " ", zh_match.group(1).strip()).upper()
    return text[:32] if text else "该会议"


def _conference_report_title(brief: str) -> str:
    subject = _conference_subject(brief)
    if "solar" in brief.lower():
        return f"深度报告：{subject} Agent 发展、技术挑战与 Solar 路线"
    return f"深度报告：{subject} Agent 议题与技术挑战"


def _insight_report_title(brief: str, *, conference_mode: bool) -> str:
    if conference_mode:
        return _conference_report_title(brief)
    subject = _normalize_brief(brief)
    subject = re.sub(r"^(deepdive|deep dive|insight|洞察|深度研究)[:：\s-]*", "", subject, flags=re.I).strip()
    return f"DeepDive 洞察报告：{subject[:64] if subject else '核心议题'}"


def _chapter_objective(brief: str, title: str, *, insight_mode: bool, conference_mode: bool) -> str:
    if not insight_mode:
        return f"Explain {title} for {brief}."
    subject = _conference_subject(brief)
    if conference_mode:
        objective_map = {
            "会议信号与中心论点": f"State what central thesis {subject} supports about Agent systems, based on conference tracks, accepted papers, and workshops; avoid generic methodology talk.",
            "议题迁移与关键变化": f"Explain how {subject} shifts the discussion from model capability to system capability, using official tracks and conference framing.",
            "论文热点、分歧与机会": f"Extract the main problem clusters, disagreements, and opportunities emerging from {subject} accepted papers instead of listing papers mechanically.",
            "规划、记忆与深度研究信号": f"Synthesize how {subject} papers redefine planning horizon, long-horizon memory, and deep research workflows.",
            "协议、规格与多 Agent 协作信号": f"Explain how {subject} frames protocols, specifications, and multi-agent coordination as first-class system problems.",
            "评测、基准与工程约束信号": f"Summarize what {subject} implies for evaluation, benchmarking, deployment constraints, and operational cost.",
            "行动路线与吸收映射": f"Translate {subject} insights into concrete architecture, product, runtime, and roadmap absorption paths.",
            "风险、反证与后续实验": f"Turn {subject} signals into falsifiable risks, open questions, and next experiments.",
        }
        return objective_map.get(title, f"Summarize {title} from {subject} conference signals and paper viewpoints.")
    objective_map = {
        "核心判断与中心论点": f"State the central thesis for {brief}; make the report answer the user's question directly before any background.",
        "信号地图与证据强度": f"Map the strongest signals, evidence quality, counter-signals, and source confidence for {brief}.",
        "关键变化、分歧与机会": f"Explain what is changing, what remains disputed, and which opportunities are genuinely new.",
        "技术、产品与生态影响": f"Translate the signals into technical, product, ecosystem, and strategy implications.",
        "行动路线与设计映射": f"Turn the insight into concrete actions, experiments, design options, roadmap items, operators, schemas, or gates when applicable.",
        "预测、反证与观察指标": f"Build falsifiable forecast packets with drivers, leading indicators, risks, and invalidation conditions.",
        "风险边界与证据缺口": f"Make uncertainty visible; separate facts, interpretations, weak evidence, and open gaps.",
        "路线图与下一步": f"Close with prioritized next steps and a watchlist that can drive follow-up work.",
    }
    return objective_map.get(title, f"Turn {brief} into a thesis-first insight chapter with evidence, action, and falsification.")


def _section_research_question(brief: str, chapter_title: str, section_title: str, *, insight_mode: bool, conference_mode: bool) -> str:
    if not insight_mode:
        return f"{brief} 在“{chapter_title}/{section_title}”上的证据、架构取舍和争议是什么？"
    subject = _conference_subject(brief)
    if conference_mode:
        section_map = {
            "会议在讨论什么问题": f"{subject} 在“{chapter_title}”这一章实际把 Agent 定义成了哪些系统问题？这些问题是从 conference tracks、accepted papers 和 workshops 里如何体现出来的？",
            "代表论文与议题观点": f"{subject} 的代表论文、official pages 和 workshops 在“{chapter_title}”上分别提出了什么判断？哪些观点彼此呼应？",
            "核心分歧与技术挑战": f"{subject} 在“{chapter_title}”上暴露出哪些尚未解决的技术挑战、分歧和工程难点？",
            "对 Solar 的启示": f"基于 {subject} 在“{chapter_title}”上的会议信号，Solar 应吸收哪些思想、避免哪些误判、优先建设哪些能力？",
        }
        return section_map.get(section_title, f"{subject} 在“{chapter_title}/{section_title}”上的会议观点、主要挑战和对 Solar 的启示是什么？")
    section_map = {
        "本节判断": f"本节围绕“{chapter_title}”必须给出什么明确判断？这个判断如何服务整篇 DeepDive 的中心论点？",
        "证据链": f"哪些证据支持、削弱或限制“{chapter_title}”的判断？证据强度和来源边界是什么？",
        "影响与行动": f"“{chapter_title}”可以转成哪些技术、产品、研究、工程或内容行动？优先级如何？",
        "反证和观察": f"哪些反证会推翻“{chapter_title}”的判断？接下来应该观察哪些领先指标？",
    }
    return section_map.get(section_title, f"{brief} 在“{chapter_title}/{section_title}”上的判断、证据、行动和反证是什么？")


def _question_text(brief: str, chapter_title: str, section_title: str | None = None, *, insight_mode: bool, conference_mode: bool) -> str:
    if not insight_mode:
        return f"{brief}: {chapter_title}" if section_title is None else f"{brief}: {chapter_title} / {section_title}"
    subject = _conference_subject(brief)
    if conference_mode:
        if section_title is None:
            return f"{subject}: {chapter_title} 这章应该总结哪些会议级问题？"
        return f"{subject}: {chapter_title} / {section_title}"
    if section_title is None:
        return f"{brief}: {chapter_title} 这章如何支撑中心论点？"
    return f"{brief}: {chapter_title} / {section_title} 的判断、证据、行动和反证是什么？"


def chapter_count_for_target(target_chars: int) -> int:
    if target_chars >= 90000:
        return 12
    if target_chars >= 70000:
        return 10
    return 8


def sections_per_chapter(target_chars: int) -> int:
    return 4 if target_chars < 90000 else 5


def create_survey_plan(
    brief: str,
    target_chars: int = 50000,
    audience: str = "technical",
    domain: str = "ai",
    run_id: str | None = None,
    planner_mode_hint: str | None = None,
) -> dict:
    run_id = run_id or _stable_id("survey", brief + str(target_chars))
    conference_mode = _is_conference_insight_brief(brief)
    insight_mode = conference_mode or _is_insight_brief(brief, planner_mode_hint)
    chapter_titles = CONFERENCE_CHAPTER_TITLES if conference_mode else INSIGHT_CHAPTER_TITLES if insight_mode else DEFAULT_CHAPTER_TITLES
    section_titles = CONFERENCE_SECTION_TITLES if conference_mode else INSIGHT_SECTION_TITLES if insight_mode else DEFAULT_SECTION_TITLES
    chapters_n = chapter_count_for_target(target_chars)
    if insight_mode:
        chapters_n = min(chapters_n, len(chapter_titles))
    per_chapter = sections_per_chapter(target_chars)
    total_sections = chapters_n * per_chapter
    chapter_chars = max(target_chars // chapters_n, 1)
    section_chars = max(target_chars // total_sections, 1)

    run = SurveyRun(run_id=run_id, brief=brief, target_chars=target_chars, audience=audience, domain=domain)
    chapters: list[ChapterSpec] = []
    sections: list[SectionSpec] = []
    questions: list[SurveyQuestion] = []
    source_matrix: list[SourceMatrix] = []

    for cidx in range(1, chapters_n + 1):
        title = chapter_titles[(cidx - 1) % len(chapter_titles)]
        chapter_id = f"ch{cidx:02d}"
        chapters.append(ChapterSpec(
            chapter_id=chapter_id,
            title=title,
            order=cidx,
            target_chars=chapter_chars,
            objective=_chapter_objective(brief, title, insight_mode=insight_mode, conference_mode=conference_mode),
        ))
        parent_q = SurveyQuestion(
            question_id=f"q{cidx:02d}",
            text=(
                f"{_conference_subject(brief)}: {title} 这一章从会议和论文信号中暴露出的核心问题是什么？"
                if conference_mode
                else f"{brief}: {title} 这一章如何支撑中心论点、证据链和行动路线？"
                if insight_mode
                else f"{brief}: {title} 的核心问题是什么？"
            ),
            depth=0,
            required_source_types=["paper", "official_doc", "code", "benchmark"],
        )
        questions.append(parent_q)
        for sidx in range(1, per_chapter + 1):
            section_id = f"{chapter_id}/sec{sidx:02d}"
            section_title = section_titles[(sidx - 1) % len(section_titles)]
            required = ["paper", "official_doc"] if sidx == 1 else ["paper", "code"] if sidx == 2 else ["paper", "benchmark"]
            sections.append(SectionSpec(
                section_id=section_id,
                chapter_id=chapter_id,
                title=f"{title}：{section_title}",
                order=(cidx - 1) * per_chapter + sidx,
                target_chars=section_chars,
                research_question=_section_research_question(brief, title, section_title, insight_mode=insight_mode, conference_mode=conference_mode),
                required_source_types=required,
                min_evidence=4,
                min_claims=3,
                suggested_figure_type=_suggested_figure_type(title, section_title, insight_mode=insight_mode),
            ))
            questions.append(SurveyQuestion(
                question_id=f"q{cidx:02d}_{sidx:02d}",
                text=_question_text(brief, title, section_title, insight_mode=insight_mode, conference_mode=conference_mode),
                parent_id=parent_q.question_id,
                depth=1,
                required_source_types=required,
            ))
            source_matrix.append(SourceMatrix(
                section_id=section_id,
                required_source_types=required,
                recommended_source_types=["survey", "review", "dataset", "negative_result"],
                min_sources=4,
                min_evidence=4,
                contradiction_required=True,
            ))

    ast = SurveyReportAST(
        ast_id=_stable_id("survey_ast", run_id + brief),
        run_id=run_id,
        title=_insight_report_title(brief, conference_mode=conference_mode) if insight_mode else f"Professor-Grade Survey: {brief}",
        target_chars=target_chars,
        chapters=chapters,
        sections=sections,
    )
    planner_mode = "conference_insight" if conference_mode else "insight" if insight_mode else "general_survey"
    return {
        "run": to_dict(run),
        "planner_mode": planner_mode,
        "questions": to_dict(questions),
        "source_matrix": to_dict(source_matrix),
        "report_ast": to_dict(ast),
    }


def write_survey_plan(plan: dict, output_dir: str | Path) -> dict:
    root = Path(output_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "survey_plan": root / "survey_plan.json",
        "survey_report_ast": root / "survey_report_ast.json",
        "source_matrix": root / "survey_source_matrix.json",
    }
    files["survey_plan"].write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    files["survey_report_ast"].write_text(json.dumps(plan["report_ast"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    files["source_matrix"].write_text(json.dumps(plan["source_matrix"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {key: str(path) for key, path in files.items()}
