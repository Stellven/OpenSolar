# Handoff — Professor-Grade DeepResearch Survey MVP + Writing Loop

## Status

Implementation complete. The sprint is ready for evaluator review.

2026-05-15 update: added deterministic section writing/review/revision loop and batch section runner. The implementation is no longer only AST/evidence-pack scaffolding; every ready section can now produce `draft.md`, `review.json`, `revision_trace.json`, and `final.md` through an artifact-backed loop.

## 变更文件列表 (Changes / Files)

新增 / 修改的代码与测试位于以下路径（package-first 布局）：

- `harness/lib/research/survey/` — 全新 survey 模块根包
  - `schemas.py` — 带 `schema_version` 的 survey dataclasses
  - `planner.py` — survey planner（`target_chars=50000` → 8 章 / 32 节）
  - `evidence_pack.py` — per-section evidence pack builder（复用 sources / evidence / claims ledgers）
  - `writing_loop.py` — section writer / reviewer / reviser loop（新增）
  - `section_compiler.py` — section compiler（blocked-pack enforcement + writing loop adapter）
  - `evaluator.py` — professor-grade survey evaluator（5-section brief 与 plan-only 输出会被判 FAIL）
- `harness/cli/` 下新增 CLI adapter：
  - `survey-plan`
  - `survey-pack`
  - `survey-write-section`
  - `survey-run-sections`
  - `survey-review`
  - `survey-compile`
  - `survey-eval`
- `harness/tests/research_survey/` — 新增测试套件覆盖上述模块

## Done 条件达成证据

合约 Done 条件逐条核对：

1. **Survey-native package 落地** ✅ — `harness/lib/research/survey/` 6 个模块全部就位，dataclasses 带 `schema_version` 支持后续迁移。
2. **Planner 产出 8 章 / 32 节** ✅ — `survey-plan` CLI smoke 输出 `8 chapters / 32 sections`（见下方"验证方法"）。
3. **Evidence pack 可复用现有 ledger** ✅ — `survey-pack` 从 sources / evidence / claims ledgers 构出 ready pack。
4. **Section compiler 强制 blocked-pack 校验** ✅ — `section_compiler.py` 含 blocked-pack enforcement；`survey-write-section` finalized sections。
4.1. **Section 写作/审稿/修订闭环** ✅ — `writing_loop.py` 会根据 `section.spec.json` + `evidence_pack.json` 生成草稿、审稿、最多多轮修订，并写出 `revision_trace.json`。
5. **Professor-grade evaluator 拒绝低质输出** ✅ — Plan-only strict smoke：`survey-eval --strict` 返回 FAIL 并报 `evidence_packs_missing` + `finalized_sections_low:0<3`。
6. **CLI 7 个适配器全部可调用** ✅ — `survey-plan / survey-pack / survey-write-section / survey-run-sections / survey-review / survey-compile / survey-eval` 全部接通。
7. **测试套件完整** ✅ — `68 passed`（runtime harness）+ `68 passed`（source repo harness）双路径一致。
8. **既有 CLI 兼容性** ✅ — `research run` / `handoff-search` / `import-search` / `source-audit` / `eval-artifacts` 路径未改动（package-first 增量，非破坏）。

## 验证方法 (Verify)

Runtime harness:

```bash
python3 -m pytest -q \
  /Users/sihaoli/.solar/harness/tests/research_survey \
  /Users/sihaoli/.solar/harness/tests/research_unit/test_cli.py \
  /Users/sihaoli/.solar/harness/tests/research_unit/test_evaluator.py \
  /Users/sihaoli/.solar/harness/tests/research_unit/test_cli_claim_quality.py \
  /Users/sihaoli/.solar/harness/tests/research_unit/test_cli_synthesize.py \
  /Users/sihaoli/.solar/harness/tests/graph/test_graph_dispatch_submit.py
```

Result: `68 passed in 0.61s`

Source repo harness:

```bash
HARNESS_DIR=/Users/sihaoli/Solar/harness python3 -m pytest -q \
  /Users/sihaoli/Solar/harness/tests/research_survey \
  /Users/sihaoli/Solar/harness/tests/research_unit/test_cli.py \
  /Users/sihaoli/Solar/harness/tests/research_unit/test_evaluator.py \
  /Users/sihaoli/Solar/harness/tests/research_unit/test_cli_claim_quality.py \
  /Users/sihaoli/Solar/harness/tests/research_unit/test_cli_synthesize.py \
  /Users/sihaoli/Solar/harness/tests/graph/test_graph_dispatch_submit.py
```

Result: `68 passed in 0.80s`

Strong CLI smoke:

- `survey-plan` created `8 chapters / 32 sections`.
- `survey-pack` built ready evidence packs from existing latent reasoning ledgers.
- `survey-run-sections --limit 3` finalized 3 sections through revision loops.
- `survey-compile` wrote final survey shell.
- `survey-eval --strict` returned `PASS`.

Plan-only strict smoke:

- `survey-plan` alone followed by `survey-eval --strict` returns FAIL with `evidence_packs_missing` and `finalized_sections_low:0<3`.

## Remaining Limitations

- The loop is deterministic MVP; it establishes artifact contracts and failure gates, but a true professor-grade prose layer still needs LLM/expert writer implementation.
- Full 5-10 万字 generation now has a section production loop, but still needs chapter-level editorial synthesis and cross-chapter contradiction review.
