# Plan — S05 Verification-Release (KVTC 接入质量修复 / 末尾切片)

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release`
slice: `verification-release`
gate: `G_S05_verification_release_passed`
knowledge_context: solar-harness context inject used (mirage degraded → qmd/obsidian/solar_db fallback)

## 0. 本切片定位

末尾切片：S01..S04 已 passed。本 sprint 只交付 CI gate + 回归证据 + 发布文档，让父 epic `parent-check` 可通过。**禁止触碰 src/omlx 任何代码**，全部写范围限于 `scripts/`、`tests/`、`.github/workflows/`、`reports/`、`docs/`、本 sprint 自身 artifact。

## 1. DAG 与并行边界

```
D0 (CLI 升级)
  ├── D1 (15 cells fixtures)
  ├── D2 (e2e tests)
  └── D3 (CI workflow)
        └── D4 (smoke run evidence) [join 3 → 1]
              └── D5 (release docs)
                    └── D6 (handoff + traceability + epic close prep)
```

**并行批次**：

| 批次 | 节点 | 说明 |
|------|------|------|
| Wave 1 | `D0_ab_correctness_cli_upgrade` | 唯一根节点，必须先 PASS |
| Wave 2 (并行) | `D1_fixtures_15_cells` · `D2_e2e_tests` · `D3_ci_workflow` | 三者 write_scope 完全不重叠（scripts/tests/.github），可同批派发给 3 个 builder |
| Wave 3 (join) | `D4_smoke_run_evidence` | 必须等 D1+D2+D3 全 passed；S05 唯一允许真跑节点 |
| Wave 4 | `D5_release_docs` | 引用 D4 reports 路径 |
| Wave 5 | `D6_handoff_traceability_epic_close_prep` | 聚合全部，输出 epic close prep |

**write_scope 冲突说明**：D1/D2/D3 路径互斥（`scripts/fetch_kvtc_fixtures.sh`+`tests/fixtures/kvtc/**` vs `tests/regression/test_kvtc_e2e.py` vs `.github/workflows/kvtc-regression.yml`），无需串行。D4 唯一写 `reports/kvtc-ab/<ts>/`，D5 唯一写 `docs/KVTC_RELEASE.md`，D6 唯一写本 sprint handoff/traceability。

## 2. 每节点验收 gate（hard，禁止放宽）

- **D0**：5 个新 CLI flags 全到位、退出码 0/1/2/3 正确、`from omlx.cache.kvtc_recon_gate import evaluate` 可导入、summary.json schema_version=`kvtc.ab_summary.v1`、recon_gate.jsonl 14 字段全、旧 CLI 兼容。
- **D1**：`tests/fixtures/kvtc/manifest.json` 含 ≥15 fixture entries、stable-ci ≥12 / local-only ≤3、每 fixture 11 字段全、numpy seed 固定、每 .npz ≤100 MB、`fetch_kvtc_fixtures.sh` 可执行。
- **D2**：`tests/regression/test_kvtc_e2e.py` 含 ≥8 e2e cases、`./venv/bin/python -m pytest tests/regression/ -v` 全 PASSED、CPU ≤60s、TestClient 不真起 uvicorn。
- **D3**：`.github/workflows/kvtc-regression.yml` 含 pre-merge + nightly 两 job、hard SLO FAIL→issue `kvtc-regression`、soft SLO WARN→issue `kvtc-watchlist`、记录 `atlas.kvtc.recon_gate_repair` hook 名。
- **D4** (S05 唯一真跑节点)：退出码 0、`reports/kvtc-ab/<ts>/` 全套 artifact 存在、summary.json `hard_violations=0`、`kvtc_accept` 子集 `min_cos ≥ 0.999`、每 fixture 实际 decision = manifest expect_decision、per_fixture/*.json ≥15 个。
- **D5**：`docs/KVTC_RELEASE.md` 含 R1..R7 状态、D4 evidence 路径与关键数字、rollback 4 个 env 全集、ATLAS hook 名、OQ1/OQ2 未闭环项、**禁止乐观词「已修复 / 稳定 / 完美 / 无需担忧」**。
- **D6**：handoff.md + traceability.json 齐全、traceability 含 12 字段（schema_version / R1..R7 / OQ1..OQ4 / N1-E1..N7-E6 ≥30 evidence / S01..S05 gate status / parent_check_ready=true / files_touched / smoke_run_evidence_paths / builder_forbidden_aggregate / generated_at / knowledge_context）。

## 3. 模型路由

| 节点 | preferred_model | 理由 |
|------|-----------------|------|
| D0, D1, D2, D4 | sonnet | python/numpy/pytest/evidence 路由复杂度中 |
| D3 | glm-5.1 | yaml/CI 标准化模板，省钱 |
| D5 | sonnet | release docs 表述精度要求高 |
| D6 | opus | 跨 sprint 聚合 + epic close 决策，需高 reasoning |

## 4. SLO 阈值（D0 + D2 + D4 共同 enforce）

| 指标 | hard FAIL | soft WARN |
|------|-----------|-----------|
| `kvtc_accept` p95_rel_rmse | > 0.02 | > 0.015 |
| `kvtc_accept` min_cos | < 0.999 | < 0.9995 |
| 混合 family `kvtc_accept` 数 | > 0 (立即 FAIL) | n/a |
| stable-ci fixture 个数 | < 12 | < 14 |
| named prompt cache 2xx 比例 (env=1) | < 0.95 | < 0.99 |
| 任一 NaN/Inf 未 reject | > 0 | n/a |
| CI job 总耗时 (stable-ci) | > 30 min | > 10 min |

## 5. Stop Rules（继承 contract）

- 缺 `task_graph.json` 不得派 builder（已有）
- 缺可复现验证不得标记 passed（D4 是验证）
- 发现 scope 冲突必须回写父级 traceability（D6 负责）
- D4 任一 fixture decision ≠ expect_decision → S05 整体 FAIL，触发 S03 round-2
- 禁止真改 `src/omlx/cache/kvtc_*.py` 或 `src/omlx/server.py`（S03/S04 范围）
- 禁止真加载 Qwen3.6 真模型权重
- 禁止 commit 巨型 fixture（>100 MB 必须走 fetch_kvtc_fixtures.sh）
- 禁止放宽 hard 阈值 0.02 / 0.999
- 禁止乐观词

## 6. 失败恢复

- D0 失败：CLI 升级回滚（旧 scripts/kvtc_ab_correctness.py 兼容性强），重派一次。
- D1/D2/D3 任一失败：单独重派该节点，不阻塞另外两个 wave-2 节点。
- D4 失败：诊断 evidence (recon_gate.jsonl 14 字段)，若是 S03 实现 bug → 必须触发 S03 round-2，本 sprint 暂停不 passed。
- D5/D6 失败：单独重派，写范围隔离。

## 7. 当前执行状态（2026-05-27 快照）

| 节点 | status | gate_status | note |
|------|--------|-------------|------|
| D0_ab_correctness_cli_upgrade | reviewing | passed | handoff 已写，等 evaluator |
| D1_fixtures_15_cells | passed | passed | — |
| D2_e2e_tests | passed | passed | — |
| D3_ci_workflow | passed | passed | — |
| D4_smoke_run_evidence | passed | passed | 真跑 evidence 已落 reports/kvtc-ab/ |
| D5_release_docs | passed | passed | — |
| D6_handoff_traceability_epic_close_prep | passed | passed | — |
| **Gate G_S05_verification_release_passed** | **passed** | — | 2026-05-22T10:38:12Z |

实际所有节点已 passed，gate 已 passed，`.finalized` 文件已存在 (May 22 06:42)。本 plan.md 为补齐 Workflow Guard 文件清单要求；不重新规划。

## 8. 给 epic close 的接力

- D6 traceability.json 已含 `parent_check_ready=true` 与 `epic_required_gates_status` 全集（S01..S05 all passed）。
- coordinator/epic_decomposer 在 S05 evaluator 最终确认后自动跑 parent-check 关闭父 epic。
- S05 不主动 close epic。
