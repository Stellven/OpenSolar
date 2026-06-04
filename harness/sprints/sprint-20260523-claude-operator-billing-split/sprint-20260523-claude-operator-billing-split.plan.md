# Plan — sprint-20260523-claude-operator-billing-split

This plan details the implementation strategy for splitting Claude physical operators by their execution surface (interactive Claude Code vs. programmatic print mode) and billing pools on the Mac mini.

## Parallelization and Dependencies

The task graph defines 5 nodes with a strictly sequential dependency chain:
`N1 -> N2 -> N3 -> N4 -> N5`

- **N1 (Design & Inventory)**: Establishes the foundations and design. (Completed & Verified)
- **N2 (Schema & Registry)**: Updates schemas and migrates `/Users/lisihao/.solar/harness/config/physical-operators.json`. Depends on N1.
- **N3 (Classifier & Router)**: Implements detection logic and routing policies in `/Users/lisihao/.solar/harness/lib/operator_runtime.py` and `multi_task_runner.py`. Depends on N2.
- **N4 (Observability)**: Exposes fields in status lists and bridge JSON files (`/Users/lisihao/.solar/harness/run/monitor-bridge/global.latest.json`). Depends on N3.
- **N5 (Closeout & Report)**: Verification and final summary reports in `/Users/lisihao/.solar/harness/monitor-reports/claude-operator-billing-split.md`. Depends on N4.

## Proposed Changes and Technical Solutions

### N1: Live Claude surface inventory and billing policy design
- **Goal**: Gather live process evidence from `tmux` and `ps`, inspect wrapper scripts (`~/bin/claude`), and formulate the billing separation policy.
- **Deliverables**: 
  - [claude-operator-billing-split.md](file:///Users/lisihao/.solar/harness/docs/claude-operator-billing-split.md)
  - [sprint-20260523-claude-operator-billing-split.N1-handoff.md](file:///Users/lisihao/.solar/harness/sprints/sprint-20260523-claude-operator-billing-split.N1-handoff.md)
- **Verification**: Verify that `tmux list-panes` and `ps` can distinguish interactive processes from programmatic `claude -p` / `claude --print`. Ensure wrapper scripts do not force print mode.

### N2: Registry schema and Claude operator catalog migration
- **Goal**: Update `physical-operators.schema.json` to introduce first-class fields (`surface`, `billing_surface`, `billing_pool`, `launch_cmd_kind`, `quota_policy`) and migrate existing operators in `physical-operators.json` to explicit entries.
- **Files Modified**:
  - `~/.solar/harness/config/physical-operators.json`
  - `~/.solar/harness/config/physical-operators.schema.json`
  - `~/.solar/harness/tests/test_physical_operator_schema.py`
- **Verification**: Run `pytest tests/test_physical_operator_schema.py` to ensure schema validation fails for generic operators lacking a surface.

### N3: Runtime classifier and quota-aware routing policy
- **Goal**: Implement cmd classification logic inside a new module or extension and wire it into the task runner to prevent `claude_print` operators from being scheduled for low-value tasks (e.g. bulk edits, tests, fanouts).
- **Files Modified**:
  - `~/.solar/harness/lib/claude_surface.py`
  - `~/.solar/harness/lib/multi_task_runner.py`
  - `~/.solar/harness/tests/test_claude_surface.py`
  - `~/.solar/harness/tests/test_physical_operator_logical_selector.py`
- **Verification**: Ensure tests verify that wrappers/commands are classified properly and routing filters function correctly.

### N4: Bridge and status observability for Claude billing surfaces
- **Goal**: Expose new billing fields in tmux/status tables and the monitor bridge JSON, including process counts.
- **Files Modified**:
  - `~/.solar/harness/lib/multi_task_status.py`
  - `~/.solar/harness/tools/monitor_bridge.py`
  - `~/.solar/harness/tests/test_operator_status_observability.py`
- **Verification**: Verify fields are present in the global.latest.json and the status table outputs.

### N5: Final report and migration backlog
- **Goal**: Conduct full test suite run, verify prior handoffs, compile final report at `/Users/lisihao/.solar/harness/docs/monitor-reports/claude-operator-billing-split.md`.
- **Verification**: Ensure all tests pass and graph parent ready checks succeed.

## Risks & Mitigations
- **Quota Overruns**: High-value print operators scheduled for fanout. Mitigation: strict exclusion policy in routing logic.
- **Wrapper Confusion**: Custom wrapper scripts hiding arguments. Mitigation: recursive inspection of executable wrappers.
