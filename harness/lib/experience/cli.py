"""CLI for Solar Experience Memory.

Provides: extract | compress | index | query | backfill | stats
Called via solar-harness.sh experience <subcommand>
"""
import json
import logging
import sys
from typing import List

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def cmd_extract(args: List[str]) -> int:
    """Extract terminal sprints to trajectory files."""
    from .extractor import extract_sprint, extract_all_terminal

    as_json = "--json" in args
    limit_idx = args.index("--limit") if "--limit" in args else -1
    limit = int(args[limit_idx + 1]) if limit_idx >= 0 and limit_idx + 1 < len(args) else None

    sid_args = [a for a in args if not a.startswith("-") and "sprint-" in a]
    if sid_args:
        results = []
        for sid in sid_args:
            traj = extract_sprint(sid)
            if traj:
                results.append(traj)
            else:
                if as_json:
                    print(json.dumps({"ok": False, "error": f"not terminal or not found: {sid}"}))
                else:
                    print(f"SKIP: {sid} (not terminal or not found)")
        if results and as_json:
            print(json.dumps({"ok": True, "extracted": len(results), "trajectories": results}))
        elif results:
            for t in results:
                print(f"OK: {t['sid']} status={t['status']} outcome={t['outcome']}")
        return 0

    results = extract_all_terminal(limit=limit)
    if as_json:
        print(json.dumps({"ok": True, "extracted": len(results), "trajectories": results}))
    else:
        for t in results:
            print(f"OK: {t['sid']} status={t['status']} outcome={t['outcome']}")
        print(f"Total: {len(results)}")
    return 0


def cmd_compress(args: List[str]) -> int:
    """Compress trajectories into experience entries."""
    from .extractor import extract_all_terminal
    from .compressor import compress_trajectories

    as_json = "--json" in args
    trajectories = extract_all_terminal()
    entries = compress_trajectories(trajectories)
    if as_json:
        print(json.dumps({"ok": True, "entries": len(entries)}))
    else:
        print(f"Compressed {len(trajectories)} trajectories → {len(entries)} entries")
    return 0


def cmd_index(args: List[str]) -> int:
    """Rebuild the SQLite+FTS5 index."""
    from .index import init_db
    from .extractor import extract_all_terminal
    from .compressor import compress_trajectories

    as_json = "--json" in args
    init_db()
    trajectories = extract_all_terminal()
    entries = compress_trajectories(trajectories)
    if as_json:
        print(json.dumps({"ok": True, "indexed": len(entries)}))
    else:
        print(f"Index rebuilt: {len(entries)} entries")
    return 0


def cmd_query(args: List[str]) -> int:
    """Query experience memory for a sprint or free text."""
    from .query import query_for_sprint, query_fts_memories

    as_json = "--json" in args
    sid = None
    text = None
    limit = 10

    i = 0
    while i < len(args):
        if args[i] == "--sid" and i + 1 < len(args):
            sid = args[i + 1]
            i += 2
        elif args[i] == "--text" and i + 1 < len(args):
            text = args[i + 1]
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    if sid:
        result = query_for_sprint(sid, limit=limit)
    elif text:
        result = query_fts_memories(text, limit=limit)
    else:
        print("error: --sid <sid> or --text <query> required", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(result, default=str))
    else:
        memories = result.get("memories", [])
        print(f"Found {len(memories)} memories for sid={sid or text}")
        for m in memories:
            print(f"  [{m['pattern_class']}] {m.get('advisory','')[:100]} "
                  f"(hits={m.get('hit_count',0)} reason={m.get('match_reason','')})")
    return 0


def cmd_backfill(args: List[str]) -> int:
    """Backfill all historical sprints."""
    from .backfill import run_backfill

    as_json = "--json" in args
    result = run_backfill()
    if as_json:
        print(json.dumps(result))
    else:
        print(f"Backfill: processed={result['processed']} skipped={result['skipped']} "
              f"errors={result['errors']}")
    return 0


def cmd_stats(args: List[str]) -> int:
    """Show aggregate statistics."""
    from .query import get_stats

    as_json = "--json" in args
    s = get_stats()
    if as_json:
        print(json.dumps(s))
    else:
        print(f"Total entries: {s['total_entries']}")
        print("By pattern:")
        for k, v in s.get("by_pattern", {}).items():
            print(f"  {k}: {v}")
        print("By outcome:")
        for k, v in s.get("by_outcome", {}).items():
            print(f"  {k}: {v}")
    return 0


COMMANDS = {
    "extract": cmd_extract,
    "compress": cmd_compress,
    "index": cmd_index,
    "query": cmd_query,
    "backfill": cmd_backfill,
    "stats": cmd_stats,
}


def main(args: List[str]) -> int:
    if not args:
        print("Usage: solar-harness experience <extract|compress|index|query|backfill|stats> [options]",
              file=sys.stderr)
        return 1
    subcmd = args[0]
    rest = args[1:]
    handler = COMMANDS.get(subcmd)
    if not handler:
        print(f"Unknown subcommand: {subcmd}. Available: {', '.join(COMMANDS)}", file=sys.stderr)
        return 1
    try:
        return handler(rest)
    except Exception as e:
        logger.error("experience %s failed: %s", subcmd, e)
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1
