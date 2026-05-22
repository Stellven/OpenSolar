# Design — S03 Core-Runtime 切片：KVTC 核心实现与数据模型

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime`
slice: `core-runtime`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T08:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream_passed: `S02_architecture (passed/completed 2026-05-22T08:39:39Z, 7 architecture artifacts + traceability.json)`

## 0. 本切片的边界（强制 read-first）

- **本 sprint 第一次允许 builder Write/Edit ThunderOMLX 业务代码**，但严格限制在以下路径（per S02 A1 source_archeology）：
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_codec.py`
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_calibration_store.py`
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/paged_ssd_cache.py`（仅 KVTC 区域：lines 395-466 metadata + 1604-1998 KVTC IO）
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_errors.py`（新建）
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_recon_gate.py`（新建）
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_tools_recalibrate.py`（新建，或同等路径）
  - `/Users/lisihao/ThunderOMLX/tests/kvtc/test_*.py`（新建）
- **严格禁止** 触碰：
  - `/Users/lisihao/ThunderOMLX/src/omlx/server.py`（属 S04）
  - `/Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py`（属 S05）
  - 任何 UI / frontend 路径（属 S04）
  - 任何 `.github/workflows/`（属 S05）
  - 任何 `paged_ssd_cache.py` 非 KVTC 区域代码（行号区间外）
- 禁止 `tmux send-keys`、`solar-harness restart`、动 `~/.solar/STATE.md`、动 epic.*、动 S01/S02 artifacts。
- 禁止用乐观词；禁止放宽 hard 阈值（p95_rel_rmse ≤ 0.02、min_cos ≥ 0.999）；禁止异步化 codec encode 路径；禁止把 `force_kvtc` 暴露到 env / model card。

## 1. 上游摘要（S02 → S03）

S02 已交付 7 个架构 artifact + traceability.json。S03 必须 1:1 消费 handoff brief 中 8 项 expected_output：

| # | S02 handoff | S03 节点 | S03 实施物 |
|---|-------------|----------|-----------|
| 1 | error class hierarchy (`omlx.cache.kvtc_errors`) | B0 | 新文件 `kvtc_errors.py` 含 8 个 exception 类 |
| 2 | `kvtc_calibration_store.py` 5-dim key + manifest.jsonl + v1 read-only | B1 | 修 `kvtc_calibration_store.py` |
| 3 | `kvtc_recon_gate.py` evaluate() + ReconResult/Metrics | B2 | 新文件 `kvtc_recon_gate.py` |
| 4 | `paged_ssd_cache.py` Schema 4 v2 fields + kvtc_version=2 | B3 | 修 `paged_ssd_cache.py` lines 395-466 + 1604-1998 |
| 5 | `kvtc.tools.recalibrate` CLI | B4 | 新文件 `kvtc_tools_recalibrate.py` + `__main__` |
| 6 | `kvtc_codec.py` encode 入口加 classifier + recon_gate hook + sink/recent + K/V 独立 config + env switches | B5 | 修 `kvtc_codec.py` |
| 7 | 22 pytests pass (N2-A1..A7 + N3-A1..A8 + N4-A1..A7) | B6 | 新 `tests/kvtc/test_calibration_key.py` + `test_family_classifier_bypass.py` + `test_reconstruction_gate.py` |
| 8 | S03 → S04/S05 handoff brief + traceability | B7 (join) | 新 `<s03-sid>.handoff.md` + `.traceability.json` |

## 2. 系统视图（哪个文件什么变化）

```
omlx/cache/                                      （S03 写范围）
├── kvtc_errors.py            [B0 NEW]            8 exception classes
├── kvtc_calibration_store.py [B1 MODIFY]         5-dim key, manifest.jsonl, v1 read-only
├── kvtc_recon_gate.py        [B2 NEW]            evaluate() + ReconResult + ReconMetrics
├── kvtc_tools_recalibrate.py [B4 NEW]            __main__ CLI
├── paged_ssd_cache.py        [B3 MODIFY]         metadata v2 + kvtc_version=2 header + sideband
└── kvtc_codec.py             [B5 MODIFY]         encode 入口 = classifier → calibration_lookup
                                                  → encode → recon_gate.evaluate → accept|fallback
                                                  + sink/recent + K/V independent config
                                                  + env: THUNDEROMLX_KVTC_DISABLE / *_FORCE_LEGACY*

