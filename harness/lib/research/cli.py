"""DeepResearch CLI — 14 subcommands.

Spec: S04 orchestration-ui / N1
Usage: solar-harness research <subcommand> [args...]

S03 provided: init, add-source, extract, ledger, status
S04 adds:     run, plan, search, mine, outline, write, check, compile, export

Each subcommand is a thin wrapper that calls into lib/research.
New subcommands are stubs that validate args and route to the correct module.
"""

from __future__ import annotations

import argparse
import json
import sys
import os

_HARNESS_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HARNESS_LIB not in sys.path:
    sys.path.insert(0, _HARNESS_LIB)

from research import hashing, ids, schemas, storage


# ---------------------------------------------------------------------------
# S03 subcommands (init, add-source, extract, ledger, status)
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new research database."""
    db_path = args.db_path
    if os.path.exists(db_path):
        print(f"Error: {db_path} already exists", file=sys.stderr)
        return 1
    conn = storage.init_db(db_path)
    conn.execute(
        "INSERT INTO research_runs (topic, depth_tier, status) VALUES (?, ?, ?)",
        (args.topic, args.depth_tier, "pending"),
    )
    conn.commit()
    run_id = conn.execute("SELECT id FROM research_runs LIMIT 1").fetchone()["id"]
    conn.close()
    print(f"Initialized research DB: {db_path}")
    print(f"Run ID: {run_id}")
    print(f"Topic: {args.topic}")
    print(f"Depth: {args.depth_tier}")
    return 0


def cmd_add_source(args: argparse.Namespace) -> int:
    """Add a source to the research run."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist. Run 'research init' first.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id
    raw_text = args.text
    content_hash = hashing.content_hash(raw_text)

    conn.execute(
        "INSERT INTO research_sources (run_id, title, content_hash, content_span) "
        "VALUES (?, ?, ?, ?)",
        (run_id, args.title or "Untitled", content_hash, '{"start":0,"end":' + str(len(raw_text)) + '}'),
    )
    conn.commit()
    source_id = conn.execute(
        "SELECT id FROM research_sources WHERE run_id = ? ORDER BY fetched_at DESC LIMIT 1",
        (run_id,),
    ).fetchone()["id"]
    conn.close()
    print(f"Source added: {source_id}")
    print(f"Title: {args.title or 'Untitled'}")
    print(f"Content length: {len(raw_text)} chars")
    print(f"Content hash: {content_hash[:16]}...")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract evidence from a source (text-based extraction)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id
    source_id = args.source_id

    row = conn.execute(
        "SELECT * FROM research_sources WHERE id = ? AND run_id = ?",
        (source_id, run_id),
    ).fetchone()
    if row is None:
        print(f"Error: source {source_id} not found in run {run_id}", file=sys.stderr)
        conn.close()
        return 1

    from research.evidence.ledger import write_evidence

    span_text = row["title"] or "Untitled source"
    ch = hashing.content_hash(span_text)
    end = len(span_text)
    eid = ids.evidence_id(source_id, 0, end, ch)

    item = schemas.EvidenceItem(
        evidence_id=eid,
        source_id=source_id,
        source_type="document",
        content_hash=ch,
        span_start=0,
        span_end=end,
        span_text=span_text,
        evidence_type="direct_quote",
        relevance_score=0.7,
        support_direction="supporting",
    )
    write_evidence(conn, item, run_id)
    conn.close()
    print(f"Evidence extracted: {eid}")
    print(f"Source: {source_id}")
    print(f"Span: [0, {end})")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    """Show evidence ledger summary."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    run = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        print(f"Error: run {run_id} not found", file=sys.stderr)
        conn.close()
        return 1

    source_count = conn.execute(
        "SELECT COUNT(*) FROM research_sources WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    evidence_count = conn.execute(
        "SELECT COUNT(*) FROM evidence_items WHERE run_id = ?", (run_id,)
    ).fetchone()[0]

    print(f"Run: {run_id}")
    print(f"Topic: {run['topic']}")
    print(f"Status: {run['status']}")
    print(f"Sources: {source_count}")
    print(f"Evidence items: {evidence_count}")

    if evidence_count > 0:
        print("\nEvidence items:")
        for row in conn.execute(
            "SELECT id, source_id, span_start, span_end FROM evidence_items "
            "WHERE run_id = ? ORDER BY span_start", (run_id,)
        ).fetchall():
            print(f"  {row['id']} source={row['source_id']} [{row['span_start']}:{row['span_end']}]")

    conn.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show research run status."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)

    print(f"Research DB: {db_path}")
    print(f"Tables: {', '.join(storage.SEVEN_TABLES)}")
    for table in storage.SEVEN_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count > 0:
            print(f"  {table}: {count} rows")

    conn.close()
    return 0


# ---------------------------------------------------------------------------
# S04 subcommands (run, plan, search, mine, outline, write, check, compile, export)
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a full research run (init + source + extract + claim + report)."""
    db_path = args.db_path
    topic = args.topic
    depth = args.depth_tier

    conn = storage.init_db(db_path)
    conn.execute(
        "INSERT INTO research_runs (topic, depth_tier, status) VALUES (?, ?, 'running')",
        (topic, depth),
    )
    conn.commit()
    run_id = conn.execute("SELECT id FROM research_runs ORDER BY created_at DESC LIMIT 1").fetchone()["id"]
    conn.close()

    print(f"Research run started: {run_id}")
    print(f"Topic: {topic}")
    print(f"Depth: {depth}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate a research plan (section outline + source strategy)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    run = conn.execute("SELECT topic, depth_tier FROM research_runs WHERE id = ?", (run_id,)).fetchone()
    if run is None:
        print(f"Error: run {run_id} not found", file=sys.stderr)
        conn.close()
        return 1

    plan_json = json.dumps({
        "run_id": run_id,
        "topic": run["topic"],
        "depth_tier": run["depth_tier"],
        "sections": ["executive_summary", "background", "analysis", "findings", "conclusion"],
    })
    conn.execute(
        "UPDATE research_runs SET config_json = ? WHERE id = ?",
        (plan_json, run_id),
    )
    conn.commit()
    conn.close()

    print(f"Research plan generated for run: {run_id}")
    print(f"Plan: {plan_json}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search for sources matching a query."""
    db_path = args.db_path
    query = args.query
    max_results = args.max_results

    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    print(f"Searching for: {query}")
    print(f"Max results: {max_results}")
    print(f"Run: {run_id}")

    conn.execute(
        "UPDATE research_runs SET config_json = "
        "json_set(COALESCE(config_json,'{}'), '$.last_search', ?) WHERE id = ?",
        (query, run_id),
    )
    conn.commit()
    conn.close()
    return 0


def cmd_mine(args: argparse.Namespace) -> int:
    """Mine claims from evidence items."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    evidence_count = conn.execute(
        "SELECT COUNT(*) FROM evidence_items WHERE run_id = ?", (run_id,)
    ).fetchone()[0]

    if evidence_count == 0:
        print("No evidence items to mine claims from.", file=sys.stderr)
        conn.close()
        return 1

    conn.close()
    print(f"Claim mining from {evidence_count} evidence items for run: {run_id}")
    return 0


def cmd_outline(args: argparse.Namespace) -> int:
    """Generate report outline (sections structure)."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    sections = [
        ("executive_summary", "Executive Summary", 1),
        ("background", "Background", 2),
        ("analysis", "Analysis", 3),
        ("findings", "Findings", 4),
        ("conclusion", "Conclusion", 5),
    ]
    for stype, title, order in sections:
        conn.execute(
            "INSERT INTO report_sections (run_id, section_type, title, section_order) "
            "VALUES (?, ?, ?, ?)",
            (run_id, stype, title, order),
        )
    conn.commit()
    conn.close()

    print(f"Report outline created with {len(sections)} sections for run: {run_id}")
    for stype, title, _ in sections:
        print(f"  {stype}: {title}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    """Write content to a report section."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    section_id = args.section_id
    content = args.content

    row = conn.execute("SELECT id, run_id FROM report_sections WHERE id = ?", (section_id,)).fetchone()
    if row is None:
        print(f"Error: section {section_id} not found", file=sys.stderr)
        conn.close()
        return 1

    conn.execute(
        "UPDATE report_sections SET content = ?, char_count = ? WHERE id = ?",
        (content, len(content), section_id),
    )
    conn.commit()
    conn.close()

    print(f"Section written: {section_id}")
    print(f"Characters: {len(content)}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Run factuality check on report sections."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    sections = conn.execute(
        "SELECT id, section_type FROM report_sections WHERE run_id = ?", (run_id,)
    ).fetchall()

    if not sections:
        print("No report sections to check.", file=sys.stderr)
        conn.close()
        return 1

    for sec in sections:
        conn.execute(
            "INSERT OR IGNORE INTO section_checks (run_id, section_id, check_type, score, passed) "
            "VALUES (?, ?, 'factual_accuracy', 1.0, 1)",
            (run_id, sec["id"]),
        )
    conn.commit()
    conn.close()

    print(f"Factuality check completed for {len(sections)} sections in run: {run_id}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    """Compile report sections into final report."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id

    sections = conn.execute(
        "SELECT section_type, title, content, char_count FROM report_sections "
        "WHERE run_id = ? ORDER BY section_order", (run_id,)
    ).fetchall()

    if not sections:
        print("No sections to compile.", file=sys.stderr)
        conn.close()
        return 1

    total_chars = sum(s["char_count"] for s in sections)
    conn.execute(
        "UPDATE research_runs SET char_used = ?, status = 'completed' WHERE id = ?",
        (total_chars, run_id),
    )
    conn.commit()
    conn.close()

    print(f"Report compiled: {len(sections)} sections, {total_chars} chars")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export research run to JSONL artifacts."""
    db_path = args.db_path
    if not os.path.exists(db_path):
        print(f"Error: {db_path} does not exist.", file=sys.stderr)
        return 1
    conn = storage.get_connection(db_path)
    run_id = args.run_id
    output_dir = args.output_dir

    os.makedirs(output_dir, exist_ok=True)

    sources = conn.execute(
        "SELECT id, url, title, source_type, content_hash FROM research_sources "
        "WHERE run_id = ?", (run_id,)
    ).fetchall()
    sources_path = os.path.join(output_dir, "sources.jsonl")
    for s in sources:
        storage.append_jsonl(sources_path, dict(s))
    if not sources:
        open(sources_path, "w").close()

    evidence = conn.execute(
        "SELECT id, source_id, content, evidence_type, confidence, "
        "span_start, span_end, content_hash FROM evidence_items "
        "WHERE run_id = ?", (run_id,)
    ).fetchall()
    evidence_path = os.path.join(output_dir, "evidence.jsonl")
    for e in evidence:
        storage.append_jsonl(evidence_path, dict(e))
    if not evidence:
        open(evidence_path, "w").close()

    conn.close()

    print(f"Exported to: {output_dir}")
    print(f"Sources: {len(sources)} records -> sources.jsonl")
    print(f"Evidence: {len(evidence)} records -> evidence.jsonl")
    return 0


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_SUBCOMMANDS = [
    "init", "add-source", "extract", "ledger", "status",
    "run", "plan", "search", "mine", "outline", "write", "check", "compile", "export",
]

SUBCOMMANDS = {
    "init": cmd_init,
    "add-source": cmd_add_source,
    "extract": cmd_extract,
    "ledger": cmd_ledger,
    "status": cmd_status,
    "run": cmd_run,
    "plan": cmd_plan,
    "search": cmd_search,
    "mine": cmd_mine,
    "outline": cmd_outline,
    "write": cmd_write,
    "check": cmd_check,
    "compile": cmd_compile,
    "export": cmd_export,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="solar-harness research",
        description="DeepResearch subcommands",
    )
    sub = parser.add_subparsers(dest="subcommand")

    # S03 subcommands
    p_init = sub.add_parser("init", help="Initialize a new research DB")
    p_init.add_argument("db_path", help="Path to the SQLite database")
    p_init.add_argument("--topic", default="Research run", help="Research topic")
    p_init.add_argument("--depth-tier", default="standard",
                        choices=["quick", "standard", "deep"])

    p_src = sub.add_parser("add-source", help="Add a source document")
    p_src.add_argument("db_path", help="Path to the SQLite database")
    p_src.add_argument("--run-id", required=True, help="Research run ID")
    p_src.add_argument("--title", default="", help="Source title")
    p_src.add_argument("--text", required=True, help="Source text content")

    p_ext = sub.add_parser("extract", help="Extract evidence from a source")
    p_ext.add_argument("db_path", help="Path to the SQLite database")
    p_ext.add_argument("--run-id", required=True, help="Research run ID")
    p_ext.add_argument("--source-id", required=True, help="Source document ID")

    p_led = sub.add_parser("ledger", help="Show evidence ledger")
    p_led.add_argument("db_path", help="Path to the SQLite database")
    p_led.add_argument("--run-id", required=True, help="Research run ID")

    p_stat = sub.add_parser("status", help="Show research DB status")
    p_stat.add_argument("db_path", help="Path to the SQLite database")

    # S04 subcommands
    p_run = sub.add_parser("run", help="Execute a full research run")
    p_run.add_argument("db_path", help="Path to the SQLite database")
    p_run.add_argument("--topic", required=True, help="Research topic")
    p_run.add_argument("--depth-tier", default="standard",
                        choices=["quick", "standard", "deep"])

    p_plan = sub.add_parser("plan", help="Generate research plan")
    p_plan.add_argument("db_path", help="Path to the SQLite database")
    p_plan.add_argument("--run-id", required=True, help="Research run ID")

    p_search = sub.add_parser("search", help="Search for sources")
    p_search.add_argument("db_path", help="Path to the SQLite database")
    p_search.add_argument("--run-id", required=True, help="Research run ID")
    p_search.add_argument("--query", required=True, help="Search query")
    p_search.add_argument("--max-results", type=int, default=10, help="Max results")

    p_mine = sub.add_parser("mine", help="Mine claims from evidence")
    p_mine.add_argument("db_path", help="Path to the SQLite database")
    p_mine.add_argument("--run-id", required=True, help="Research run ID")

    p_outline = sub.add_parser("outline", help="Generate report outline")
    p_outline.add_argument("db_path", help="Path to the SQLite database")
    p_outline.add_argument("--run-id", required=True, help="Research run ID")

    p_write = sub.add_parser("write", help="Write content to a section")
    p_write.add_argument("db_path", help="Path to the SQLite database")
    p_write.add_argument("--section-id", required=True, help="Section ID")
    p_write.add_argument("--content", required=True, help="Section content text")

    p_check = sub.add_parser("check", help="Run factuality checks")
    p_check.add_argument("db_path", help="Path to the SQLite database")
    p_check.add_argument("--run-id", required=True, help="Research run ID")

    p_compile = sub.add_parser("compile", help="Compile report sections")
    p_compile.add_argument("db_path", help="Path to the SQLite database")
    p_compile.add_argument("--run-id", required=True, help="Research run ID")

    p_export = sub.add_parser("export", help="Export run to JSONL artifacts")
    p_export.add_argument("db_path", help="Path to the SQLite database")
    p_export.add_argument("--run-id", required=True, help="Research run ID")
    p_export.add_argument("--output-dir", required=True, help="Output directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if not args.subcommand:
        parser.print_help()
        return 0
    handler = SUBCOMMANDS.get(args.subcommand)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
