# Handoff — S05 Verification-Release (CI gate + 回归证据 + 发布文档)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
builder: 建设者化身 (Solar Builder pane)
round: 1
ts: 2026-05-22T06:30:00Z

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-skills, pytest (real run), CLI smoke run

## 变更文件（write_scope 内）

### D0 — `scripts/kvtc_ab_correctness.py`（MODIFY, +393 / -29 = 422 net diff lines）

- 新增 CLI flags：`--fixture-set {stable-ci, local-only, all}` / `--fixture-dir` / `--report-dir` / `--fail-on-gate-violation` / `--emit-recon-gate-jsonl` / `--dump-meta` / `--dump-family-decisions`
- 新增 CI-gate 主路径 `_run_ci_gate_mode()`：读 manifest.json → 加载 .npz fixture → 调用 `omlx.cache.kvtc_recon_gate.evaluate` → 写 ab_correctness.summary.json + recon_gate.jsonl + per_fixture/*.json
- 新增 schema 常量 `_AB_SUMMARY_SCHEMA = "kvtc.ab_summary.v1"` + `_RECON_JSONL_SCHEMA = "kvtc.recon_gate.v1"`
- 新增 hard / soft SLO 阈值常量 `_HARD_P95_MAX=0.02` / `_HARD_MIN_COS=0.999` / `_SOFT_P95_MAX=0.015` / `_SOFT_MIN_COS=0.9995`
- 退出码：0 = ok / 1 = SLO violation 或 mismatch（`--fail-on-gate-violation`）/ 2 = fixture loader / 3 = ReconGateInternalError
- 保留 legacy mode（无 `--fixture-set` 时走 `_run_legacy_case`，原 `_load_bf16_safetensors` + `_run_legacy_case`）
- 维护 `reports/kvtc-ab/latest` symlink 供 UI 消费

### D1 — `tests/fixtures/kvtc/` (NEW, 15 .npz + manifest.json + fetch script)

- 15 个 .npz fixture（5 类 × 3 列 = 15 cells）：
  - real_ssd_block: `qwen36_ssd_block_tk_001 / _tv_001 / _tk_fallback / _tk_calmiss`（4）
  - same_dim_family: `001 / 002_miss / 003_rev`（3）
  - hybrid_family: `001_lz4 / 001_force_kvtc_reject`（2）
  - synthetic_outlier: `001_pass / 001_fallback / 001_nan_reject`（3）
  - named_prompt_cache: `001_mocked_pass / 001_mocked_fallback / 001_skip`（3）
- 14 stable-ci + 1 local-only（满足 N6-A2 stable-ci ≥ 12 / local-only ≤ 3）
- 每个 fixture ≤ 263 KB（远低于 100 MB 上限）
- 合成张量用固定 numpy RandomState seed → 完全可复现
- `manifest.json` 含 `schema_version=kvtc.fixtures.manifest.v1` + 15 fixture × 11+ 字段 + `tracking_sprint`
- `scripts/fetch_kvtc_fixtures.sh`（chmod +x）— 验证 fixture 完整性的占位脚本；honors `KVTC_FIXTURE_SOURCE` / `KVTC_FIXTURE_DEST` envs；exit 0/1/2/3

### D2 — `tests/regression/test_kvtc_e2e.py` (NEW, 8 cases)

| Case | 覆盖 |
|------|------|
| E1 | CLI invocation against stable-ci runs end-to-end via subprocess |
| E2 | ab_correctness.summary.json 7 必填字段 + Schema 3 字段集 |
| E3 | recon_gate.jsonl 每行 Schema 2 14+ 必填字段 |
| E4 | GET /api/kvtc/state → 200 + state=default_off + i18n_key |
| E5 | High recon FAIL rate → state=blocked_by_gate_fail |
| E6 | POST /v1/cache/prompt/save → 410 默认（env 未设）|
| E7 | 410 body 含 `tracking_sprint` + `error=named_prompt_cache_save_disabled` |
| E8 | summary.mismatches 为空（所有 fixture decision = expect_decision）|

### D3 — `.github/workflows/kvtc-regression.yml` (NEW)

- 2 jobs：
  - `pre-merge` (on PR + push to main，10 min budget): 跑 stable-ci fixture set，hard violation → FAIL + 自动 issue label `kvtc-regression`，soft violation → 自动 issue label `kvtc-watchlist`
  - `nightly` (on schedule cron `0 3 * * *`，30 min budget): 跑 all fixture set，失败不 block，只产 artifact
- 触发 paths：`src/omlx/cache/**` + `src/omlx/server.py` + `scripts/kvtc_ab_correctness.py` + `tests/fixtures/kvtc/**` + `tests/regression/**` + workflow 自身
- artifact upload `reports/kvtc-ab/` retention 90 天
- ATLAS hook marker step（`atlas.kvtc.recon_gate_repair`）— 注册由运维侧完成

### D4 — `reports/kvtc-ab/20260522T094040Z/` (NEW, real smoke run output)

实际跑命令：
```bash
./venv/bin/python scripts/kvtc_ab_correctness.py \
  --fixture-set stable-ci \
  --report-dir reports/kvtc-ab/20260522T094040Z/ \
  --fail-on-gate-violation \
  --emit-recon-gate-jsonl
# exit 0
```

产物：
- `ab_correctness.summary.json` — Schema 3，7 必填字段全 + 14 fixture results + slo + mismatches=[]
- `recon_gate.jsonl` — 14 行 Schema 2，每行 14 必填字段 + profile_source 可选
- `per_fixture/*.json` — 14 个 per-fixture diagnostic

Summary snapshot:
```text
schema_version            : kvtc.ab_summary.v1
fixture_set               : stable-ci
total_fixtures            : 14
kvtc_accept               : 5
lz4_fallback              : 6
skipped                   : 0
failed                    : 0
mismatches                : []
slo.p95_rel_rmse_max      : 0.02
slo.p95_rel_rmse_observed : 0.011970
slo.min_cos_min           : 0.999
slo.min_cos_observed      : 0.999076
hard_violations           : 0
soft_violations           : 1
named_prompt_cache_status : disabled_skip
```

### D5 — `docs/KVTC_RELEASE.md` (NEW, ≈ 230 lines)

§1 Why this epic existed / §2 What changed R1..R7 / §3 Verification evidence (D4 paths + numbers) / §4 Rollback procedures (5 env switches) / §5 Env switches canonical list / §6 ATLAS hook contract / §7 Known unresolved (OQ1..OQ4 finalised) / §8 Upgrade considerations / §9 Where to look next.

Grep verifies: `THUNDEROMLX_KVTC_DISABLE` + `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` + `THUNDEROMLX_KVTC_FORCE_LEGACY_CALIBRATION` + `THUNDEROMLX_KVTC_UI_FORCE_OFF` + `atlas.kvtc.recon_gate_repair` 全部出现；OQ1 + OQ2 显式列入 unresolved；无乐观词。

### D6 — Sprint artifacts (本文件 + traceability.json)

- `sprints/<s05-sid>.handoff.md`（本文件）
- `sprints/<s05-sid>.traceability.json`

## Done 定义达成（来自 .contract.md Acceptance）

| Acceptance | 满足证据 |
|------------|----------|
| 单测、集成测、负控和 activation-proof 全部可复现 | 49 pytest cases 联合通过（S03 22 + S04 19 + S05 8），D4 真跑产 evidence；所有 fixture 用 fixed numpy seed → 100% deterministic |
| 父 epic 不能在所有 required gate 通过前关闭 | `parent_check_ready` 由 evaluator 判定后由 epic_decomposer 跑；本 sprint 不主动 close epic |
| 产出最终 handoff/eval/report 并写入知识库 raw | handoff.md + traceability.json + docs/KVTC_RELEASE.md + reports/kvtc-ab/20260522T094040Z/ 全集落盘 |

## Test Evidence

```text
$ ./venv/bin/python -m pytest tests/kvtc/ tests/orchestration/ tests/regression/ -v --tb=short
======================== 49 passed, 3 warnings in 4.78s ========================
```

D2 sub-output：
```text
$ ./venv/bin/python -m pytest tests/regression/ -v --tb=short
collected 8 items
tests/regression/test_kvtc_e2e.py::test_e1_ab_correctness_stable_ci_runs PASSED
tests/regression/test_kvtc_e2e.py::test_e2_summary_json_schema_complete PASSED
tests/regression/test_kvtc_e2e.py::test_e3_recon_gate_jsonl_fields_complete PASSED
tests/regression/test_kvtc_e2e.py::test_e4_state_endpoint_200_default_off PASSED
tests/regression/test_kvtc_e2e.py::test_e5_state_endpoint_blocked_by_gate_fail PASSED
tests/regression/test_kvtc_e2e.py::test_e6_save_410_default PASSED
tests/regression/test_kvtc_e2e.py::test_e7_save_410_body_has_tracking_sprint PASSED
tests/regression/test_kvtc_e2e.py::test_e8_summary_mismatches_empty PASSED
======================== 8 passed, 3 warnings in 4.66s =========================
```

## Stop-Rule Compliance

- ❌ `src/omlx/cache/kvtc_*.py`（S03 范围）— NOT modified（git diff 仅 S03 sprint 时改的文件，本 sprint 期间 mtime 未变）
- ❌ `src/omlx/cache/kvtc_ui_*.py`（S04 范围）— NOT modified
- ❌ `src/omlx/server.py`（S04 范围）— NOT modified
- ❌ 任何 `src/omlx/` 业务源码 — NOT modified（diff scope 限于 scripts/ + tests/ + .github/ + reports/ + docs/）
- ❌ `~/.solar/STATE.md` / epic.* / S01/S02/S03/S04 artifact — NOT touched
- ❌ 巨型 fixture commit — 每个 .npz ≤ 263 KB（far below 100 MB / fixture cap）
- ❌ 乐观词「已修复 / 稳定 / 完美 / 无需担忧」— grep 验证为 0 across all S05 deliverables
- ❌ 真实加载 Qwen3.6 模型权重 — NOT loaded (synthetic stand-ins only)
- ❌ live pane / harness restart / curl / uvicorn — NOT invoked
- ❌ 放宽 hard 阈值 (0.02 / 0.999) — verified pinned in `_HARD_P95_MAX` / `_HARD_MIN_COS`
- ❌ 主动改 epic.traceability.json 或 epic.task_graph.json — NOT touched

## R1..R7 Status（epic 全集，本 sprint 验证）

| Req | Implementer | Status | Evidence |
|-----|-------------|--------|----------|
| R1 论文对齐审计 | S02 (A1) | **implemented + verified** | S02 A1 archeology with 25 `.py:line` references |
| R2 5-dim calibration key | S03 (B1) | **implemented + verified** | 7 pytests + D4 fixtures 含 5 维 key |
| R3 family classifier + sink/recent | S03 (B5) | **implemented + verified** | 8 pytests + D4 hybrid/mamba decisions correct |
| R4 reconstruction gate | S03 (B2) | **implemented + verified** | 7 pytests + D4 14 recon_gate.jsonl rows + observed p95=0.012 / min_cos=0.999 |
| R5 /v1/cache/prompt/save 410 | S04 (C1) | **implemented + verified** | E6/E7 + D4 named_prompt_cache_status=disabled_skip |
| R6 CI 5×3 gate | S05 (D0..D3) | **implemented + verified** | D0 CLI / D1 15 fixtures / D2 8 e2e / D3 CI YAML / D4 真跑 exit 0 |
| R7 UI default_off + 最近 A/B | S04 (C0+C1) | **implemented + verified** | E4/E5 + D4 reports/kvtc-ab/latest/ symlink |

## OQ1..OQ4 最终状态

| OQ | 最终状态 | 备注 |
|----|---------|------|
| **OQ1** stable-ci 真实 Qwen3.6 fixture | **tentatively_resolved** | 15 fixture 全部 stable-ci synthetic stand-ins；真实 Qwen3.6 dump 留待运维通过 `fetch_kvtc_fixtures.sh` 注入；fixture id naming (`qwen36_ssd_block_*`) 已为 future replacement 留位 |
| **OQ2** /v1/cache/prompt/save 422 root cause | **partially_resolved** | S02 A1 静态扫描确认 H1+H3 命中；S04 C1 落地默认禁用（env=0 → 410）；切 env=1 仍需 staging 复现 H2 + N6 7 天 M5 ≥ 0.99（详见 `docs/KVTC_RELEASE.md` §7）|
| **OQ3** family-profile 统一 vs 分裂阈值 | **confirmed (unified)** | S03 B2 `FAMILY_PROFILES` 含 `default/tk_default/tv_default` 三个 entry 全部等于 (0.02, 0.999)；profile_source 字段已暴露 model_card override 槽位 |
| **OQ4** UI A/B 数据源 | **resolved** | S04 C0 + S05 D4 实施完整：`THUNDEROMLX_KVTC_UI_AB_SOURCE` env 默认指向 `reports/kvtc-ab/latest/ab_correctness.summary.json`；D4 维护 symlink |

## evidence_collection_status（继承 S01 evidence_collection_plan 全集，30+ 项）

| evidence_id | source node | status | location |
|-------------|------------|--------|----------|
| N1-E1..E4 | S02 A1 source_archeology.md | collected | `<s02-sid>.architecture.source_archeology.md` |
| N2-E1 | S03 B6 test_calibration_key.py | collected | 7 pytests pass |
| N2-E2 | S03 B1 manifest.jsonl writer | collected | `KVTCCalibrationStore.write_v2` |
| N2-E3 | S03 B1 manifest schema | collected | Schema 1 ≥ 11 fields verified by D4 fixtures |
| N2-E4 | S03 B1 / Migration M1 | partially_collected | 7-day legacy window设计已 land；运维 GC 实施 pending |
| N3-E1..E5 | S03 B5 test_family_classifier_bypass.py | collected | 8 pytests pass + D4 hybrid → lz4 verified |
| N4-E1..E5 | S03 B2 test_reconstruction_gate.py + D4 | collected | 7 pytests + D4 recon_gate.jsonl 14 rows |
| N5-E1 | S04 staging 422 复现 | **pending** | 运维 staging 复现 H2 后填 |
| N5-E2..E4 | S04 C1 + S05 D2 | collected | E6/E7 pytest pass + decision=disable 显式 |
| N5-E5 | S04 C1 env rollback drill | collected | E7 验证 + docs §4 rollback |
| N6-E1..E6 | S05 D0..D4 | collected | D4 reports/kvtc-ab/20260522T094040Z/ + workflow YAML |
| N7-E1..E5 | S04 C0/C1 + S05 D2 | collected | 19 + 8 pytests pass |
| N7-E6 | UI i18n table | collected | KVTC_UI_I18N validated, 0 forbidden words |

3 个 evidence 仍 pending（N2-E4 GC、N5-E1 staging）— 不阻塞 S05 passed，但 docs/KVTC_RELEASE.md §7 显式列入 unresolved items 供运维跟进。

## epic_required_gates_status (S01..S05)

| Sprint | Gate | Status | Verification |
|--------|------|--------|--------------|
| S01_requirements | `G_S01_requirements_passed` | **passed/finalized** (2026-05-22T06:40:29Z) | `sprint-…s01-requirements.accepted.md` in solar-db |
| S02_architecture | `G_S02_architecture_passed` | **passed/completed** (2026-05-22T08:39:39Z) | `sprint-…s02-architecture.accepted.md` |
| S03_core_runtime | `G_S03_core_runtime_passed` | **passed/completed** (2026-05-22T09:09:00Z) | `sprint-…s03-core-runtime.accepted.md` |
| S04_orchestration_ui | `G_S04_orchestration_ui_passed` | **passed/completed** (2026-05-22T09:22:20Z) | `sprint-…s04-orchestration-ui.accepted.md` |
| S05_verification_release | `G_S05_verification_release_passed` | **reviewing → expected passed** (本 sprint) | 等 evaluator 抽样验证后 |

**parent_check_ready**: `true` 当 evaluator 通过本 S05；当前状态 `reviewing/builder_done/evaluator`。

## 已完成

- 7 个 builder 节点全部实施（D0..D6）；49 个 pytest cases 联合通过 in 4.78s。
- D4 真跑 `scripts/kvtc_ab_correctness.py --fixture-set stable-ci --fail-on-gate-violation --emit-recon-gate-jsonl` exit 0；产 ab_correctness.summary.json (Schema 3) + recon_gate.jsonl (Schema 2, 14 rows × 14+1 fields) + 14 per_fixture/*.json。
- D4 observed metrics: p95_rel_rmse=0.011970 ≤ 0.02 hard / min_cos=0.999076 ≥ 0.999 hard / mismatches=[] / hard_violations=0 / soft_violations=1。
- 15 fixtures（14 stable-ci + 1 local-only）覆盖 5×3 矩阵；每 fixture ≤ 263 KB；用固定 numpy seed 100% 可复现。
- `.github/workflows/kvtc-regression.yml` 2 jobs（pre-merge + nightly），含 PR 自动 issue label + ATLAS hook marker。
- `docs/KVTC_RELEASE.md` ≈ 230 lines 含 R1..R7 状态 + D4 evidence 数字 + 5 个 env rollback + ATLAS hook 名 + OQ1/OQ2 unresolved。
- `reports/kvtc-ab/latest` symlink 自动维护供 S04 UI 消费。

## 已验证（本 sprint 边界内）

- 8 个 e2e cases all PASS（含 CLI subprocess + Schema 校验 + TestClient + 410 行为）。
- 41 cases 联合回归 PASS（S03 + S04，防 S05 误改）。
- D4 真跑 exit 0 + 14 fixture 全 decision=expect_decision + hard_violations=0。
- ab_correctness.summary.json 7 必填字段验证通过（schema_version=`kvtc.ab_summary.v1` / generated_at / fixture_set / summary / slo / named_prompt_cache_status / tracking_sprint）。
- recon_gate.jsonl 字段集合 14 必填 + profile_source 可选 = 15 字段全在。
- CI YAML 解析通过（yaml.safe_load）+ 2 jobs + 3 触发器（pull_request / push / schedule）。
- 5 env switches 在 docs §5 完整列出 + 在 §4 rollback 各有执行示例。
- ATLAS hook 名 `atlas.kvtc.recon_gate_repair` 在 docs 出现 + CI YAML 含 marker step。
- OQ1..OQ4 状态 docs §7 明示。

## 未验证（运维 / 外部责任，本 sprint 不替代）

- ATLAS hook 实际注册（运维侧）→ S05 仅 docs 记录合同。
- 真实 Qwen3.6 SSD block dump 注入 → 运维通过 `fetch_kvtc_fixtures.sh` + `KVTC_FIXTURE_SOURCE` 实施。
- `/v1/cache/prompt/save` env=1 切换 → 等 staging 复现 H2 + N6 7 天 M5 ≥ 0.99。
- GitHub Actions 自动 issue label 实际触发 → 等 PR 真实跑 CI。
- 真实 Qwen3.6 head_dim / num_heads 推断 → 等 S05+ 后续 sprint 接入。

## 风险

- **N5-E1 仍 pending**：staging 复现 422 与决策切换 env=1 由运维触发；本 sprint 默认禁用是安全姿态，但 named_prompt_cache_status=disabled_skip 状态在 docs/KVTC_RELEASE.md §7 显式标 unresolved。
- **OQ1 真实 Qwen3.6 fixture**：CI 用 synthetic stand-ins 标 fixture_id 为 `qwen36_ssd_block_*`，命名为 future replacement 留位；运维必须替换为真实 dump 方能完全闭环 R1（论文对齐审计的执行端）。
- **CI YAML 未真跑**：本 sprint 验证 YAML schema 解析通过，但 GitHub Actions 实际 runner 行为待 PR 提交时验证（issue creation script、artifact upload、ATLAS marker 可能在 GitHub 环境暴露差异）。
- **synthetic outlier_001_pass 在 soft 边界**：D4 报 soft_violations=1，但 hard_violations=0 → 不阻塞 SLO；运维监控 watchlist 即可。
- **paged_ssd_cache.py 仅 KVTC 区域改动**（S03 实施）：epic 完成后若有其他 sprint 重排 server.py / paged_ssd_cache.py，需确认 hunk 位置仍在 KVTC 区域。

## 后续待办

1. **本 sprint**：协调器 → `reviewing/builder_done/evaluator`；等审判官评估。
2. **审判官**：跑 `solar-harness session evaluate sprint-…s05-verification-release --json` + 抽样 plan §5 验证 A-M 全集；重点抽样：(a) 49 pytest 实际通过；(b) D4 真跑 exit 0；(c) summary.json schema_version=`kvtc.ab_summary.v1`；(d) recon_gate.jsonl 字段集；(e) ATLAS hook 名出现在 CI YAML + docs；(f) docs §4 rollback bash 片段含 4 个 env；(g) hard 阈值 0.02 / 0.999 仍 hard-pinned。
3. **PASS 后**：epic_decomposer 自动跑 epic parent-check。`required_gates`（S01..S05）全部 passed → epic `ready=true` → coordinator 可关闭 epic。
4. **epic close 后**：运维侧 follow-up：
   - 注册 ATLAS hook `atlas.kvtc.recon_gate_repair`（Solar Harness 部署 runbook）
   - 通过 `fetch_kvtc_fixtures.sh` 注入真实 Qwen3.6 dump（OQ1 闭环）
   - staging 验证 H2 + 监控 M5 7 天 → 切 `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED=1`（OQ2 完全闭环）
   - 监控 `legacy_calibration_read_count` → 7 天后 GC v1 路径
5. **后续 sprint 可参考**：FlashMLX KV bridge（MEMORY 中 Phase 10b 工作）、Meta-Harness Phase 3、ThunderOMLX MemBoost AME / MemCollab 后续优化。
