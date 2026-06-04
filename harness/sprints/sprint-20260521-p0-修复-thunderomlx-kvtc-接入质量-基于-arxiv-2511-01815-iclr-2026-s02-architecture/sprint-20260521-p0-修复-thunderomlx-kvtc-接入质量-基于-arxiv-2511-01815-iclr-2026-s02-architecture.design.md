# Design — S02 Architecture 切片：KVTC 接入质量修复 · 架构设计与接口契约

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture`
slice: `architecture`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T06:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream_passed: `S01_requirements (passed/finalized 2026-05-22T06:40:29Z, 7 matrices + traceability.json + traceability_map.md)`

## 0. 本切片的边界（强制）

- 本 sprint 是 **架构设计 + 接口契约**，**不写任何业务代码**（与 S01 `not_in_scope` NIS1..NIS10 完全一致）。
- 允许 builder **read-only** 扫描 ThunderOMLX 源码（`/Users/lisihao/ThunderOMLX/...`）以填 S01-N1 中 7 个 `[TBD-S02 read]` 标记；**不允许任何 Write/Edit 到 ThunderOMLX 仓库**；不允许 `pytest` / `curl /v1/...` / 跑 `kvtc_ab_correctness.py` / 启动主服务。
- 写范围严格限于 `sprints/<s02-sid>.architecture.*.md` 与 `sprints/<s02-sid>.architecture.*.json`；不动 `~/.solar/STATE.md`、不动 epic.*、不改 S01 任何 artifact。
- 输出 = **架构合同**，由 S03/S04/S05 各自的 planner+builder 实施。S02 必须使每个 S01 R1..R7 的下游 owner 拿到「足够实施的合同」。

## 1. 上游摘要（S01 → S02）

S01 已交付 7 个需求矩阵 + 1 个 traceability 包；S02 必须 1:1 消费：

| S01 矩阵 | 主交付 | S02 必须解决 |
|----------|--------|--------------|
| N1 paper_alignment | 7 项 audit gap，含 7 个 `[TBD-S02 read]` | A1：通过实际读 ThunderOMLX 源码补全；A2/A3 据此设计组件边界 |
| N2 calibration_key | 5 维 key BNF + 迁移策略 + 回滚 | A3 接口契约（calibration_store 公共 API）+ A4 manifest jsonl schema + A5 v1→v2 迁移 |
| N3 family_classifier_bypass | 5 类 family + 决策表 + sink/recent + side-band | A3 codec encode 入口签名 + A4 side-band 字段 + A2 codec/cache 边界 |
| N4 reconstruction_gate | 抽样流程 + 阈值 + jsonl log + 公共 API `evaluate(meta, decoded, expected)` | A3 接口契约 + A4 jsonl schema + A6 observability + A5 临时 buffer 不落 cache 的 IO 路径设计 |
| N5 named_prompt_cache_422 | 422 root cause 假设 + 修/禁决策树 + 410 文案 | A3 server route 契约 + A5 API compat（保留 410 替代）+ A6 telemetry |
| N6 ci_regression_gate | 5×3 覆盖矩阵 + SLO + CI hook 位置 | A4 ab_correctness.summary.json schema + A6 CI artifact 落盘合同 |
| N7 ui_default_off_gate | 4 状态机 + 数据源决策（复用 N6 artifact）+ 文案 | A3 UI 数据源契约（`THUNDEROMLX_KVTC_UI_AB_SOURCE`）+ A4 ab_summary schema + A5 UI feature flag |

OQ1..OQ4：S02 必须给出 architecture-level 倾向（仍保留 S03/S04/S05 最终决策权）。

## 2. 系统分层（Control Plane / Data Plane / State / Observability）

```
┌──────────────────────────── Control Plane ────────────────────────────┐
│  UI Gate (N7 state machine, default_off)                              │
│   ├── 读 A/B summary 路径（env-overrideable）                         │
│   ├── 订阅 recon_gate FAIL 事件 → auto-block_by_gate_fail             │
│   └── Feature Flag: THUNDEROMLX_KVTC_DISABLE / *_FORCE_LEGACY / etc   │
│  Server Routes                                                        │
│   ├── /v1/cache/prompt/save  ← 修 or 禁用(410) 决策由 S04 选          │
│   └── /v1/cache/prompt/*     ← 其他路径不动                           │
└────────────────────────────────────────────────────────────────────────┘
                              │ env / flag / route 配置下发
                              ▼
┌──────────────────────────── Data Plane ───────────────────────────────┐
│  Inference Loop                                                       │
│   ├── KVTC Codec (encode entry = classifier → calibration_lookup →    │
│   │     kvtc_encode → recon_gate.evaluate → accept|fallback)          │
│   ├── PagedSSDCache (写: 主体 + sideband; 读: side-band prefix concat) │
│   └── Calibration Store (v2 5 维 key 写, v1 read-only)                │
│  Tools                                                                │
│   └── kvtc.tools.recalibrate (离线 CLI; S03 实现)                     │
└────────────────────────────────────────────────────────────────────────┘
                              │ jsonl / json artifact
                              ▼
┌────────────────────────── State / Observability ─────────────────────┐
│  $THUNDEROMLX_KVTC_HOME/                                              │
│   ├── calibration/v2/<vendor>/<model>/<rev>/<family>/<shape>/...      │
│   │     ├── basis.npz  (per N2-A6)                                    │
│   │     └── (read-only) calibration/v1/<model>/basis.npz              │
│   ├── calibration/v2/manifest.jsonl                                   │
│   ├── logs/recon_gate.jsonl                                           │
│   └── profiles/recon_gate.json                                        │
│  reports/kvtc-ab/<ts>/                                                │
│   ├── ab_correctness.summary.json                                     │
│   ├── recon_gate.jsonl                                                │
│   └── per_fixture/*.json                                              │
│  Alerts                                                               │
│   ├── ATLAS hook: atlas.kvtc.recon_gate_repair (N6-A5)                │
│   └── PagerDuty/issue: kvtc-regression / kvtc-watchlist (N6 hard/soft)│
└───────────────────────────────────────────────────────────────────────┘
```

## 3. 模块/组件分工（A2 输入）

| 组件 | 责任 | 源文件（A1 待补全） | 上游契约 | 下游契约 |
|------|------|---------------------|----------|----------|
| `kvtc_codec` | encode/decode + classifier 入口 + recon_gate hook | `/Users/lisihao/ThunderOMLX/.../kvtc_codec.py` | calibration_store.lookup, paged_ssd_cache.write_sideband | server inference loop / paged_ssd_cache 主体 |
| `kvtc_calibration_store` | 5 维 key v2 写，v1 read-only，manifest jsonl 追加 | `/Users/lisihao/ThunderOMLX/.../kvtc_calibration_store.py` | offline fit 工具 | codec.lookup |
| `paged_ssd_cache` | 主体 .kvtc + sideband 分离落盘；decode 时按顺序拼接 | `/Users/lisihao/ThunderOMLX/.../paged_ssd_cache.py` | codec.write_block | inference loop 读路径 |
| `kvtc.recon_gate` | 抽样 + 阈值 + jsonl 写盘；公共 API `evaluate()` | 新模块（S03 创建） | codec encode | S05 ab_correctness.py 导入 |
| `kvtc.tools.recalibrate` | 离线 re-fit CLI | 新 CLI（S03 创建） | calibration_store v1 read + v2 write | 运维 |
| `server.routes.cache.prompt` | /v1/cache/prompt/save 修 or 410 禁用 | `/Users/lisihao/ThunderOMLX/.../server*.py` | inference KV capture hook | UI |
| `frontend.ui.kvtc_gate` | N7 4-state state machine + i18n | `/Users/lisihao/ThunderOMLX/.../ui/*` 或独立 web/ | A/B summary 数据源 + feature flag | 用户 |
| `scripts/kvtc_ab_correctness.py` | 5×3 覆盖 + jsonl emit + report dir | `/Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py` | recon_gate.evaluate | CI |
| `.github/workflows/kvtc-regression.yml` | CI pre-merge job | （A1 确认 CI 文件实际位置） | scripts/kvtc_ab_correctness.py | 仓库 PR check |

`[TBD-S02 read]` 标记 7 项必须被 A1 节点替换成具体文件路径 + 函数名 + 行号区间，禁止留空。

## 4. 接口契约（A3 输入要点）

S02 必须把以下 API 写为「Builder 可直接落地的签名」，并以表格 + 例子形式落到 `<sid>.architecture.interfaces.md`：

1. **`kvtc_codec.encode(tensor, meta, *, sink_tokens=4, recent_window=64, force_kvtc=False, sideband_dtype=None) -> EncodedBlock`**
   - `meta`：必须含 N3-A2 7 元组 `(layer_type, head_dim, num_heads, num_kv_heads, dtype, rope_state, op_kind)`
   - 返回 `EncodedBlock { decision: "kvtc_accept"|"lz4_fallback", payload, sideband, reason, metrics }`
   - 失败语义：异常永远转 lz4，绝不向上抛
2. **`kvtc.recon_gate.evaluate(meta, decoded, expected) -> ReconResult`**（N4-A6 钉死）
3. **`kvtc_calibration_store.lookup(key_tuple) -> Basis | None`** + `write(key_tuple, basis, *, manifest_meta) -> None`
4. **`paged_ssd_cache.write_block(block_id, *, kvtc_payload, sideband, decision_meta) -> None`** + `read_block(block_id) -> ConcatenatedKV`（顺序：sink → kvtc decoded → recent）
5. **HTTP `POST /v1/cache/prompt/save`**：修分支 = 对齐 pydantic schema + 鉴权前置；禁用分支 = `410 Gone` + N5 统一错误体
6. **UI 数据源**：`GET <ui-state>/kvtc/state` → 4 状态 + 最近 A/B summary 摘要；`THUNDEROMLX_KVTC_UI_AB_SOURCE` 切源

接口契约必须明确：

- 同步/异步语义（推理路径强制同步；CLI 工具异步）
- 错误类层级（`CalibrationKeyIncompleteError`, `ClassifierInputIncompleteError`, `ReconGateException`, `InvalidTensorError`）
- 兼容性承诺（公共 API 一旦发布，S03 不得在本 epic 内 break）

## 5. 数据模型（A4 输入要点）

S02 必须在 `<sid>.architecture.data_models.md` + `<sid>.architecture.data_models.schemas/`（不创建实际目录，仅描述）中给出完整 schema：

- `calibration/v2/manifest.jsonl`（jsonl，每行一条）：N2-A6 + sha256 + fitted_at + sample_count + tool_version
- `logs/recon_gate.jsonl`：N4-A5 14 字段全集
- `reports/kvtc-ab/<ts>/ab_correctness.summary.json`：N6-A7 + N7-A3 UI 渲染合同 7 个字段
- `paged_ssd_cache` 块格式扩展（兼容 v1）：新增 `sideband` 字段名 `kv_sideband_raw`（N3-A6），保留旧字段不删
- `EncodedBlock` Python dataclass / TypedDict（in-process）
- `kvtc.recon_gate.ReconResult` dataclass（含 metrics + decision + reason）
- `ui/kvtc/state` 响应 schema（4 状态 + 最近 summary 引用）

每个 schema 必须含：版本号、字段列表、必填/可选、变更策略。

## 6. 状态机（State）

- **UI**：N7-A1 4 状态闭包（default_off / preview / enabled / blocked_by_gate_fail），状态迁移由 recon_gate + 用户操作 + feature flag 三源驱动。
- **Codec encode 内部**：classifier → calibration_lookup → encode → recon_gate.evaluate → accept|fallback，**必须同步串行，不允许异步**（N4 Stop Rule）。
- **Calibration store**：v1 read-only / v2 read-write（写入校验 5 维），不允许 v1 写。

## 7. 失败恢复（Failure Recovery，A6 输入要点）

| 失败模式 | 检测点 | 自动恢复动作 | 人工 escalation |
|----------|--------|--------------|-----------------|
| `tensor_family=unknown` | classifier | lz4 fallback + `reason=unknown_family` | 无（设计内） |
| `calibration_miss` | calibration_store.lookup | lz4 fallback + `reason=calibration_miss` | 触发离线 re-fit（运维或 nightly） |
| `recon_threshold_violation` | recon_gate.evaluate | lz4 fallback + 记录 jsonl + 临时 buffer 释放 | 若同 fixture 连续 3 次 → ATLAS `atlas.kvtc.recon_gate_repair` |
| `recon_gate_exception` | except 分支 | lz4 fallback + `reason=recon_gate_exception:<cls>` | 高优先级 issue + ATLAS |
| `force_kvtc unsupported_family` | encode kwargs 校验 | RuntimeError + log critical | 阻断 PR |
| 422 → 410 切换后客户端仍调用 | server middleware | 返回 410 + 统一错误体 | UI 灰态 + tracking_sprint 显示 |
| UI 读 A/B summary 失败 | UI 数据源 | 维持 default_off + banner | 检查 reports/ 路径 |
| Feature flag global off | UI / codec env | 全 family 直接 lz4 + UI banner | 运维通告 |
| 旧 v1 calibration 残留 | calibration_store.lookup 读旧路径 | `legacy=True` warn + 强制走 recon_gate | re-fit 完成后清理 |

所有失败 → 必须 jsonl 落盘 + 不污染 paged_ssd_cache（N4-A7 物理保证）。

## 8. 观测（Observability，A6 输入要点）

- **结构化日志**：所有决策点 → `logs/recon_gate.jsonl`（per-block） + server-side log（per-request）
- **指标**：`p95_rel_rmse`、`min_cos`、`kvtc_accept_rate`、`lz4_fallback_rate_by_reason`、`legacy_calibration_read_count`、`force_kvtc_attempts`
- **追踪**：每个 encode 请求附 `block_id`（与 paged_ssd_cache 同），便于 UI/CI/服务端串联
- **告警**：
  - hard SLO 越界 → CI FAIL → issue `kvtc-regression`
  - soft SLO → issue `kvtc-watchlist`
  - 任一 `decision=kvtc_accept` + `min_cos < 0.999` → 立即 hard FAIL（无 soft 缓冲）
  - 连续 3 次同 fixture FAIL → ATLAS structured repair
- **UI 可见**：N7-A3 `slo`、`summary`、`named_prompt_cache_status` 字段在 UI 直显，不允许隐藏

## 9. 兼容性与迁移（Migration，A5 输入要点）

| 项 | 兼容策略 | 迁移路径 | 回滚 |
|----|----------|----------|------|
| calibration v1 → v2 | v1 read-only 7 天 + deprecation log；新写 fail-closed 拒收旧 key | `kvtc.tools.recalibrate --model <id> --revision <sha>` 扫描重 fit | `THUNDEROMLX_KVTC_FORCE_LEGACY_CALIBRATION=1` 临时回 v1 |
| paged_ssd_cache 旧块（无 sideband） | 读路径 sideband 缺省 = None，按旧路径直接解 | 不强制重写旧块；新写均含 sideband | 无需，旧块永远可读 |
| `/v1/cache/prompt/save` 422 → 修 or 410 | 任一分支保留 feature flag `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` | 默认 0（禁用）；修复完成 = 1 + N6 success_rate ≥ 95% 7 天后切默认 1 | env=0 即时回禁用 |
| UI default_off 强制 | 任何升级首装均 default_off；自动门禁触发也 → blocked | 升级路径不允许直跳 enabled；旧用户已 enabled 状态 → 强制走 preview 一次 | feature_flag_off 全局直接 default_off |
| `recon_gate.jsonl` 字段扩展 | 字段集只可加不可删；新增字段对老 consumer 可选 | S03 实现后向兼容写；S05 校验保 v1 字段集 | 还原 codec 版本即可 |
| `kvtc.recon_gate.evaluate` 公共 API | 签名稳定；新 kwargs 必须默认值兼容 | 不允许 break call site | 还原 codec 版本 |

## 10. 冲突 / 依赖 / 降级（PRD 验收第 3 条）

**冲突**：

- N5「禁用」分支 vs N6「named prompt cache fixture stable-ci」：S02 必须明确 N5=禁用 时 N6 fixture 走 `mocked-pending-stable`，CI WARN 不 FAIL（N6-A6 已钉死）。S02 A3 接口契约必须显式同步两侧。
- N3 `force_kvtc=True` vs N7 UI gate：S02 必须把 `force_kvtc` 锁死在 kwargs 层，禁止 env / model card 暴露；UI 也不允许给该 kwarg 入口（N3-A7 优先级表 + N7 Stop Rule）。
- v2 calibration 与 v1 共存的目录冲突：S02 必须规定 v2 严格在 `calibration/v2/` 子树，禁止与 v1 文件名碰撞。

**依赖**：

- S03 实施 → 依赖 S02 全部 7 个 artifact
- S04 实施 → 依赖 S02 A3 (interfaces) + A4 (data_models) + A5 (migration: server compat + UI feature flag)
- S05 实施 → 依赖 S02 A3 (`kvtc.recon_gate.evaluate` API) + A4 (recon_gate.jsonl + ab_summary schemas) + A6 (CI artifact 路径)
- 各 sprint 内部 round-N 修复 → 全部回到 S02 A7 handoff brief 重读

**降级**：

- 任一接口契约缺失 → S03/S04/S05 builder 立即停在 graph_node_dispatch，要求 S02 round-2
- 任一 schema 版本号缺失 → CI artifact 不可消费 → N6 hard FAIL（已设计）
- 知识库 mirage degraded 持续 → A1 source archeology 必须独立完成（直接 read repo），不依赖检索；A2..A7 设计文档保持 self-contained 不依赖外链

## 11. 非目标（明确禁止 S02 builder 越权）

- 不修任何 `*.py / *.ts / *.js / *.sh / *.yaml` 业务代码（S01 NIS1..NIS6 同样适用）
- 不真实跑 pytest / `scripts/kvtc_ab_correctness.py` / curl ThunderOMLX HTTP API
- 不真实创建 `$THUNDEROMLX_KVTC_HOME/calibration/v2/` 任何目录或落盘 basis.npz
- 不动 `~/.solar/STATE.md`、不动 epic.*、不改 S01 任何 artifact
- 不打开 live tmux pane、不重启 harness、不动主服务 cache
- 不在 architecture 文档使用 "已修复 / 稳定 / 完美 / 无需担忧" 等乐观词（S01 builder_forbidden_aggregate 规则）
- 不放宽 hard 阈值（p95_rel_rmse ≤ 0.02、min_cos ≥ 0.999）；如需调严必须新增 acceptance row

## 12. 给 S03/S04/S05 的接力清单（A7 输入要点摘要）

- S03_core_runtime：实现 `kvtc_codec.encode` 入口（含 classifier / recon_gate / sideband）、`kvtc_calibration_store` v2 写 + v1 read-only、`paged_ssd_cache` sideband 字段扩展、`kvtc.recon_gate.evaluate` 公共 API、`kvtc.tools.recalibrate` CLI、env 开关
- S04_orchestration_ui：决策 N5（修 or 禁用）并实现；UI 4 状态机 + i18n + 最近 A/B summary 渲染 + 自动 block_by_gate_fail + feature flag
- S05_verification_release：扩 `scripts/kvtc_ab_correctness.py` 12+ stable-ci fixtures + 5×3 矩阵 + hard/soft SLO + CI YAML + jsonl emit + ATLAS hook 注册

每个下游 sprint 必须从本 sprint A7 handoff brief 中拿到「输入文件 + 期望输出 + 禁止动作 + 验证证据计划」四元组。
