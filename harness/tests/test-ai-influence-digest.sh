#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/Users/lisihao/Solar/harness}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cat > "$TMPDIR/config.yaml" <<YAML
version: 1
mac_mini_only: false
allowed_hostnames: []
output:
  raw_dir: "$TMPDIR/raw"
  state_dir: "$TMPDIR/state"
  max_items_per_run: 10
  per_account_limit: 2
  lookback_hours: 72
  keep_seen_days: 7
fetch:
  timeout_seconds: 1
  rss_templates: []
  duckduckgo_enabled: false
tier1_accounts: [sama]
categories:
  - name: 核心领袖与技术大神
    accounts: [sama]
analysis_keywords:
  model_release: [launch, released, model, benchmark]
  research: [paper, arxiv, reasoning]
  compute: [gpu, chip]
YAML

cat > "$TMPDIR/feed.xml" <<XML
<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>fixture</title>
    <item>
      <title>New model launch with benchmark results</title>
      <link>https://x.com/sama/status/1</link>
      <pubDate>Sun, 10 May 2026 12:00:00 GMT</pubDate>
      <description>Released a model and benchmark details.</description>
    </item>
  </channel>
</rss>
XML

python3 "$ROOT/scripts/ai_influence_digest.py" \
  --config "$TMPDIR/config.yaml" \
  --fixture-rss "$TMPDIR/feed.xml" \
  --force-host >/tmp/ai-digest-test.out

test -f "$TMPDIR/raw/latest.md"
grep -q "Classified Table" "$TMPDIR/raw/latest.md"
grep -q "https://x.com/sama/status/1" "$TMPDIR/raw/latest.md"
find "$TMPDIR/raw" -path '*/items/*.md' -type f | grep -q .

echo "ok: ai influence digest fixture test passed"
