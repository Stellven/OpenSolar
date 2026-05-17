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

if grep -Fq '标 `未验证` 或 `风险`' "$COORD"; then
  fail "raw DoD backtick spans would execute as shell commands in generate_dispatch"
fi

ok "coordinator dispatch heredoc escapes DoD backticks"