tests/kvtc/                                       （S03 写范围）
├── test_calibration_key.py    [B6 NEW]           N2-A1..A7  (7 cases)
├── test_family_classifier_bypass.py [B6 NEW]     N3-A1..A8  (8 cases)
└── test_reconstruction_gate.py [B6 NEW]          N4-A1..A7  (7 cases)
                                                  Total: ≥22 pytests
```

下游不动（属其他 sprint，禁止改）：
- `src/omlx/server.py`、`scripts/kvtc_ab_correctness.py`、`.github/workflows/`、任何 UI / frontend。

## 3. 数据流（runtime, post-fix）

```
inference_loop
   │
   ▼
codec.encode(tensor, meta=ClassifierMeta(layer_type, head_dim, num_heads,
                                          num_kv_heads, dtype, rope_state, op_kind),
             sink_tokens=4, recent_window=64, force_kvtc=False)
   │
   ├─ env THUNDEROMLX_KVTC_DISABLE? → 直接 lz4_fallback (reason=disabled_by_env)
   ├─ family_classifier(meta) → family
   │     └─ family ∈ {mamba-like, hybrid, unknown}: → lz4_fallback (reason=family_not_supported)
   ├─ slice sink + recent → side-band raw bytes (lossless)
   ├─ calibration_store.lookup(5-dim key)
   │     └─ miss: → lz4_fallback (reason=calibration_miss)
   ├─ kvtc encode middle segment via per-family-per-shape basis
   ├─ candidate decode in temp buffer
   ├─ recon_gate.evaluate(meta, decoded, expected) → ReconResult
   │     └─ decision=lz4_fallback: → 丢弃 candidate，整段 lz4_fallback
   ├─ EncodedBlock { decision=kvtc_accept, payload, sideband, metrics, family, shape_sig, ... }
   ▼
paged_ssd_cache.write_block(block_id, kvtc_payload, sideband, decision_meta)
   └─ append to logs/recon_gate.jsonl (1 line)

decode read path:
paged_ssd_cache.read_block(block_id) → ConcatenatedKV
   └─ side-band sink + codec.decode(kvtc payload) + side-band recent → concat
