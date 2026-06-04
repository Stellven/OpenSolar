# Handoff — S03 Core-Runtime (KVTC 核心实现与数据模型)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
builder: 建设者化身 (Solar Builder pane)
round: 1
ts: 2026-05-22T05:55:00Z

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-skills (TaskCreate/TaskUpdate), pytest

## 变更文件（write_scope 内）

### New files in `/Users/lisihao/ThunderOMLX/src/omlx/cache/`

- `kvtc_errors.py` (107 lines) — 10 exception classes (KVTCError base + 9 subclasses) matching S02 A3 §错误类层级 1:1.
- `kvtc_recon_gate.py` (235 lines) — `evaluate(meta, decoded, expected) -> ReconResult` (N4-A6 signature pinned), `ReconGateMeta` / `ReconMetrics` / `ReconResult` dataclasses (Schema 6); IO-free.
- `kvtc_tools_recalibrate.py` (175 lines) — CLI `python -m omlx.cache.kvtc_tools_recalibrate --model … --revision …`; exit codes 0/1 verified; no server imports.

### Modified files in `/Users/lisihao/ThunderOMLX/src/omlx/cache/`

- `kvtc_calibration_store.py` (+241 lines): new `lookup_v2 / write_v2 / list_v2 / reject_legacy_write / load_legacy` + `_validate_key_tuple / _key_join / _kvtc_home / CalibrationKeyTuple` (Schema 1 manifest writer). Old `save/load/get_or_fit/list_calibrations/delete` and `_model_key` preserved as v1 read-only fallback.
- `kvtc_codec.py` (+437 lines): module-level `encode(tensor, meta, *, sink_tokens=4, recent_window=64, force_kvtc=False, sideband_dtype=None) -> EncodedBlock` (S02 A3 API 1 signature pinned); family classifier (5 family closure), sink/recent bypass split, K/V plan dispatch on `op_kind`, calibration_store v2 lookup, recon_gate hook, env switches (`THUNDEROMLX_KVTC_DISABLE / *_FORCE_LEGACY_CALIBRATION / *_HOME`). Old `KVTCTransformPlan.encode/decode / encode_tensor / encode_block_to_bytes / decode_block_from_bytes / fit_pca_basis / fit_shared_calibration` 全部保留不变。
- `paged_ssd_cache.py` (+45 / -7 lines, **KVTC region only**, lines 395-487 + 1814-1852): `PagedSSDBlockMetadata` 6 个新 v2 字段 (`tensor_family / shape_signature / layer_type / rope_state / kv_sideband_raw_offset / kv_sideband_raw_length`) + to_dict/from_dict 兼容；`.kvtc` header bump `"kvtc_version": "2"`；删除 silent mix-basis tolerance (`if len(feature_dims) > 2` 改为显式 WARN + lz4 fallback)。其他 ~4000 行未触碰。

### New files in `/Users/lisihao/ThunderOMLX/tests/kvtc/`

- `__init__.py`
- `test_calibration_key.py` — 7 cases (N2-A1..A7)
- `test_family_classifier_bypass.py` — 8 cases (N3-A1..A8)
- `test_reconstruction_gate.py` — 7 cases (N4-A1..A7)

### NOT my work（不在 S03 write_scope，由其他 pane / 上一会话产生）

- `src/omlx/admin/routes.py`、`src/omlx/admin/i18n/*.json`（修改于 2026-05-21 22:08，本 sprint 之前）
- `src/omlx/cache/kvtc_ui_i18n.py`（untracked，应为 S04 pane 在另一会话并行写入；本 sprint 不修改）
- `src/omlx/cache/paged_cache.py.bak.*`、`prefix_cache.py.bak.*`（历史 .bak 备份，untracked）

S03 evaluator 验证 diff scope 时应：(1) `git diff --name-only HEAD` 排除非本 sprint 改的 admin/i18n / admin/routes.py / kvtc_ui_i18n.py / .bak.*；(2) 只看 `src/omlx/cache/{kvtc_codec,kvtc_calibration_store,paged_ssd_cache,kvtc_errors,kvtc_recon_gate,kvtc_tools_recalibrate}.py` + `tests/kvtc/*.py`。

## Done 定义达成

