#!/usr/bin/env python3
"""Slow DB-native YouTube transcript backfill for Tech Hotspot Radar.

This is the production backfill path for historical AI Influence YouTube data.
It advances week by week from 2026-W20 down to 2026-W01 and only uses:

  caption_discovery -> subtitle_download -> browser_capture

It does not enqueue or run local/premium ASR. Browser capture is implemented by
YoutubeTranscriptExtractor through youtube.cli's browser_capture job handler.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:
    yaml = None

UTC = dt.timezone.utc
HARNESS_ROOT = Path("/Users/lisihao/Solar/harness")
LIVE_ROOT = Path("/Users/lisihao/.solar/harness")
DEFAULT_DB = LIVE_ROOT / "state/tech-hotspot-radar/tech-hotspot-radar.sqlite"
DEFAULT_STATE_DIR = LIVE_ROOT / "state/tech-hotspot-radar"
DEFAULT_CONFIG = HARNESS_ROOT / "config/tech-hotspot-radar.yaml"
DEFAULT_STATE_PATH = DEFAULT_STATE_DIR / "youtube-weekly-db-backfill-state.json"
USABLE_SOURCES = {"standard_caption", "youtube_asr_caption", "browser_caption"}
USABLE_TIERS = {"T0", "T1", "T2"}


def iso_z(ts: dt.datetime | None = None) -> str:
    ts = ts or dt.datetime.now(UTC)
    return ts.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")


def parse_week(label: str) -> dt.date:
    year, week = label.split("-W", 1)
    return dt.date.fromisocalendar(int(year), int(week), 1)


def fmt_week(day: dt.date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_labels_newest_first(start_week: str, end_week: str) -> list[str]:
    start = parse_week(start_week)
    end = parse_week(end_week)
    labels: list[str] = []
    cursor = start
    while cursor >= end:
        labels.append(fmt_week(cursor))
        cursor -= dt.timedelta(days=7)
    return labels


def load_min_duration(config_path: Path) -> int:
    if yaml is None or not config_path.exists():
        return 600
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return int(((payload.get("youtube") or {}).get("min_transcript_duration_seconds") or 600))
    except Exception:
        return 600


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def is_usable(row: sqlite3.Row | None) -> bool:
    if row is None:
        return False
    source = str(row["source"] or "")
    tier = str(row["quality_tier"] or "")
    chars = int(row["char_count"] or 0)
    return source in USABLE_SOURCES and tier in USABLE_TIERS and chars >= 200


def week_bounds(week: str) -> tuple[str, str]:
    start = parse_week(week)
    end = start + dt.timedelta(days=7)
    return start.isoformat(), end.isoformat()


def stable_job_id(video_id: str, job_type: str, reason: str) -> str:
    digest = hashlib.sha1(f"{video_id}:{job_type}:{reason}".encode("utf-8")).hexdigest()[:16]
    return f"ytj-{digest}"


def load_state(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "youtube-weekly-db-backfill-state.v1", "completed_weeks": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_week_stats(conn: sqlite3.Connection, week: str, min_duration: int) -> dict[str, Any]:
    start, end = week_bounds(week)
    rows = conn.execute(
        """SELECT v.video_id, v.duration_seconds, t.source, t.quality_tier, t.char_count
           FROM youtube_videos v
           LEFT JOIN youtube_transcripts t USING(video_id)
           WHERE date(v.published_at) >= date(?) AND date(v.published_at) < date(?)""",
        (start, end),
    ).fetchall()
    videos = len(rows)
    usable = 0
    short_or_unknown = 0
    needs = 0
    for row in rows:
        if is_usable(row):
            usable += 1
            continue
        duration = row["duration_seconds"]
        if duration is not None and int(duration) < min_duration:
            short_or_unknown += 1
            continue
        terminal = conn.execute(
            """SELECT 1 FROM youtube_transcript_jobs
               WHERE video_id=? AND status IN ('metadata_only','cancelled','quarantined')
               LIMIT 1""",
            (row["video_id"],),
        ).fetchone()
        if terminal:
            continue
        needs += 1
    jobs = conn.execute(
        """SELECT status, COUNT(*) n
           FROM youtube_transcript_jobs
           WHERE video_id IN (
             SELECT video_id FROM youtube_videos
             WHERE date(published_at) >= date(?) AND date(published_at) < date(?)
           )
           GROUP BY status""",
        (start, end),
    ).fetchall()
    return {
        "week": week,
        "videos": videos,
        "usable": usable,
        "short_or_below_threshold": short_or_unknown,
        "needs_backfill": needs,
        "jobs": {str(row["status"]): int(row["n"]) for row in jobs},
    }


def mark_short_metadata(conn: sqlite3.Connection, week: str, min_duration: int, limit: int) -> int:
    start, end = week_bounds(week)
    rows = conn.execute(
        """SELECT v.video_id, v.duration_seconds
           FROM youtube_videos v
           LEFT JOIN youtube_transcripts t USING(video_id)
           WHERE date(v.published_at) >= date(?) AND date(v.published_at) < date(?)
             AND v.duration_seconds IS NOT NULL AND v.duration_seconds < ?
             AND (t.video_id IS NULL OR NOT (
               t.source IN ('standard_caption','youtube_asr_caption','browser_caption')
               AND t.quality_tier IN ('T0','T1','T2') AND t.char_count >= 200
             ))
           LIMIT ?""",
        (start, end, min_duration, limit),
    ).fetchall()
    now = iso_z()
    for row in rows:
        conn.execute(
            """INSERT INTO youtube_transcripts
               (video_id, transcript_raw, transcript_clean, transcript_status, source, language,
                fetched_at, char_count, quality_score, quality_tier, coverage_ratio, hallucination_risk)
               VALUES (?, '', '', 'metadata_only', 'metadata', '', ?, 0, 0.0, 'T3', 0.0, 1.0)
               ON CONFLICT(video_id) DO UPDATE SET
                 transcript_status='metadata_only',
                 source='metadata',
                 fetched_at=excluded.fetched_at,
                 char_count=0,
                 quality_score=0.0,
                 quality_tier='T3',
                 coverage_ratio=0.0,
                 hallucination_risk=1.0""",
            (row["video_id"], now),
        )
    conn.commit()
    return len(rows)


def enqueue_caption_discovery(conn: sqlite3.Connection, week: str, min_duration: int, limit: int) -> int:
    start, end = week_bounds(week)
    rows = conn.execute(
        """SELECT v.video_id, v.duration_seconds, t.source, t.quality_tier, t.char_count
           FROM youtube_videos v
           LEFT JOIN youtube_transcripts t USING(video_id)
           WHERE date(v.published_at) >= date(?) AND date(v.published_at) < date(?)
             AND (v.duration_seconds IS NULL OR v.duration_seconds >= ?)
             AND (t.video_id IS NULL OR NOT (
               t.source IN ('standard_caption','youtube_asr_caption','browser_caption')
               AND t.quality_tier IN ('T0','T1','T2') AND t.char_count >= 200
             ))
             AND NOT EXISTS (
               SELECT 1 FROM youtube_transcript_jobs j
               WHERE j.video_id=v.video_id
                 AND j.status IN ('pending','running')
             )
             AND NOT EXISTS (
               SELECT 1 FROM youtube_transcript_jobs j
               WHERE j.video_id=v.video_id
                 AND j.status IN ('metadata_only','cancelled','quarantined')
             )
           ORDER BY datetime(v.published_at) DESC
           LIMIT ?""",
        (start, end, min_duration, limit),
    ).fetchall()
    now = iso_z()
    for row in rows:
        job_id = stable_job_id(row["video_id"], "caption_discovery", f"weekly-db-backfill:{week}")
        conn.execute(
            """INSERT INTO youtube_transcript_jobs
               (job_id, video_id, job_type, priority, status, backend, max_attempts, error_message, created_at)
               VALUES (?, ?, 'caption_discovery', 'P2', 'pending', 'subtitle-first', 3, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET
                 status=CASE
                   WHEN youtube_transcript_jobs.status IN ('succeeded','metadata_only','running')
                   THEN youtube_transcript_jobs.status ELSE 'pending' END,
                 next_retry_at=NULL,
                 error_message=excluded.error_message""",
            (job_id, row["video_id"], f"weekly-db-backfill:{week}", now),
        )
    conn.commit()
    return len(rows)


def run_youtube_cli(db: Path, state_dir: Path, job_type: str, limit: int, timeout: int, dry_run: bool) -> dict[str, Any]:
    if limit <= 0:
        return {"job_count": 0, "processed": 0, "skipped": "limit<=0"}
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{HARNESS_ROOT / 'lib'}:{env.get('PYTHONPATH', '')}"
    cmd = [
        sys.executable,
        "-m",
        "youtube.cli",
        "process-transcript-jobs",
        "--db",
        str(db),
        "--state-dir",
        str(state_dir),
        "--job-type",
        job_type,
        "--priority",
        "P0,P1,P2",
        "--limit",
        str(limit),
        "--timeout",
        str(timeout),
        "--json",
    ]
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=str(HARNESS_ROOT))
    text = proc.stdout or ""
    try:
        payload = json.loads(text[text.find("{"):]) if "{" in text else {}
    except Exception:
        payload = {"raw": text[-2000:]}
    payload["rc"] = proc.returncode
    if proc.returncode != 0:
        payload["error"] = text[-2000:]
    return payload


def pick_week(conn: sqlite3.Connection, weeks: list[str], min_duration: int, only_week: str = "") -> tuple[str | None, dict[str, Any]]:
    if only_week:
        return only_week, get_week_stats(conn, only_week, min_duration)
    for week in weeks:
        stats = get_week_stats(conn, week, min_duration)
        active = sum(stats["jobs"].get(status, 0) for status in ("pending", "running", "failed"))
        if stats["needs_backfill"] > 0 or active > 0:
            return week, stats
    return None, {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Slow DB-native YouTube transcript weekly backfill")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--state-path", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--start-week", default="2026-W20")
    parser.add_argument("--end-week", default="2026-W01")
    parser.add_argument("--only-week", default="")
    parser.add_argument("--enqueue-limit", type=int, default=12)
    parser.add_argument("--short-mark-limit", type=int, default=50)
    parser.add_argument("--caption-limit", type=int, default=12)
    parser.add_argument("--subtitle-limit", type=int, default=12)
    parser.add_argument("--browser-limit", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = Path(args.db).expanduser()
    state_dir = Path(args.state_dir).expanduser()
    state_path = Path(args.state_path).expanduser()
    min_duration = load_min_duration(Path(args.config).expanduser())
    weeks = week_labels_newest_first(args.start_week, args.end_week)
    state = load_state(state_path)

    conn = open_db(db)
    try:
        week, before_stats = pick_week(conn, weeks, min_duration, args.only_week)
        if week is None:
            state.update({"last_run_at": iso_z(), "status": "complete", "start_week": args.start_week, "end_week": args.end_week})
            save_state(state_path, state)
            print(json.dumps({"status": "complete", "message": "all target weeks complete"}, ensure_ascii=False, indent=2))
            return 0

        short_marked = 0 if args.dry_run else mark_short_metadata(conn, week, min_duration, args.short_mark_limit)
        enqueued = 0 if args.dry_run else enqueue_caption_discovery(conn, week, min_duration, args.enqueue_limit)
    finally:
        conn.close()

    caption = run_youtube_cli(db, state_dir, "caption_discovery", args.caption_limit, args.timeout, args.dry_run)
    subtitle = run_youtube_cli(db, state_dir, "subtitle_download", args.subtitle_limit, args.timeout, args.dry_run)
    browser = run_youtube_cli(db, state_dir, "browser_capture", args.browser_limit, args.timeout, args.dry_run)

    conn = open_db(db)
    try:
        after_stats = get_week_stats(conn, week, min_duration)
    finally:
        conn.close()

    result = {
        "schema": "youtube-weekly-db-backfill-run.v1",
        "ran_at": iso_z(),
        "week": week,
        "min_duration_seconds": min_duration,
        "dry_run": bool(args.dry_run),
        "before": before_stats,
        "short_marked_metadata": short_marked,
        "caption_discovery_enqueued": enqueued,
        "processed": {
            "caption_discovery": caption,
            "subtitle_download": subtitle,
            "browser_capture": browser,
        },
        "after": after_stats,
    }
    state.update({
        "last_run_at": result["ran_at"],
        "status": "running" if after_stats.get("needs_backfill", 0) else "week_drained",
        "active_week": week,
        "last_result": result,
        "start_week": args.start_week,
        "end_week": args.end_week,
    })
    save_state(state_path, state)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