```

## 4. 关键设计决策（钉死）

1. **错误类绝对路径** `omlx.cache.kvtc_errors`；S04/S05 import 时统一从该模块（per S02 A3）。
2. **5 维 calibration key**：`model_id | tensor_family | shape_signature | layer_type | rope_state`（per N2 BNF）。
3. **manifest.jsonl** 路径合同：`$THUNDEROMLX_KVTC_HOME/calibration/v2/manifest.jsonl`；`$THUNDEROMLX_KVTC_HOME` 默认 = `~/.omlx/cache/kvtc_v2`（S03 选定，可被 env override）。
4. **v1 旧路径** read-only：`~/.omlx/cache/kvtc_calibrations/{16hex}.safetensors` 保留 7 天，每次读发 `legacy_calibration_key_read` warn log。
5. **K/V 独立 config**：拆 `KVTCCodecConfig` 为 `{k_config: KVTCCodecConfig, v_config: KVTCCodecConfig}`，默认 `k_config.bits=6 / v_config.bits=6`（暂统一，per OQ3 tentative）；K/V plan 已分离（A1 确认）。
6. **recon_gate API 签名钉死**：`evaluate(meta, decoded, expected) -> ReconResult`；签名冻结 ≥1 epic 周期；阈值越界**不抛**异常（设计选择：返回 `decision=lz4_fallback`）。
7. **encode 同步串行**：禁止异步化；任何 IO（manifest/jsonl 写）允许 buffered/append-only 但**不允许跨 await**。
8. **临时 buffer 物理保证**：抽样 decode 在 numpy temp array；任一路径回退 lz4 时绝不写 paged_ssd_cache（N4-A7）。
9. **paged_ssd_cache header v2** 新字段：`kvtc_version="2"`、`tensor_family`、`shape_signature`、`layer_type`、`rope_state`、`kv_sideband_raw_offset / _length`；v1 header (`kvtc_version="1"`) 仍可读，但不允许新写。
10. **env switches**（在 codec encode 入口拦截）：
    - `THUNDEROMLX_KVTC_DISABLE=1` → 全 family 立即 lz4
    - `THUNDEROMLX_KVTC_FORCE_LEGACY_CALIBRATION=1` → calibration_store.lookup 走旧 v1 路径
    - `THUNDEROMLX_KVTC_HOME` → 新 v2 落盘根目录（无默认硬编码业务路径）

## 5. 测试矩阵（B6 必跑 ≥22 cases）

| 文件 | cases | 来源 | 说明 |
|------|-------|------|------|
| `tests/kvtc/test_calibration_key.py` | 7 | N2-A1..A7 | 5 维 key 校验 + legacy 读 + manifest 写 |
| `tests/kvtc/test_family_classifier_bypass.py` | 8 | N3-A1..A8 | classifier closure + sink/recent + force_kvtc + hybrid |
| `tests/kvtc/test_reconstruction_gate.py` | 7 | N4-A1..A7 | 阈值 + fallback + jsonl schema + 临时 buffer |

测试必须：

- 使用 **synthetic 张量**（不依赖真实 Qwen3.6 权重；real-block A/B 属 S05）。
- 全 24 cases 都可在 `pytest` 普通 CPU 跑（≤ 30s 总耗时）。
- 覆盖 happy path + error path（每个具名 exception 至少 1 个 test）。
- 不依赖 `$THUNDEROMLX_KVTC_HOME` 真实目录：使用 `tmp_path` fixture。
- 不允许 mock recon_gate.evaluate；阈值校验必须真跑 numpy 计算。

## 6. 状态机（runtime + persistent state）

- **codec.encode 内部**：classifier → lookup → encode → gate → accept|fallback，**同步串行**（per N4 Stop Rule）。
- **calibration_store**：v1 read-only + v2 read-write；写路径必须 fail-closed 校验 5 维 key。
- **manifest.jsonl**：append-only；每条决策成功写入 basis 时追加 1 行；不允许整文件重写。
- **recon_gate.jsonl**：append-only；每次 encode 决策追加 1 行（accept 或 fallback 都写）。

## 7. 失败恢复（详见 S02 A6，本 sprint 实施）

S03 实施时必须把 S02 失败模式表（≥9 行）逐项落地到代码 + jsonl log：

- F1 family=unknown → lz4 fallback (reason=unknown_family)
- F2 calibration_miss → lz4 fallback (reason=calibration_miss)
- F3 recon_threshold_violation → lz4 fallback (reason=recon_threshold_violation)
- F4 recon_gate_exception → lz4 fallback (reason=recon_gate_exception:<cls>)
- F5 force_kvtc + unsupported family → `ForceKVTCUnsupportedFamilyError` (critical)
- F6 legacy v1 calibration 读 → `legacy=True` + warn
- F7 invalid tensor (NaN/Inf/非 2D) → `InvalidTensorError`
- F11 env DISABLE=1 → 全 family lz4 (reason=disabled_by_env)
- F12 env FORCE_LEGACY=1 → 走 v1 calibration（仅供紧急对照）

## 8. 观测（详见 S02 A6）

- 所有失败 → recon_gate.jsonl 落盘（per Schema 6 / N4-A5 全 14 字段）
- 主要指标（S03 不实现 dashboard，只产生原始数据，dashboard 属 S04/运维）：
  - `kvtc_accept_rate` = `decision=kvtc_accept` 占比
  - `lz4_fallback_rate_by_reason`
  - `legacy_calibration_read_count`
  - `force_kvtc_attempts` / `_blocked_count`

## 9. 兼容性（详见 S02 A5，本 sprint 实施）

| 项 | 兼容动作 |
|----|----------|
| `kvtc_codec.KVTCTransformPlan.encode/decode` 旧签名 | 保留（公开 API 不破坏）；新 `kvtc.codec.encode(tensor, meta, ...)` 是 module-level 包装入口 |
| `KVTCCalibrationStore.save/load/get_or_fit` | 保留旧方法签名；新增 5 维 key 方法 `lookup_v2 / write_v2`；旧 `_model_key` 仅 read-only fallback |
| `paged_ssd_cache.save_block/load_block` | 保留方法名 alias；header 内部 `kvtc_version="2"` 切换；旧 `kvtc_version="1"` 仍可读 |
| `encode_block_to_bytes / decode_block_from_bytes` | 保留（S05 ab_correctness.py 还在用）；底层切到新路径但顶层签名不变 |
| `~/.omlx/cache/kvtc_calibrations/` 旧路径 | read-only 7 天保留期 |
| `$THUNDEROMLX_KVTC_HOME` env | 默认 `~/.omlx/cache/kvtc_v2`；不强制 ops 改环境 |

## 10. 冲突 / 依赖 / 降级

**冲突**：

- `paged_ssd_cache.py:1785-1795` 旧"允许 ≤2 distinct feature_dims"逻辑 vs N3 决策表「unknown/hybrid → lz4」→ B3 必须删除该容错或改为严格 lz4 fallback。
- `KVTCCodecConfig` 单实例 K/V 共享 → B5 拆 `k_config / v_config`，可能影响现有调用方（A/B 脚本、单测）→ 必须保留旧 API 别名。
- 旧 1 维 calibration key 与新 5 维同存 → B1 必须按 fingerprint 标记 `legacy=True` 而非全量删除。

**依赖**：

- B1/B2/B3/B4 全部依赖 B0（错误类 import）
- B5 依赖 B1（calibration lookup）+ B2（recon_gate）+ B3（paged_ssd_cache sideband 字段）
- B6 测试依赖 B0..B5 全部实现
- B7 join 所有

**降级**：

- 若 B5 实施期发现 `KVTCSharedCalibration` 重构破坏 `kvtc_ab_correctness.py` 现有 import → 立即 round-2，不允许 silent break
- 若 B6 pytest 任一 case 失败 → S03 不许 passed，必须 round-2 修
- 若 mirage 知识库持续 degraded → 不影响 B0..B6（实现依赖代码 + S01/S02 文档，已 self-contained）

## 11. 非目标（明确禁止 S03 builder 越权）

- 不修 `server.py`（S04）
- 不修 `scripts/kvtc_ab_correctness.py`（S05）
- 不写 UI / frontend / i18n 资源（S04）
- 不写 `.github/workflows/`（S05）
- 不真实跑 `scripts/kvtc_ab_correctness.py`（即使是验证用；属 S05 范围）
- 不动 epic.* / S01/S02 任何 artifact / ~/.solar/STATE.md
- 不打开 live tmux pane / 不重启 harness
- 不放宽 hard 阈值（0.02 / 0.999）
- 不暴露 `force_kvtc` 到 env / model card
- 不在 paged_ssd_cache.py 内嵌 decode（必须委托给 codec.decode）
- 不异步化 codec encode 路径
- 不使用乐观词

## 12. 给 S04/S05 的接力清单（B7 输入要点）

- **S04**（依赖 S03 完成）：
  - 公共 import：`from omlx.cache.kvtc_errors import (...)`
  - UI `GET /api/kvtc/state` 数据源 = `reports/kvtc-ab/<ts>/ab_correctness.summary.json`（S05 产生，S04 渲染）
  - `/v1/cache/prompt/save` 修 or 410：双签名由 S04 决策（S03 不动 server.py）
  - env 切换 `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED`（S04 实现）
- **S05**（依赖 S03 完成）：
  - 调用 `kvtc.recon_gate.evaluate(meta, decoded, expected)` 在 `kvtc_ab_correctness.py`
  - 读 `recon_gate.jsonl`、`manifest.jsonl` 做 CI 断言（per Schema 1 / 2）
  - 5×3 覆盖矩阵 fixture 由 S05 准备；S03 不真实跑
  - CI YAML 与 ATLAS hook 由 S05 注册；S03 不写