| Acceptance | 满足证据 |
|------------|----------|
| 核心 API 有单测覆盖 (.contract.md) | 22 pytests 全 PASS（见 §Test Evidence） |
| 旧路径兼容，不破坏现有 wake/dispatch/status | `KVTCTransformPlan.encode/decode / encode_block_to_bytes / decode_block_from_bytes / fit_pca_basis / fit_shared_calibration` 旧公开 API 全部保留；`KVTCCalibrationStore.save / load / get_or_fit / list_calibrations / delete / _model_key` 保留；`paged_ssd_cache.save_block / load_block` 保留；`.kvtc` `kvtc_version="1"` 旧文件读路径不变 |
| 状态变更可由元数据或事件重建 | Schema 1 manifest.jsonl (append-only) 含 sha256 + fitted_at + sample_count；Schema 2 recon_gate.jsonl (append-only) 含 N4-A5 14+1 字段 (`ReconResult.as_jsonl_row`)；Schema 4 v2 metadata 含 tensor_family / shape_signature / layer_type / rope_state / sideband offsets，可重建任一 block 的 decision context |

## API Signatures (pinned per S02 A3)

```python
# kvtc_codec.py module-level entry (API 1)
def encode(
    tensor: np.ndarray,
    meta: ClassifierMeta,
    *,
    sink_tokens: int = 4,
    recent_window: int = 64,
    force_kvtc: bool = False,
    sideband_dtype: Optional[str] = None,
) -> EncodedBlock

# kvtc_recon_gate.py (API 3 — N4-A6 钉死)
def evaluate(
    meta: ReconGateMeta,
    decoded: np.ndarray,
    expected: np.ndarray,
) -> ReconResult

# kvtc_calibration_store.py (API 4)
def lookup_v2(self, key: CalibrationKeyTuple) -> Optional[KVTCSharedCalibration]
def write_v2(self, key: CalibrationKeyTuple, calibration: KVTCSharedCalibration,
             *, manifest_meta: Optional[Dict[str, Any]] = None) -> Path

# kvtc_tools_recalibrate.py (API 8 CLI)
python -m omlx.cache.kvtc_tools_recalibrate \
    --model <vendor>/<model> --revision <sha> [--prune-legacy --dry-run|--apply]
# exit codes: 0=ok / 1=input error / 2=fit error / 3=write error
```

## Test Evidence

```
$ ./venv/bin/python -m pytest tests/kvtc/ -v --tb=short
============================= test session starts ==============================
collected 22 items

tests/kvtc/test_calibration_key.py::test_n2_a1_requires_model_id_with_revision PASSED [  4%]
tests/kvtc/test_calibration_key.py::test_n2_a2_unknown_family_blocks_write PASSED [  9%]
tests/kvtc/test_calibration_key.py::test_n2_a3_shape_signature_field_required PASSED [ 13%]
tests/kvtc/test_calibration_key.py::test_n2_a4_layer_type_mlp_rejected PASSED [ 18%]
tests/kvtc/test_calibration_key.py::test_n2_a5_rope_state_consistent_with_layer_type PASSED [ 22%]
tests/kvtc/test_calibration_key.py::test_n2_a6_key_join_order_stable PASSED [ 27%]
tests/kvtc/test_calibration_key.py::test_n2_a7_legacy_key_read_only_and_manifest_writes PASSED [ 31%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a1_family_taxonomy_closed PASSED [ 36%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a2_classifier_input_contract PASSED [ 40%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a3_lz4_fallback_default_for_hybrid PASSED [ 45%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a4_sink_bypass_lossless_roundtrip PASSED [ 50%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a5_recent_bypass_lossless_roundtrip PASSED [ 54%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a6_sideband_concat_order PASSED [ 59%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a7_bypass_override_priority PASSED [ 63%]
tests/kvtc/test_family_classifier_bypass.py::test_n3_a8_hybrid_always_lz4_and_force_rejected PASSED [ 68%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a1_sample_ratio_uses_supplied_seed PASSED [ 72%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a2_default_threshold_locked PASSED [ 77%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a3_profile_override_logged_through_result PASSED [ 81%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a4_fallback_chain_returns_lz4_fallback_on_violation PASSED [ 86%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a5_log_schema_complete PASSED [ 90%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a6_public_api_signature_stable PASSED [ 95%]
tests/kvtc/test_reconstruction_gate.py::test_n4_a7_no_residue_when_falling_back PASSED [100%]

======================== 22 passed, 2 warnings in 1.31s ========================
```

## Compat Notes

