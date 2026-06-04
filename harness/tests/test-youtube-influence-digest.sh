#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/Users/lisihao/Solar/harness}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
PUBLISHED_AT="$(python3 - <<'PY'
import datetime as dt
print((dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+00:00"))
PY
)"

cat > "$TMPDIR/config.yaml" <<YAML
version: 1
mac_mini_only: false
allowed_hostnames: []
output:
  raw_dir: "$TMPDIR/raw"
  state_dir: "$TMPDIR/state"
  max_videos_per_run: 10
  per_channel_limit: 2
  lookback_hours: 168
  keep_seen_days: 7
  transcript_max_chars: 20000
  browser_agent_report:
    enabled: true
    requested_model: chatgpt-5.5-thinking-high
    project_name: 杂项
    operator_script: "$TMPDIR/fake_chatgpt_report_operator.py"
    python_executable: "$(command -v python3)"
fetch:
  timeout_seconds: 1
  sleep_between_channels_seconds: 0
  sleep_between_videos_seconds: 0
channels:
  - channel_id: UC_x5XG1OV2P6uZZ5FSM9Ttw
    name: Google Developers
    category: 开发、工具与产品前沿
    priority: tier1
analysis_keywords:
  model_release: [model, launch, benchmark]
  agent: [agent, automation]
  tutorial: [tutorial, demo, build]
YAML

cat > "$TMPDIR/feed.xml" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>abc123xyz00</yt:videoId>
    <title>Build an AI agent demo with tools</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abc123xyz00"/>
    <published>${PUBLISHED_AT}</published>
  </entry>
</feed>
XML

cat > "$TMPDIR/transcript.xml" <<XML
<?xml version="1.0" encoding="utf-8"?>
<transcript>
  <text start="0" dur="2">Today we build an AI agent demo with tools.</text>
  <text start="2" dur="2">The workflow shows automation and evaluation.</text>
</transcript>
XML

cat > "$TMPDIR/fake_chatgpt_report_operator.py" <<'PY'
import json
import os
import sys
from pathlib import Path

request_dir = Path(os.environ["BROWSER_AGENT_REQUEST_DIR"])
request_dir.mkdir(parents=True, exist_ok=True)
kind = os.environ.get("CHATGPT_REPORT_OPERATOR_KIND", "")
purpose = os.environ.get("BROWSER_AGENT_PURPOSE", "")
prompt = sys.stdin.read()
(request_dir / "captured-prompt.txt").write_text(prompt, encoding="utf-8")
(request_dir / "submitted-run.json").write_text(
    json.dumps(
        {
            "task_id": f"task-{kind}",
            "conversation_id": f"conv-{kind}",
            "url": f"https://chatgpt.com/c/{kind}",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
(request_dir / "page.json").write_text(
    json.dumps(
        {
            "conversation_id": f"conv-{kind}",
            "url": f"https://chatgpt.com/c/{kind}",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
if kind == "planner":
    payload = {
        "trends": [
            {
                "title": "Agent Workflow Signals",
                "chapters": [
                    {
                        "chapter_id": "chapter-1",
                        "title": "Agent Workflow Overview",
                        "subsections": [
                            {
                                "subsection_id": "sub-1",
                                "title": "Core Evidence",
                                "evidence_refs": ["E001"],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    text = json.dumps(payload, ensure_ascii=False)
else:
    text = (
        "中心判断：Agent workflow 正在从 demo 走向可复用基础设施。"
        if "phase3" in purpose
        else "Agent Workflow Overview 正文章节。"
    )
(request_dir / "assistant-response.txt").write_text(text + "\n", encoding="utf-8")
print(text)
PY

python3 "$ROOT/scripts/youtube_influence_digest.py" \
  --config "$TMPDIR/config.yaml" \
  --fixture-feed "$TMPDIR/feed.xml" \
  --fixture-transcript "$TMPDIR/transcript.xml" \
  --force-host >/tmp/youtube-digest-test.out

test -f "$TMPDIR/raw/latest.md"
grep -q "Classified Table" "$TMPDIR/raw/latest.md"
grep -q "Build an AI agent demo with tools" "$TMPDIR/raw/latest.md"
grep -q "transcripts_ok: 1" "$TMPDIR/raw/latest.md"
find "$TMPDIR/raw" -path '*/videos/*.md' -type f | grep -q .
grep -R "Today we build an AI agent demo" "$TMPDIR/raw" >/dev/null
find "$TMPDIR/raw" -path '*/browser-agent-report/report.md' -type f | grep -q .
find "$TMPDIR/raw" -path '*/browser-agent-report/archive/archive_manifest.json' -type f | grep -q .
grep -R "Agent workflow 正在从 demo 走向可复用基础设施" "$TMPDIR/raw" >/dev/null

echo "ok: youtube influence digest fixture test passed"
