# PRD: Claude Interactive vs Programmatic Physical Operator Split

Sprint: `sprint-20260523-claude-operator-billing-split`
Priority: P0
Target: Mac mini `/Users/lisihao/.solar/harness`

## Background

The Model Fleet Operator Runtime currently models Claude operators too coarsely. Several registry entries and status panes describe `claude-code` / `claude-cli` as one surface, but Mac mini live evidence shows two materially different execution surfaces:

- interactive Claude Code panes: `tmux ... pane_current_command=claude`
- programmatic print-mode DAG workers: `claude ... -p <dispatch>`

Official Anthropic CLI docs distinguish `claude` interactive usage from `claude -p` / `--print`, where `-p` queries via SDK and exits, with programmatic output formats available. Anthropic help also says usage credits can be used for API, Workbench, and Claude Code, while Claude usage limits and billing can differ by product surface. Anthropic's Agent SDK plan article confirms the key billing split for this design: starting June 15, 2026, Agent SDK and `claude -p` usage on eligible subscription plans draws from a separate monthly Agent SDK credit, while interactive Claude Code remains on subscription usage limits. Therefore Solar must not treat interactive panes and print-mode automation as the same physical operator.

## Live Evidence From Mac Mini

Snapshot command:

```bash
tmux list-panes -a -F '#{session_name}:#{window_index}.#{pane_index} #{pane_title} #{pane_current_command} #{pane_pid}'
ps -axo pid,ppid,command | grep -E 'claude( |$)|claude -p|--print' | grep -v grep
which claude; type claude; cat ~/bin/claude 2>/dev/null
```

Observed:

- `solar-harness:1.0` runs command `claude` and is an interactive Claude Code pane.
- current DAG N4 process uses `claude --permission-mode ... -p <dispatch>`, which is programmatic print mode.
- `/opt/homebrew/bin/claude` resolves to an installed Claude binary; `~/bin/claude` wraps `/Users/lisihao/.local/bin/claude --dangerously-skip-permissions "$@"`, but does not itself force `-p`.

## Goal

Split Claude physical operators by billing and execution surface:

```yaml
op.claude.interactive.opus47.architect.01:
  surface: claude_code_interactive
  launch_cmd: claude
  billing_surface: subscription_interactive
  role: architect/debug/review

op.claude.programmatic.opus47.print.reserve.01:
  surface: claude_print
  launch_cmd: claude -p
  billing_surface: anthropic_agent_sdk_or_usage_credit
  role: batch/final_review/root_cause_debug/arch_decision
```

## Requirements

### R1 Registry schema and catalog split

Add first-class fields to Claude operators:

- `surface`: `claude_code_interactive | claude_print | claude_sdk | claude_github_action`
- `billing_surface`: `subscription_interactive | anthropic_agent_sdk_credit | usage_credit | unknown`
- `billing_pool`: logical pool id, for example `anthropic_subscription_interactive` or `anthropic_agent_sdk_credit`
- `launch_cmd_kind`: `interactive_repl | print_once | sdk_call`
- `quota_policy`: monthly/rolling/observed, reserve and fallback rules

Existing Claude operators must be migrated into explicit interactive or programmatic entries. No entry may remain as generic `tool: claude-code` without a surface.

### R2 Runtime detection

Add or extend detection to classify active Claude processes:

- `claude` without `-p` / `--print`: interactive
- `claude -p` or `claude --print`: programmatic print
- wrapper scripts must be inspected enough to detect whether they force `-p`
- tmux pane title/status must expose the surface and billing pool

### R3 Quota broker and routing policy

Programmatic Claude print operators are scarce reserve operators:

```yaml
use_for:
  - FINAL_REVIEW
  - ROOT_CAUSE_DEBUG
  - ARCH_DECISION
  - SMALL_HIGH_VALUE_BATCH
avoid_for:
  - FANOUT
  - BULK_EDIT
  - TEST_RUN
  - LOW_VALUE_SCAN
```

Interactive Claude operators remain suited for deep human-in-the-loop architecture/debug/review. DAG nodes must choose by logical operator class and billing constraints, not by raw model string.

### R4 Status and bridge observability

`solar-harness multi-task status` and `run/monitor-bridge/global.latest.json` must show:

- operator id
- provider/vendor/model
- `surface`
- `billing_surface`
- `billing_pool`
- runtime command classification
- observed `claude -p` process count
- reserve policy and current availability

### R5 Tests and safety

Tests must use fixtures, not real billing calls. Required coverage:

- classify interactive `claude`
- classify `claude -p`
- classify `claude --print`
- classify wrapper that does not force `-p`
- registry validation rejects generic Claude operators with missing `surface`
- routing policy keeps programmatic Claude out of fanout/bulk/test/low-value tasks
- bridge/status exposes `surface` and `billing_surface`

## Non-goals

- Do not attempt to spend or verify real Agent SDK credits in tests.
- Do not change active user interactive panes.
- Do not kill existing Claude or tmux processes.
- Do not print secrets, tokens, cookies, or raw auth state.
- Do not assume a dollar amount in code; make monthly credit configurable and observed.

## Acceptance

- A report exists at `/Users/lisihao/.solar/harness/monitor-reports/claude-operator-billing-split.md`.
- Registry contains separate interactive and programmatic Claude operator examples.
- Runtime classifier correctly reports the live Mac mini process split.
- Routing tests prove `claude_print` reserve operators are not selected for low-value fanout/bulk/test work.
- Bridge/status output includes billing surface fields.

## Source Notes

- Anthropic CLI docs: `claude` starts interactive mode; `claude -p` / `--print` runs print/programmatic mode and can emit JSON/stream JSON for automation.
- Anthropic Agent SDK docs: Agent SDK supports production automation and notes that Agent SDK and `claude -p` on subscription plans draw from a separate monthly Agent SDK credit starting June 15, 2026.
- Anthropic help center: the separate Agent SDK monthly credit covers Agent SDK, `claude -p`, GitHub Actions, and Agent SDK-authenticated third-party apps; it does not cover interactive Claude Code terminal/IDE usage. The same page lists current plan amounts including Pro `$20`, Max 5x `$100`, and Max 20x `$200`.
- Anthropic help center: usage credits can apply to API, Workbench, and Claude Code; usage limits and pay-as-you-go behavior are product-surface dependent. Treat exact plan credit amounts as configurable policy, not hard-coded routing logic.