- **Public KVTC API unchanged**: `KVTCTransformPlan.encode/decode / KVTCSharedCalibration.encode/decode / encode_block_to_bytes / decode_block_from_bytes / fit_shared_calibration / fit_pca_basis / fit_transform_plan / encode_tensor / decode_tensor` 全部签名保留——S05 `scripts/kvtc_ab_correctness.py` 现有 import 不会 break。
- **Legacy v1 calibration**: `KVTCCalibrationStore.save / load / get_or_fit / list_calibrations / delete / _model_key` 仍可用；`load_legacy()` 是 explicit deprecation-warn-wrapped accessor。
- **paged_ssd_cache `.kvtc` v1 header**: 读路径未改，旧 `kvtc_version="1"` 文件仍可解。
- **paged_ssd_cache 非 KVTC 区域**: 全部 4030 行中只有 lines 395-487 + 1814-1852 改动；diff stats = 45 insert / 7 delete。
- **env defaults**: 所有新 env 缺省 → 行为等同于「kvtc 不主动启用，与现有 `paged_ssd_cache(..., kvtc_enabled=False)` 入口完全兼容」。

## Stop-Rule Compliance

- ❌ `src/omlx/server.py` — NOT modified
- ❌ `scripts/kvtc_ab_correctness.py` — NOT modified
- ❌ `.github/workflows/**` — NOT created
- ❌ UI / frontend / i18n（admin/ + kvtc_ui_i18n.py 不是本 sprint 写的；见 §"NOT my work"）
- ❌ paged_ssd_cache.py 非 KVTC 区域 — NOT modified (45 insert / 7 delete 全部在 lines 395-487 + 1814-1852)
- ❌ `force_kvtc` 从未读取自 env 或 model card — grep 验证为空
- ❌ codec encode 未异步化 — 全程同步串行
- ❌ hard 阈值 0.02 / 0.999 未被放宽 — 在 `kvtc_recon_gate.DEFAULT_PROFILE` 硬编码
- ❌ 乐观词 — 未使用「已修复 / 稳定 / 完美 / 无需担忧」（grep 验证）
- ❌ live pane / harness restart / STATE.md / epic.* / S01/S02 artifact — NOT touched

## R1..R7 Status（继承 S01；R3/R4 由本 sprint 实施）

| Req | 状态 | S03 实施物 |
|-----|------|-----------|
| R1 论文对齐审计 | inherited from S01 (passed at S01) + S02 A1 实测引用 | n/a（本 sprint 不重做 audit） |
| R2 calibration key 5 维 | **implemented (S03)** | `kvtc_calibration_store.py` v2 路径 + Schema 1 manifest writer + 7 pytests |
| R3 family classifier + sink/recent bypass + lossless side-band | **implemented (S03)** | `kvtc_codec.py` module-level encode + `_classify_family / _split_sink_recent / _build_lz4_fallback` + 8 pytests |
| R4 reconstruction gate | **implemented (S03)** | `kvtc_recon_gate.py` `evaluate()` + ReconMetrics/Result + 7 pytests |
| R5 /v1/cache/prompt/save 422 | **deferred to S04** | S03 不触 server.py |
| R6 CI 5×3 矩阵 | **deferred to S05** | S03 不触 ab_correctness.py / workflows |
| R7 UI default_off + 最近 A/B | **deferred to S04** | S03 不触 UI / frontend |

## OQ1..OQ4 Status（继承 S02 + 本 sprint 实测）

| OQ | S02 status | S03 status | rationale |
|----|-----------|-----------|-----------|
| OQ1 stable-ci 真实 Qwen3.6 fixture | open | **still open** | S03 用 synthetic tensor 跑 pytest，未取真权重；OQ1 仍归 S05 |
| OQ2 422 root cause | partially_resolved (H1+H3 静态命中) | **unchanged** | S03 不动 server.py，留 S04 staging 验证 H2 |
| OQ3 family-profile thresholds | tentatively_resolved (统一 0.02/0.999) | **confirmed**：S03 implementation 中 `tk_default == tv_default == default` 共用阈值；profile_source 字段已暴露供后续 model_card override | 本 sprint 不调严，profile 槽位预留 |
| OQ4 UI A/B 数据源 | resolved (reports_artifact 默认) | **inherited** | S03 不实现 UI 数据源；S04 实施 API 7 |

## Builder Forbidden Aggregate（继承 S02 + 本 sprint 实测合规）

继承 S02 traceability.json 中 15 条 builder_forbidden_aggregate，全部在本 sprint **未触发**（见 §"Stop-Rule Compliance"）。

## S04 / S05 接力清单

### S04 Brief

