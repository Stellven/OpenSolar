#!/usr/bin/env python3
"""Collect new YouTube videos, transcripts, and raw Markdown for knowledge ingest.

The job is config-driven and local-only. It can monitor public YouTube channels
without OAuth by using the official channel RSS feed, then extracting caption
tracks from the public watch page when transcripts are available.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import platform
import re
import socket
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    import requests
except Exception as exc:  # pragma: no cover
    print(f"ERROR: requests is required: {exc}", file=sys.stderr)
    raise SystemExit(2)

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"ERROR: PyYAML is required: {exc}", file=sys.stderr)
    raise SystemExit(2)


UTC = dt.timezone.utc


@dataclasses.dataclass
class Channel:
    channel_id: str
    name: str
    category: str
    url: str
    priority: str = "rotation"


@dataclasses.dataclass
class Video:
    video_id: str
    channel_id: str
    channel_name: str
    category: str
    priority: str
    title: str
    url: str
    published_at: str
    fetched_at: str
    source: str
    transcript: str
    transcript_status: str
    transcript_source: str
    summary: str
    signal_type: str
    impact: str
    score: int
    why_it_matters: str


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC).replace(microsecond=0)


def iso_z(value: dt.datetime | None = None) -> str:
    value = value or now_utc()
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    value = value.strip()
    for parser in (
        lambda s: email.utils.parsedate_to_datetime(s),
        lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")),
    ):
        try:
            parsed = parser(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            pass
    return None


def strip_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def slugify(text: str, max_len: int = 80) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-._")
    return (text[:max_len] or "video").lower()


def stable_id(video_id: str, title: str, published_at: str) -> str:
    payload = "\n".join([video_id.strip(), title.strip(), published_at[:10]])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def assert_mac_mini(config: dict[str, Any], force: bool = False) -> None:
    if force or not config.get("mac_mini_only", True):
        return
    hostnames = {socket.gethostname(), platform.node()}
    try:
        hostnames.add(socket.getfqdn())
    except Exception:
        pass
    allowed = set(config.get("allowed_hostnames") or [])
    if not (hostnames & allowed):
        print(
            "skip: this job is Mac-mini-only; "
            f"host={sorted(hostnames)} allowed={sorted(allowed)}",
            file=sys.stderr,
        )
        raise SystemExit(0)


def load_seen(state_dir: Path, keep_days: int) -> dict[str, str]:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "seen.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    cutoff = now_utc() - dt.timedelta(days=keep_days)
    kept: dict[str, str] = {}
    for key, ts in data.items():
        parsed = parse_time(ts)
        if parsed and parsed >= cutoff:
            kept[key] = ts
    return kept


def save_seen(state_dir: Path, seen: dict[str, str]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / "seen.json.tmp"
    tmp.write_text(json.dumps(seen, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(state_dir / "seen.json")


def request_text(session: requests.Session, url: str, timeout: int, user_agent: str) -> str | None:
    try:
        res = session.get(url, timeout=timeout, headers={"User-Agent": user_agent})
        if res.status_code >= 400:
            return None
        return res.text
    except Exception:
        return None


def xml_text(node: ET.Element, names: list[str]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return found.text.strip()
        found = node.find(f"{{*}}{name}")
        if found is not None and found.text:
            return found.text.strip()
    return ""


def canonical_channel_id(value: str) -> str:
    value = value.strip()
    match = re.search(r"(UC[0-9A-Za-z_-]{20,})", value)
    return match.group(1) if match else ""


def resolve_channel_id(session: requests.Session, value: str, timeout: int, user_agent: str) -> tuple[str, str]:
    """Resolve UC channel id from a channel id, handle, or public channel URL."""
    direct = canonical_channel_id(value)
    if direct:
        return direct, value
    raw = value.strip()
    if not raw:
        return "", ""
    if raw.startswith("@"):
        url = f"https://www.youtube.com/{raw}"
    elif raw.startswith("http://") or raw.startswith("https://"):
        url = raw
    elif "/" in raw:
        url = "https://www.youtube.com/" + raw.lstrip("/")
    else:
        url = f"https://www.youtube.com/@{raw}"
    page = request_text(session, url, timeout, user_agent) or ""
    for pattern in (
        r'"channelId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"',
        r'<meta itemprop="channelId" content="(UC[0-9A-Za-z_-]{20,})"',
        r'"externalId"\s*:\s*"(UC[0-9A-Za-z_-]{20,})"',
    ):
        match = re.search(pattern, page)
        if match:
            return match.group(1), url
    return "", url


def flatten_channels(config: dict[str, Any], session: requests.Session | None = None) -> list[Channel]:
    fetch_cfg = config.get("fetch", {})
    timeout = int(fetch_cfg.get("timeout_seconds", 15))
    user_agent = fetch_cfg.get("user_agent", "Solar-YouTube-Influence-Digest/1.0")
    session = session or requests.Session()
    channels: list[Channel] = []
    seen: set[str] = set()
    for raw in config.get("channels") or []:
        if isinstance(raw, str):
            entry = {"url": raw}
        elif isinstance(raw, dict):
            entry = raw
        else:
            continue
        source_value = str(entry.get("channel_id") or entry.get("url") or entry.get("handle") or "").strip()
        channel_id = canonical_channel_id(source_value)
        resolved_url = str(entry.get("url") or source_value)
        if not channel_id and source_value:
            channel_id, resolved_url = resolve_channel_id(session, source_value, timeout, user_agent)
        if not channel_id or channel_id in seen:
            continue
        seen.add(channel_id)
        name = str(entry.get("name") or entry.get("handle") or channel_id).strip().lstrip("@")
        channels.append(
            Channel(
                channel_id=channel_id,
                name=name or channel_id,
                category=str(entry.get("category") or "未分类"),
                url=resolved_url or f"https://www.youtube.com/channel/{channel_id}",
                priority=str(entry.get("priority") or "rotation"),
            )
        )
    return channels


def parse_channel_feed(channel: Channel, xml: str, source: str, fetched_at: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml.encode("utf-8"))
    except Exception:
        return []
    entries = root.findall(".//{*}entry")
    videos: list[dict[str, str]] = []
    for entry in entries:
        video_id = xml_text(entry, ["videoId"])
        if not video_id:
            found = entry.find("{*}videoId")
            if found is not None and found.text:
                video_id = found.text.strip()
        title = strip_text(xml_text(entry, ["title"]))
        published = parse_time(xml_text(entry, ["published", "updated"]))
        link = ""
        link_node = entry.find("{*}link")
        if link_node is not None:
            link = link_node.attrib.get("href", "")
        if not link and video_id:
            link = f"https://www.youtube.com/watch?v={video_id}"
        if not video_id or not title:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "url": link,
                "published_at": iso_z(published) if published else fetched_at,
                "source": source,
                "channel_id": channel.channel_id,
                "channel_name": channel.name,
                "category": channel.category,
                "priority": channel.priority,
            }
        )
    return videos


def extract_json_object(text: str, marker: str) -> dict[str, Any] | None:
    idx = text.find(marker)
    if idx < 0:
        return None
    start = text.find("{", idx)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for pos in range(start, len(text)):
        ch = text[pos]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : pos + 1])
                except Exception:
                    return None
    return None


def caption_tracks_from_watch_page(page: str) -> list[dict[str, Any]]:
    data = extract_json_object(page, "ytInitialPlayerResponse")
    if not data:
        return []
    captions = data.get("captions") or {}
    renderer = captions.get("playerCaptionsTracklistRenderer") or {}
    tracks = renderer.get("captionTracks") or []
    return [track for track in tracks if isinstance(track, dict) and track.get("baseUrl")]


def parse_transcript_payload(text: str) -> str:
    stripped = text.lstrip()
    parts: list[str] = []
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(text)
            events = data.get("events", []) if isinstance(data, dict) else data
            for event in events:
                for seg in event.get("segs", []) if isinstance(event, dict) else []:
                    parts.append(str(seg.get("utf8", "")))
        except Exception:
            pass
    if not parts:
        try:
            root = ET.fromstring(text.encode("utf-8"))
            for node in root.findall(".//text"):
                if node.text:
                    parts.append(node.text)
            for node in root.findall(".//{*}text"):
                if node.text:
                    parts.append(node.text)
        except Exception:
            pass
    return strip_text(" ".join(parts))


def fetch_transcript(
    session: requests.Session,
    video_id: str,
    timeout: int,
    user_agent: str,
    fixture_transcript: str = "",
    fixture_watch: str = "",
) -> tuple[str, str, str]:
    if fixture_transcript:
        text = Path(fixture_transcript).read_text(encoding="utf-8")
        transcript = parse_transcript_payload(text)
        return transcript, "ok" if transcript else "empty", f"fixture:{fixture_transcript}"
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    page = Path(fixture_watch).read_text(encoding="utf-8") if fixture_watch else request_text(session, watch_url, timeout, user_agent)
    if not page:
        return "", "watch_page_unavailable", watch_url
    tracks = caption_tracks_from_watch_page(page)
    if not tracks:
        return "", "no_caption_tracks", watch_url
    # Prefer manually authored or English tracks, then fall back to first caption.
    def rank(track: dict[str, Any]) -> tuple[int, int]:
        lang = str(track.get("languageCode") or "").lower()
        kind = str(track.get("kind") or "").lower()
        return (0 if lang.startswith("en") or lang.startswith("zh") else 1, 1 if kind == "asr" else 0)

    for track in sorted(tracks, key=rank):
        base = str(track.get("baseUrl"))
        transcript_url = base + ("&fmt=json3" if "fmt=" not in base else "")
        payload = request_text(session, transcript_url, timeout, user_agent)
        if not payload:
            continue
        transcript = parse_transcript_payload(payload)
        if transcript:
            return transcript, "ok", transcript_url
    return "", "caption_fetch_failed", watch_url


CURRENT_CONFIG: dict[str, Any] = {}


def score_signal(text: str, config: dict[str, Any], priority: str) -> tuple[str, str, int]:
    lower = text.lower()
    keywords = config.get("analysis_keywords") or {}
    type_scores: dict[str, int] = {}
    for signal_type, words in keywords.items():
        type_scores[signal_type] = sum(1 for word in words if str(word).lower() in lower)
    signal_type = max(type_scores, key=type_scores.get) if type_scores else "other"
    score = type_scores.get(signal_type, 0)
    score += 2 if priority in {"tier1", "must_scan", "high"} else 0
    score += 2 if re.search(r"\b(release|launch|paper|benchmark|agent|model|gpu|tutorial|demo)\b", lower) else 0
    impact = "high" if score >= 6 else "medium" if score >= 3 else "low"
    return signal_type, impact, score


def summarize_text(text: str, title: str) -> str:
    clean = strip_text(text)
    if not clean:
        return title[:260]
    sentences = re.split(r"(?<=[.!?。！？])\s+", clean)
    summary = " ".join(s for s in sentences[:4] if s).strip()
    return (summary or clean[:800])[:1200]


def why_it_matters(signal_type: str, impact: str, category: str) -> str:
    base = {
        "model_release": "可能改变模型能力、API 生态或应用构建路线。",
        "research": "可能提供新方法、新基准或底层机制线索。",
        "agent": "可能影响自动化、AI 编程和工具调用工作流。",
        "compute": "可能影响算力供给、成本曲线或硬件路线。",
        "product": "可能代表产品化、用户增长或开发者体验变化。",
        "tutorial": "可提炼为操作方法、工具链实践或学习材料。",
        "market": "可能影响商业化节奏、资本预期或行业格局。",
    }.get(signal_type, "可能是该频道值得跟踪的新信号。")
    return f"{impact.upper()}：{category} 方向视频信号。{base}"


def build_video(meta: dict[str, str], transcript: str, status: str, source: str, config: dict[str, Any]) -> Video:
    title = meta["title"]
    summary = summarize_text(transcript, title)
    signal_type, impact, score = score_signal(f"{title} {summary}", config, meta.get("priority", "rotation"))
    max_chars = int((config.get("output") or {}).get("transcript_max_chars", 60000))
    return Video(
        video_id=meta["video_id"],
        channel_id=meta["channel_id"],
        channel_name=meta["channel_name"],
        category=meta["category"],
        priority=meta.get("priority", "rotation"),
        title=title,
        url=meta["url"],
        published_at=meta["published_at"],
        fetched_at=meta.get("fetched_at", iso_z()),
        source=meta["source"],
        transcript=transcript[:max_chars],
        transcript_status=status,
        transcript_source=source,
        summary=summary,
        signal_type=signal_type,
        impact=impact,
        score=score,
        why_it_matters=why_it_matters(signal_type, impact, meta["category"]),
    )


def collect_channel(
    session: requests.Session,
    channel: Channel,
    config: dict[str, Any],
    fetched_at: str,
    fixture_feed: str = "",
) -> list[dict[str, str]]:
    fetch_cfg = config.get("fetch", {})
    timeout = int(fetch_cfg.get("timeout_seconds", 15))
    user_agent = fetch_cfg.get("user_agent", "Solar-YouTube-Influence-Digest/1.0")
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={urllib.parse.quote(channel.channel_id)}"
    xml = Path(fixture_feed).read_text(encoding="utf-8") if fixture_feed else request_text(session, feed_url, timeout, user_agent)
    if not xml:
        return []
    videos = parse_channel_feed(channel, xml, feed_url if not fixture_feed else f"fixture:{fixture_feed}", fetched_at)
    for video in videos:
        video["fetched_at"] = fetched_at
    return videos


def filter_video_meta(items: list[dict[str, str]], seen: dict[str, str], config: dict[str, Any]) -> list[dict[str, str]]:
    out_cfg = config.get("output", {})
    cutoff = now_utc() - dt.timedelta(hours=int(out_cfg.get("lookback_hours", 72)))
    per_channel_limit = int(out_cfg.get("per_channel_limit", 3))
    max_videos = int(out_cfg.get("max_videos_per_run", 30))
    by_channel: dict[str, int] = {}
    selected: list[dict[str, str]] = []
    for item in sorted(items, key=lambda x: x.get("published_at", ""), reverse=True):
        if item["video_id"] in seen:
            continue
        published = parse_time(item.get("published_at"))
        if published and published < cutoff:
            continue
        count = by_channel.get(item["channel_id"], 0)
        if count >= per_channel_limit:
            continue
        selected.append(item)
        by_channel[item["channel_id"]] = count + 1
        if len(selected) >= max_videos:
            break
    return selected


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_markdown(videos: list[Video], channels: list[Channel], config: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    out_cfg = config.get("output", {})
    raw_dir = Path(out_cfg.get("raw_dir", str(Path.home() / "Knowledge/_raw/youtube-influence-digest"))).expanduser()
    current = now_utc()
    run_id = current.strftime("%Y%m%dT%H%M%SZ")
    run_dir = raw_dir / current.strftime("%Y/%m/%d") / run_id
    items_dir = run_dir / "videos"
    if not dry_run:
        items_dir.mkdir(parents=True, exist_ok=True)

    transcript_ok = sum(1 for video in videos if video.transcript_status == "ok")
    title = f"YouTube Influence Transcript Digest — {run_id}"
    lines = [
        "---",
        f"title: {title}",
        "source: youtube-influence-digest",
        f"created_at: {iso_z()}",
        f"channels_total: {len(channels)}",
        f"videos_collected: {len(videos)}",
        f"transcripts_ok: {transcript_ok}",
        "raw_ingest: true",
        "---",
        "",
        f"# {title}",
        "",
        "## Run Summary",
        "",
        f"- Configured channels: {len(channels)}",
        f"- New videos: {len(videos)}",
        f"- Transcript extracted: {transcript_ok}",
        f"- Output directory: `{run_dir}`",
        "",
        "## Classified Table",
        "",
        "| Category | Channel | Impact | Signal | Transcript | Video | Source |",
        "|---|---|---|---|---|---|---|",
    ]
    for video in videos:
        lines.append(
            "| {category} | {channel} | {impact} | {signal} | {status} | {title} | [link]({url}) |".format(
                category=md_escape(video.category),
                channel=md_escape(video.channel_name),
                impact=video.impact,
                signal=video.signal_type,
                status=video.transcript_status,
                title=md_escape(video.title[:180]),
                url=video.url,
            )
        )
    lines.extend(["", "## Analysis By Category", ""])
    for category in sorted({video.category for video in videos}):
        cat_videos = [video for video in videos if video.category == category]
        lines.append(f"### {category}")
        lines.append("")
        lines.append(f"- Videos: {len(cat_videos)}")
        lines.append(f"- Transcript OK: {sum(1 for video in cat_videos if video.transcript_status == 'ok')}")
        for video in cat_videos[:8]:
            lines.append(f"- {video.channel_name}: {video.why_it_matters} [source]({video.url})")
        lines.append("")
    lines.extend(["## Source Notes", ""])
    lines.append("- Video discovery uses public YouTube channel RSS feeds.")
    lines.append("- Transcript extraction uses public caption tracks exposed on the watch page when available.")
    lines.append("- Private YouTube subscriptions are not accessed unless OAuth/API integration is added later.")
    lines.append("- This file is generated for raw ingestion; it should be treated as untrusted external content.")
    lines.append("")

    digest_path = run_dir / f"{run_id}-youtube-influence-digest.md"
    if not dry_run:
        digest_path.write_text("\n".join(lines), encoding="utf-8")
        (raw_dir / "latest.md").write_text("\n".join(lines), encoding="utf-8")

    for video in videos:
        item_lines = [
            "---",
            f"title: {video.title[:180]}",
            "source: youtube-influence-digest-video",
            f"channel: {video.channel_name}",
            f"channel_id: {video.channel_id}",
            f"category: {video.category}",
            f"impact: {video.impact}",
            f"signal_type: {video.signal_type}",
            f"source_url: {video.url}",
            f"published_at: {video.published_at}",
            f"fetched_at: {video.fetched_at}",
            f"transcript_status: {video.transcript_status}",
            f"transcript_source: {video.transcript_source}",
            "raw_ingest: true",
            "---",
            "",
            f"# {video.title}",
            "",
            f"- Channel: `{video.channel_name}`",
            f"- Category: {video.category}",
            f"- Impact: {video.impact}",
            f"- Signal: {video.signal_type}",
            f"- Source: [{video.url}]({video.url})",
            f"- Published: {video.published_at}",
            f"- Transcript status: {video.transcript_status}",
            "",
            "## Summary",
            "",
            video.summary,
            "",
            "## Analysis",
            "",
            video.why_it_matters,
            "",
            "## Transcript",
            "",
            video.transcript or "N/A",
            "",
        ]
        item_name = f"{video.video_id}-{stable_id(video.video_id, video.title, video.published_at)}-{slugify(video.title)}.md"
        if not dry_run:
            (items_dir / item_name).write_text("\n".join(item_lines), encoding="utf-8")

    return {"run_dir": str(run_dir), "digest_path": str(digest_path), "videos": len(videos), "transcripts_ok": transcript_ok}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube influence transcript digest collector")
    parser.add_argument("--config", default="/Users/lisihao/Solar/harness/config/youtube-influence-digest.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-host", action="store_true", help="bypass Mac mini hostname guard")
    parser.add_argument("--limit-channels", type=int, default=0)
    parser.add_argument("--fixture-feed", default="", help="test-only YouTube channel feed file")
    parser.add_argument("--fixture-transcript", default="", help="test-only transcript payload used for every video")
    parser.add_argument("--fixture-watch", default="", help="test-only watch page used for every video")
    return parser


def main(argv: list[str] | None = None) -> int:
    global CURRENT_CONFIG
    args = build_arg_parser().parse_args(argv)
    config = load_config(Path(args.config))
    CURRENT_CONFIG = config
    assert_mac_mini(config, force=args.force_host)

    out_cfg = config.get("output", {})
    state_dir = Path(out_cfg.get("state_dir", "/Users/lisihao/.solar/harness/state/youtube-influence-digest")).expanduser()
    seen = load_seen(state_dir, int(out_cfg.get("keep_seen_days", 45)))
    fetched_at = iso_z()
    session = requests.Session()
    channels = flatten_channels(config, session=session)
    if args.limit_channels:
        channels = channels[: args.limit_channels]

    all_meta: list[dict[str, str]] = []
    failures: list[str] = []
    sleep_channel = float((config.get("fetch") or {}).get("sleep_between_channels_seconds", 0.4))
    for channel in channels:
        try:
            all_meta.extend(collect_channel(session, channel, config, fetched_at, fixture_feed=args.fixture_feed))
        except Exception as exc:
            failures.append(f"{channel.name}: {exc}")
        if sleep_channel > 0 and not args.fixture_feed:
            time.sleep(sleep_channel)

    selected_meta = filter_video_meta(all_meta, seen, config)
    videos: list[Video] = []
    timeout = int((config.get("fetch") or {}).get("timeout_seconds", 15))
    user_agent = (config.get("fetch") or {}).get("user_agent", "Solar-YouTube-Influence-Digest/1.0")
    sleep_video = float((config.get("fetch") or {}).get("sleep_between_videos_seconds", 0.5))
    for meta in selected_meta:
        try:
            transcript, status, transcript_source = fetch_transcript(
                session,
                meta["video_id"],
                timeout,
                user_agent,
                fixture_transcript=args.fixture_transcript,
                fixture_watch=args.fixture_watch,
            )
            videos.append(build_video(meta, transcript, status, transcript_source, config))
        except Exception as exc:
            meta["fetched_at"] = fetched_at
            videos.append(build_video(meta, "", f"error:{exc}", "", config))
        if sleep_video > 0 and not args.fixture_transcript and not args.fixture_watch:
            time.sleep(sleep_video)

    result = write_markdown(videos, channels, config, dry_run=args.dry_run)
    if not args.dry_run:
        for video in videos:
            seen[video.video_id] = fetched_at
        save_seen(state_dir, seen)
        log_path = state_dir / "runs.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": fetched_at, **result, "failures": failures[:20]}, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, **result, "channels_total": len(channels), "failures": failures[:20]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
