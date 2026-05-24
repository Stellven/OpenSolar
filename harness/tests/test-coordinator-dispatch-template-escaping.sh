#!/usr/bin/env bash
# Regression: dispatch heredoc must not execute Markdown backtick spans.
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
COORD="$HARNESS_DIR/coordinator.sh"

fail() { echo "FAIL: $*" >&2; exit 1; }
ok() { echo "PASS: $*"; }

bash -n "$COORD" || fail "coordinator.sh syntax"
grep -Fq '标 \`未验证\` 或 \`风险\`' "$COORD" \
  || fail "DoD backtick spans are not escaped inside generate_dispatch heredoc"
grep -Fq '\`prd.html\` 和后续 \`planning.html\`' "$COORD" \
  || fail "PM HTML artifact backtick spans are not escaped"
grep -Fq '\`planning.html\` 必须和 PM 侧 \`prd.html\`' "$COORD" \
  || fail "Planner HTML artifact backtick spans are not escaped"

if grep -Fq '标 `未验证` 或 `风险`' "$COORD"; then
  fail "raw DoD backtick spans would execute as shell commands in generate_dispatch"
fi
if grep -Fq '   `prd.html` 和后续 `planning.html`' "$COORD"; then
  fail "raw PM HTML artifact backticks would execute as shell commands"
fi
if grep -Fq '   `planning.html` 必须和 PM 侧 `prd.html`' "$COORD"; then
  fail "raw Planner HTML artifact backticks would execute as shell commands"
fi

ok "coordinator dispatch heredoc escapes DoD backticks"