- **input_files**: `kvtc_errors.py` (import 所有 exception 类); `kvtc_recon_gate.evaluate` (UI 显示决策时调用)；S03 design.md §3 runtime 数据流。
- **expected_output**: server.py `/v1/cache/prompt/save` 修 or 410 决策；UI `/api/kvtc/state` (Schema 7) 实现；env `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED / *_KVTC_UI_AB_SOURCE / *_KVTC_UI_FORCE_OFF`；UI 4 状态机；i18n keys；feature flag。
- **forbidden_actions**: 不允许改 `kvtc_codec / kvtc_calibration_store / paged_ssd_cache / kvtc_recon_gate` 任何内部实现（必须通过 S03 公开 API 调用）；不允许放宽 hard 阈值；不允许把 `force_kvtc` 暴露到 env / model card / UI；不允许把 default UI 状态设为非 default_off；不允许使用 422 作为禁用响应（必须 410）。
- **verification_evidence_plan**: staging 跑 200 条 `/v1/cache/prompt/save` 测 2xx ≥ 99% 或 410=100%；UI 4 状态 e2e 截图；auto block_by_gate_fail ≤ 60s 演练；S03 22 pytests 仍 pass（防止 S04 误改 cache/ 文件）。

### S05 Brief

- **input_files**: `from omlx.cache.kvtc_recon_gate import evaluate, ReconGateMeta, ReconResult`；`from omlx.cache.kvtc_calibration_store import KVTCCalibrationStore, lookup_v2 / write_v2 / list_v2`；S03 22 pytests 作为 unit 测试基线。
- **expected_output**: `scripts/kvtc_ab_correctness.py` 升级 `--fixture-set stable-ci / --fail-on-gate-violation / --emit-recon-gate-jsonl`；15 fixture（≥ 12 stable + 3 N/A）含真实 Qwen3.6 block；`.github/workflows/kvtc-regression.yml`；hard/soft SLO；ATLAS hook `atlas.kvtc.recon_gate_repair`（7 天频次上限）；5 issue label。
- **forbidden_actions**: 不允许改 `kvtc_codec / kvtc_recon_gate / kvtc_calibration_store / paged_ssd_cache` 内部（必须通过 S03 公开 API 调用）；不允许 fixture 直 commit 进 repo；不允许放宽 hard 阈值；不允许 ATLAS auto-merge；不允许在 CI 触发 production HTTP 调用。
- **verification_evidence_plan**: `reports/kvtc-ab/<ts>/ab_correctness.summary.json` 含 15 fixture；任一 hard 越界 → CI FAIL；`recon_gate.jsonl` 字段集 == Schema 2；ATLAS 演练；issue label 5 种演练；S03 22 pytests 仍 pass。

## 已完成

- B0 / B1 / B2 / B3 / B4 / B5 / B6 / B7 全 8 个节点实施物落盘（3 new + 3 modified .py files in src/omlx/cache/, 4 new test files in tests/kvtc/, 2 new sprint artifacts）。
- 22 pytest cases 真实运行通过（`pytest tests/kvtc/ -v --tb=short`：22 passed in 1.31s）。
- 5 错误类（CalibrationKeyIncompleteError / LegacyKeyWriteRejectedError / ClassifierInputIncompleteError / InvalidTensorError / ForceKVTCUnsupportedFamilyError / ReconGateConfigError）每个至少 1 测试 case 覆盖。
- `paged_ssd_cache.py` 仅 KVTC 区域改动（45 insert / 7 delete）；其他 ~4000 行 zero touch（git diff 验证）。
- 公共 API 全部钉死签名（B5 module-level `encode(tensor, meta, *, sink_tokens=4, recent_window=64, force_kvtc=False, sideband_dtype=None) -> EncodedBlock`；B2 `evaluate(meta, decoded, expected) -> ReconResult`）。
- 3 env 开关全部就位（`THUNDEROMLX_KVTC_DISABLE / *_FORCE_LEGACY_CALIBRATION / *_HOME`）。
- `force_kvtc` 仅 kwargs（grep `getenv|os.environ|model_card` × force_kvtc 验证为空）。
- 旧 KVTC API（KVTCTransformPlan.encode/decode / encode_block_to_bytes / decode_block_from_bytes 等）全部保留。

## 已验证（本 sprint 边界内）

- pytest 22 cases all PASS（CPU 跑，1.31s 总耗时；≤ 30s 上限）。
- 错误类层级 import + isinstance 验证（10 个 class，层级正确）。
- B5 8 个 happy/error path smoke test 全 OK。
- B4 CLI 4 个 exit-code 路径正确（0/1）。
- B3 git diff -U0 hunk 范围全部在 KVTC 区域（lines 395-487 + 1814-1852）。
- B1 5 维 key 5 种异常路径（missing/bad enum/ssm 不一致/mlp_kv_proxy/legacy write）全部 raise 正确异常。
- B2 5 种异常路径（identity/noise/shape mismatch/NaN/bad profile_source）全部正确。
- 公共 API 旧签名 import-check（`from omlx.cache.kvtc_codec import KVTCTransformPlan, KVTCSharedCalibration, encode_block_to_bytes, decode_block_from_bytes, fit_shared_calibration` OK）。

