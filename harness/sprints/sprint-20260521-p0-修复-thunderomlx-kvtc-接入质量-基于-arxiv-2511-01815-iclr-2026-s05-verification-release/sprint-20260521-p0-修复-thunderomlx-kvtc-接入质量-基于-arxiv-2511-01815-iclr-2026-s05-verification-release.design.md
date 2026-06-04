# Design — S05 Verification-Release 切片：CI gate + 回归证据 + 发布文档

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release`
slice: `verification-release`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T09:25:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream_passed: `S03_core_runtime (passed 2026-05-22T09:09:00Z) · S04_orchestration_ui (passed 2026-05-22T09:22:20Z)`

## 0. 本切片的边界（强制 read-first）

- **S05 是 epic 末尾切片**：所有上游（S01/S02/S03/S04）已 passed；本 sprint 产出 CI gate + 回归证据 + 发布文档，使父 epic `parent-check` 可通过。
- **本 sprint 允许的写范围**：
  - `/Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py`（modify，升 CI gate 用）
  - `/Users/lisihao/ThunderOMLX/scripts/fetch_kvtc_fixtures.sh`（新建）
  - `/Users/lisihao/ThunderOMLX/tests/fixtures/kvtc/**`（新建：12+ stable-ci 合成 fixtures + N/A 标记）
  - `/Users/lisihao/ThunderOMLX/tests/regression/test_kvtc_e2e.py`（新建）
  - `/Users/lisihao/ThunderOMLX/.github/workflows/kvtc-regression.yml`（新建）
  - `/Users/lisihao/ThunderOMLX/reports/kvtc-ab/<ts>/{ab_correctness.summary.json, recon_gate.jsonl, per_fixture/*.json}`（D4 真跑产出）
  - `/Users/lisihao/ThunderOMLX/docs/KVTC_RELEASE.md`（新建）
  - `~/.solar/harness/sprints/<s05-sid>.handoff.md`, `<s05-sid>.traceability.json`
- **严格禁止** 触碰：
  - 任何 `src/omlx/cache/kvtc_*.py`（S03 范围）
  - `src/omlx/server.py`（S04 范围）
  - 任何 S03/S04 范围 ThunderOMLX 源码（git diff 必须仅在上述允许路径出现）
  - `~/.solar/STATE.md`、epic.traceability.json、epic.task_graph.json、S01/S02/S03/S04 任何 artifact
- 禁止 `tmux send-keys`、`solar-harness restart`、打开 live tmux pane、动主服务 cache
- **S05 唯一允许真实跑** `scripts/kvtc_ab_correctness.py`（D4 节点）；其他节点禁止真跑
- 禁止用乐观词；禁止放宽 hard 阈值（p95_rel_rmse ≤ 0.02 / min_cos ≥ 0.999）；禁止 commit 巨型 fixture 到 repo（per N6-A2，必须 fetch 脚本拉取或合成）

## 1. 上游摘要（S01..S04 → S05）

| 上游 | 必须消费 |
|------|----------|
| S01 N6 (CI gate) | 5×3 覆盖矩阵 + hard/soft SLO + CI hook + ATLAS repair hook |
| S01 N4 (recon gate) | jsonl schema 字段集 + 公共 API `kvtc.recon_gate.evaluate` |
| S02 A3 API 3/6/7 | recon_gate 接口、`/v1/cache/prompt/save` 410 路径、`/api/kvtc/state` |
| S02 A4 Schema 1/2/3 | manifest.jsonl / recon_gate.jsonl / ab_correctness.summary.json 三个 schema |
| S02 A6 (observability) | CI artifact 路径合同 + ATLAS hook 名 + SLO 告警分级 |
| S03 B0..B5 (实现) | `omlx.cache.kvtc_codec.encode` + `kvtc_recon_gate.evaluate` + `kvtc_calibration_store.lookup_v2` |
| S03 B6 (22 pytest) | 已 passed → S05 可调用同 import 路径 |
| S04 C1 (server routes) | `/v1/cache/prompt/save` env=0 → 410 + `/api/kvtc/state` |
| S04 C3 (15 pytest) | 已 passed → S05 可调用同模块 |

## 2. 系统视图（哪个文件什么变化）

```
scripts/                                              （S05 写范围）
├── kvtc_ab_correctness.py    [D0 MODIFY]              新 CLI flags:
│                                                       --fixture-set stable-ci|local-only
│                                                       --report-dir <path>
│                                                       --fail-on-gate-violation
│                                                       --emit-recon-gate-jsonl
│                                                       --dump-meta / --dump-family-decisions
└── fetch_kvtc_fixtures.sh    [D1 NEW]                 fixture 拉取 hook（占位脚本，stable-ci synthetic）

tests/                                                 （S05 写范围）
├── fixtures/kvtc/            [D1 NEW]                  12+ stable-ci synthetic fixtures
│   ├── qwen36_ssd_block_tk_001.npz       (transformer-K, RoPE-applied)
│   ├── qwen36_ssd_block_tv_001.npz       (transformer-V)
│   ├── same_dim_family_001.npz           (head_dim=128 两 model)
│   ├── hybrid_family_001.npz             (local-only 标记)
│   ├── synthetic_outlier_001.npz         (5σ 尖刺)
│   ├── named_prompt_cache_001.npz        (取决于 S04: env=0 → mocked-pending-stable)
│   └── manifest.json                     (15 cell 元数据 + expect_decision + source)
└── regression/test_kvtc_e2e.py [D2 NEW]                e2e: 调用 ab_correctness + 校验 jsonl schema
                                                        调用 GET /api/kvtc/state via TestClient
                                                        校验 410 路径

.github/workflows/
└── kvtc-regression.yml       [D3 NEW]                  pre-merge: ab_correctness --fixture-set stable-ci
                                                        post-merge: 全集 + ATLAS hook

reports/kvtc-ab/<ts>/         [D4 RUN-PRODUCE]          smoke run 产出
├── ab_correctness.summary.json
├── recon_gate.jsonl
└── per_fixture/*.json

docs/
└── KVTC_RELEASE.md           [D5 NEW]                  release notes + rollback + evidence summary
```

下游不动：
- `src/omlx/cache/kvtc_*.py`、`src/omlx/server.py`（S03/S04 范围）
- `~/.solar/STATE.md`、`epic-*.traceability.json`、`epic-*.task_graph.json`、S01/S02/S03/S04 sprint artifacts

## 3. 5×3 覆盖矩阵（D1 实施 + D2/D4 验证）

per S01 N6-A1 钉死，15 cells 必须全覆盖：

| Fixture 类别 | fixture source | pass (kvtc_accept) | fallback (lz4_fallback) | fail (reject) |
|--------------|---------------|---------------------|--------------------------|----------------|
| 真实 SSD block (Qwen3.6 32B) | local-only | qwen36_real_tk_pass (本地手动) | qwen36_real_tk_fallback | qwen36_real_tk_calmiss |
| 同维 family (head_dim=128) | stable-ci | same_dim_family_001 | same_dim_family_002_miss | same_dim_family_003_rev |
| 混合 family (attention + mamba) | local-only | hybrid_001_NA (标记 expect_decision="na") | hybrid_001_lz4 | hybrid_001_force_kvtc_reject |
| synthetic outlier | stable-ci | outlier_001_pass | outlier_001_fallback | outlier_001_nan_reject |
| named prompt cache | stable-ci (mocked-pending-stable since S04=env=0 disabled) | npc_001_mocked_pass (mocked) | npc_001_mocked_fallback | npc_001_skip_when_disabled |

矩阵共 15 cells，stable-ci ≥ 12（满足 N6 SLO），local-only ≤ 3。

每 fixture `manifest.json` 字段（per N6-A1）：

```json
{
  "fixture_id": "qwen36_ssd_block_tk_001",
  "fixture_class": "real_ssd_block",
  "source": "stable-ci",
  "expect_decision": "kvtc_accept",
  "tensor_family": "transformer-K",
  "shape_signature": "d128xh40xkvh8xseq256",
  "rope_state": "applied",
  "layer_type": "attention",
  "p95_rel_rmse_max_expected": 0.02,
  "min_cos_min_expected": 0.999,
  "note": "synthetic stand-in until real Qwen3.6 dump available"
}
```

## 4. CLI 升级（D0 实施）

per N6-A3，`scripts/kvtc_ab_correctness.py` 新增 CLI 行为：

```bash
python scripts/kvtc_ab_correctness.py \
  --fixture-set stable-ci \
  --report-dir reports/kvtc-ab/$(date +%Y%m%d-%H%M%S)/ \
  --fail-on-gate-violation \
  --emit-recon-gate-jsonl

# 退出码：
#   0 = 全 fixture 符合 expect_decision
#   1 = hard SLO 越界 (--fail-on-gate-violation)
#   2 = fixture loader 失败
#   3 = recon_gate.evaluate 抛 ReconGateInternalError
```

落盘产物（per N6-A7 + Schema 3 ab_correctness.summary.json + Schema 2 recon_gate.jsonl）：

- `<report-dir>/ab_correctness.summary.json` — 含 schema_version=`kvtc.ab_summary.v1` + 15 fixture results + observed vs threshold + named_prompt_cache_status
- `<report-dir>/recon_gate.jsonl` — 每 fixture 一行 + 与 N4-A5 全 14 字段一致
- `<report-dir>/per_fixture/*.json` — 每 fixture 详细 metrics

CLI 必须 `import kvtc.recon_gate.evaluate` from `omlx.cache.kvtc_recon_gate`（S03 公共 API）。

## 5. CI Hook（D3 实施）

per N6-A3，`.github/workflows/kvtc-regression.yml`：

- **pre-merge** trigger: PR + push to main
- pre-merge job 跑 `--fixture-set stable-ci`（≤ 10 分钟）
- artifact upload: `reports/kvtc-ab/<ts>/`
- hard SLO 越界 → job FAIL + GitHub check 红 + 自动 issue 标 `kvtc-regression`
- soft SLO 越界 → job WARN + 自动 issue 标 `kvtc-watchlist`
- **post-merge / nightly** trigger: schedule cron
- post-merge job 跑全集（含 local-only mocked）→ 失败发 issue，不 block

ATLAS hook 名 `atlas.kvtc.recon_gate_repair`（per N6-A5）：

- S05 在 README.md（或 docs/KVTC_RELEASE.md）记录 hook 名 + 触发条件「连续 3 次 nightly 同 fixture FAIL」
- 实际注册 ATLAS hook 由 Solar Harness 运维侧配置（S05 不自动注册，仅记录合同；属 docs scope）

## 6. SLO 阈值（D0 + D2 + D4 共同 enforce）

per N6-A4，hard / soft 双层：

| 指标 | hard FAIL | soft WARN |
|------|-----------|-----------|
| `kvtc_accept` 子集 p95_rel_rmse | > 0.02 | > 0.015 |
| `kvtc_accept` 子集 min_cos | < 0.999 | < 0.9995 |
| 混合 family `kvtc_accept` 数 | > 0 | n/a（任何 > 0 都 FAIL） |
| stable-ci fixture 个数 | < 12 | < 14 |
| named prompt cache 2xx 比例 (env=1 时) | < 0.95 | < 0.99 |
| 任一 fixture NaN/Inf 未 reject | > 0 | n/a |
| CI job 总耗时 (stable-ci) | > 30 min | > 10 min |
| 任一 `kvtc_accept` + `min_cos < 0.999` | > 0 (立即 hard) | n/a |

## 7. 真实 Qwen3.6 block 决策

per N6-A2 + OQ1 仍 open：

- **本 sprint 默认全合成 fixture**（stable-ci 12+ synthetic + local-only 3 placeholder）
- 真实 Qwen3.6 K/V block 标记为 `source=local-only` 且 `note="synthetic stand-in until real Qwen3.6 dump available"`
- S05 不真实加载 Qwen3.6 模型（成本高 + MLX 依赖）；如运维端有真实 dump，可用 `fetch_kvtc_fixtures.sh` 在 staging 拉取后替换 placeholder
- OQ1 状态更新：`tentatively_resolved` — fixtures 默认 stable-ci synthetic；真实 dump 留 staging/运维择机注入

## 8. 状态、失败恢复、观测

- **D4 smoke run** 必须真跑 `scripts/kvtc_ab_correctness.py --fixture-set stable-ci`，产出 reports/kvtc-ab/<ts>/ 全套 artifact
- 运行环境：ThunderOMLX venv（`./venv/bin/python`）；不依赖 GPU / MLX 真模型；纯 numpy + S03 公共 API
- 失败处理：
  - D4 真跑期间 ImportError → 立即 FAIL（S03 公共 API 兼容性问题）
  - D4 任一 fixture decision ≠ expect_decision → hard FAIL
  - D4 hard SLO 越界 → 立即 FAIL + 发 issue
  - D4 输出文件缺 schema_version 字段 → FAIL
- 观测：D4 产出 jsonl + summary.json 即原始证据；D5 release notes 引用这些路径

## 9. 兼容性

- `scripts/kvtc_ab_correctness.py` 现有 CLI（A1 archeology 确认 lines 25-30 import + 83-100 run_case）必须保留兼容；新增 CLI flags 不破坏旧调用
- `tests/fixtures/kvtc/` 是新目录，与现有 tests/* 不冲突
- `.github/workflows/kvtc-regression.yml` 是新 workflow，不影响其他 CI
- `reports/kvtc-ab/<ts>/` 是新目录；时间戳防 collision
- `docs/KVTC_RELEASE.md` 是新文件；不替代 README.md（如需也可以追加 README section，但本 sprint 默认新增 docs 文件保守）

## 10. 冲突 / 依赖 / 降级

**冲突**：

- 真实 Qwen3.6 dump 不存在 vs N6 要求"覆盖真实 SSD block" → S05 用 stable-ci synthetic + local-only placeholder，OQ1 状态明示 tentatively_resolved
- D4 smoke run 必须 import `omlx.cache.kvtc_recon_gate.evaluate` → 依赖 S03 完成（已 passed）+ ThunderOMLX venv 可访问
- N5 决策 env=0 默认禁用 → named prompt cache fixture 走 `mocked-pending-stable`（N6-A6 已钉死 conditional fixture）

**依赖**：

- D1, D2, D3 依赖 D0（CLI 升级先于其他）
- D4 依赖 D1+D2+D3（fixtures+tests+CI 全到位才 smoke）
- D5 依赖 D4（release notes 引用 evidence）
- D6 join all

**降级**：

- 若 D4 smoke run 任一 fixture ≠ expect_decision → S03 实现端可能有 bug → S05 不许 passed，触发 S03 round-2
- 若 ATLAS hook 注册失败（运维侧未上线）→ S05 仅 docs 记录，不阻塞 sprint passed
- 若 mirage / qmd / obsidian 持续 degraded → 本 sprint self-contained，不依赖检索

## 11. 非目标（明确禁止）

- 不真改 `src/omlx/cache/kvtc_*.py`（S03 范围）
- 不真改 `src/omlx/server.py`（S04 范围）
- 不真加载 Qwen3.6 真模型权重（成本 + MLX 依赖）
- 不修改 `~/.solar/STATE.md` / epic.* / S01/S02/S03/S04 任何 artifact
- 不打开 live tmux pane / 不重启 harness
- 不 commit 巨型 fixture 到 repo（synthetic 张量必须 ≤ 100 MB / 个；或 fetch_kvtc_fixtures.sh 拉取）
- 不放宽 hard 阈值（0.02 / 0.999）
- 不用乐观词
- 不实施真实 Qwen3.6 fixture 拉取（OQ1 留 tentatively_resolved；运维端择机）
- 不自动 merge ATLAS repair 提议

## 12. 给 epic close 的接力（D6 输入要点）

- D6 traceability.json 必须含 epic close 准备字段：
  - `epic_required_gates_status` = 所有 5 个 sprint gate 当前状态（S01..S05）
  - `parent_check_ready` = true 当 S05 evaluator passed 后
  - `evidence_collection_complete` = N1-E1..N7-E6 全集（per S01 evidence_collection_plan）
- S05 不主动 close epic；coordinator/epic_decomposer 在 S05 passed 后自动跑 parent-check