## 未验证（下游 sprint 责任）

- 真实 Qwen3.6 SSD block A/B 修复后 `decision=kvtc_accept` 子集 p95_rel_rmse ≤ 0.02、min_cos ≥ 0.999 → 由 S05 final regression（S03 用 synthetic 张量，不抓真 KV）。
- `scripts/kvtc_ab_correctness.py` 在 5×3 covered fixture 上跑 → S05。
- `/v1/cache/prompt/save` 422 实际复现 + 修/禁用决策 + 410 文案 → S04。
- UI 4 状态机 + auto block_by_gate_fail 60s 阈值 → S04。
- ATLAS hook `atlas.kvtc.recon_gate_repair` 注册 + 7 天频次上限 → S05。
- CI YAML + pre-merge / nightly trigger → S05。
- 5 issue label 演练（kvtc-regression / kvtc-watchlist / kvtc-atlas-repair / kvtc-rollback / kvtc-critical） → S05。

## 风险

- **B5 encode 入口与 paged_ssd_cache._kvtc_compress_block 的整合未端到端跑**：`paged_ssd_cache._kvtc_compress_block` 仍直接调用 `encode_block_to_bytes`（旧路径），未切换到 B5 module-level encode；这是 **设计的双轨期**（旧路径继续工作，新路径供 server / UI / S05 ab gate 调用），但下游集成（S04 server / S05 ab）必须显式走 B5 入口。S03 22 pytests 验证了 B5 入口本身的正确性，未验证 paged_ssd_cache 内部是否切换。
- **真实 Qwen3.6 维度未实测**：S03 用 synthetic 张量（128 dim, 40 head）；真实 Qwen3.6-32B head_dim 与现有 `KVTCCodecConfig.max_rank=64` 默认是否合理由 S05 实测验证。OQ3 family-profile 阈值（0.02 / 0.999）仍统一，未按 K/V 拆分。
- **manifest.jsonl 路径与 v1 路径同盘符**：默认 `$THUNDEROMLX_KVTC_HOME = ~/.omlx/cache/kvtc_v2`，与 v1 `~/.omlx/cache/kvtc_calibrations` 同盘；磁盘满时两者会互相影响。生产部署建议 ops 显式设置 `THUNDEROMLX_KVTC_HOME` 到独立卷。
- **`paged_ssd_cache` mix-basis tolerance 删除**：原先「`len(feature_dims) > 2` silently skip」改为 WARN + return False；如果上游 cache_data 中确实有混 family block（例如旧训练流水线），现在会大量 lz4 fallback，主服务延迟可能上升（KV 写盘体积增大）。这是预期收益（防止 silent .kvtc 损坏），但需要监控。
- **legacy v1 calibration 读路径无 GC**：M1 设计了 7 天保留窗口，但本 sprint 未实现 cron / scheduled 清理。`load_legacy` 仅记 warn，需 S05/ops 后续监控 `legacy_calibration_read_count` 指标决定何时手动 prune。

## 后续待办

1. **本 sprint**：协调器将状态从 `active/planning_complete/builder_main` 推到 `reviewing/builder_done/evaluator`；等审判官评估。
2. **审判官**：跑 `solar-harness session evaluate sprint-…s03-core-runtime --json`，按 contract.md acceptance + plan §5 验证 A/B/C/D/E/F/G/H/I/J 全集 + plan §6 no-live-pane / §7 Rollback 复检；重点抽样：(a) 22 pytest 实际通过；(b) `paged_ssd_cache.py` diff 仅 KVTC 区域；(c) `force_kvtc` 不通过 env 暴露；(d) `recon_gate.evaluate` 签名钉死；(e) `kvtc_version="2"` header 出现；(f) 5 个错误类层级与 S02 A3 §错误类层级 1:1。
3. **PASS 后**：epic_decomposer 检查 S04 状态（如果尚未开始，激活 S04_orchestration_ui）；S05_verification_release 现已 ready（依赖 S03 已 passed）。
4. **S04 round-1**：必须 `from omlx.cache.kvtc_errors import ...`；任何 server.py 路由改动只允许在 `/v1/cache/prompt/save` 上（per A3 API 6a/6b）；不允许碰 cache/ 目录任何文件。
5. **S05 round-1**：必须 `from omlx.cache.kvtc_recon_gate import evaluate, ReconGateMeta`；ab_correctness 升级时 import 现有 `encode_block_to_bytes / decode_block_from_bytes` 仍可用（公开 API 不变）；CI YAML 新建。
6. **epic 关闭门禁**：S04 + S05 全部 passed 后 parent-check `ready=true` 才允许 epic close。
