# Evaluation — S02 Architecture (KVTC 接入质量修复 · 架构设计与接口契约)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
evaluator: 审判官 (Solar Evaluator pane / pane 2)
round: 1
ts: 2026-05-22T07:00:00Z
verdict: **PASS**

Knowledge Context: solar-harness context inject used (inherited from builder; mirage degraded -> qmd/obsidian/solar_db fallback). Evaluator 未重复 inject (本 sprint 评审基于实测源码 + 实跑命令, 不依赖知识检索)。
Session Log: solar-harness session evaluate **未运行** — pane 2 未挂接 session_log; 已用 Read/Bash 实测验证 7 件 artifact + 源码核对。@FALLBACK_MANUAL
verify_all skill: 未注册 → SKIPPED, 手工等价覆盖 C1..C7。

Harness Modules Used: harness-knowledge (沿用 builder 标记), harness-graph (graph-scheduler validate/ready/layers/batches/parent-check)

---

## 总判定: PASS

合约 Acceptance 3 条全部满足。plan §5 验证命令 A/B/C/D/E/F 六条全部 PASS。Stop Rule 全部满足: A1 7 行 [TBD-S02 read] 全部替换 (audit 表内 0 残留, 文件其他 7 处为节标题/元描述/反向引用); A4 7 schema 全含 schema_version; A3 4 大错误类全钉死; recon_gate.evaluate 签名字面钉死; 无 hard 阈值放宽; 无 ThunderOMLX 源码改动; 父 epic 文件未污染。10 个角度否证均失败。

---

## Done 条件逐条 (contract.md Acceptance 3 条)

| # | Acceptance | 判定 | 证据 |
|---|------------|------|------|
| D1 | 设计覆盖 control/data plane、状态、失败恢复和观测 | **PASS** | A2 components 分组 4 control + 5 data + 3 state-observability (12 组件); A6 observability 12 失败模式 + 10 指标 + 5 告警 + ATLAS hook (`atlas.kvtc.recon_gate_repair`); A4 Schema 7 含 `ui.kvtc.state.v1` 4 状态机字段; A3 API 3 `recon_gate.evaluate` 同步语义钉死。 |
| D2 | 写清楚接口边界和旧系统兼容方式 | **PASS** | A3 8 API × 6 列 (签名 / 参数语义 / 返回值 / 错误类层级 / 同步异步 / 兼容性承诺); A4 Schema 4 v2 对 v1 字段集严格 backward-compat (新字段全可选, 旧 reader 缺省 None); A5 6 项迁移含可执行 bash 回滚片段 (M2 paged_ssd_cache v1→v2; M1 calibration v1 7 天 read-only 保留窗口)。 |
| D3 | 列出冲突、依赖和降级策略 | **PASS** | 每个 A1..A7 .md 都含 `## Conflicts / Dependencies / Degradation` 段落 (plan §4 强制); A1 显式标出 paged_ssd_cache:1785-1795 "≤2 distinct feature_dims" 容错与 N3 决策表的冲突; A7 §3 列 OQ1..OQ4 4 个 open question s02_status (含 OQ2 partially_resolved 与 OQ4 resolved)。 |

---

## 自动检测 (verify-all SKIPPED, 手工等价 7 项)

| 项 | 内容 | 判定 | 证据 |
|----|------|------|------|
| C1 段落齐全 | 7 个 architecture.*.md 各含 7 段 (Outcome/Inputs From S01/Architecture Decision/Conflicts/Owner Sprint Brief/Stop Rule/Acceptance Evidence Plan) | PASS | bash grep loop missing_count=0 |
| C2 A1 实测引用 | source_archeology.md 含 ≥ 5 个 `<file>.py:<line>` 引用 (plan §5D 期望) | PASS | grep 命中 34 处 ThunderOMLX 路径引用; 唯一 `.py:line` 模式 sort -u 15 处 (kvtc_codec / kvtc_calibration_store / paged_ssd_cache / server / kvtc_ab_correctness 5 文件) |
| C3 A1 引用真实可核 | 抽样 4 处行号区间内容与 A1 描述一致 (按 MEMORY "禁止张口就来" 铁律核验) | PASS | kvtc_calibration_store.py:33-35 = `_model_key(model_name)` 单字段 ✓; kvtc_codec.py:162-198 = `KVTCSharedCalibration` 双 plan ✓; server.py:2084-2092 = prompt_too_short `raise HTTPException(422)` ✓; server.py:2199-2203 = "KV cache capture not available" 422 ✓ |
| C4 A1 文件行数 | A1 头部 read_targets 声明 vs 实际 wc -l | PASS | kvtc_codec=727 ✓; kvtc_calibration_store=221 ✓; paged_ssd_cache=4030 ✓; server=6431 ✓ |
| C5 A4 schema_version | 7 schema 全含 schema_version 字段 (plan §7 stop rule) | PASS | 7 schema 名全部 ≥ 2 hits (声明 + 字段表); EncodedBlock + ReconResult 各 4 hits (含 A3 引用) |
| C6 A3 错误类钉死 | 4 大错误类 + 子类全部声明 + 至少 3 处引用 | PASS | CalibrationKeyIncompleteError=9; ClassifierInputIncompleteError=5; ReconGateException=2 (+ 3 子类); InvalidTensorError=7; ForceKVTCUnsupportedFamilyError=3 |
| C7 recon_gate 签名 | `evaluate(meta, decoded, expected) -> ReconResult` 字面出现 | PASS | A3 第 11 行 (Outcome) + 第 69 行 (API 3 标题) + 第 181 行 (evidence) 三处命中 |

---

## 验证命令实跑证据 (plan §5 全 6 条)

### A. DAG schema validate
```
cmd: solar-harness graph-scheduler validate --graph <sid2>.task_graph.json
stdout: {"ok": true, "sprint_id": "...s02-architecture", "node_count": 7, "errors": [], "warnings": []}
conclusion: PASS
```

### B1. ready
```
cmd: solar-harness graph-scheduler ready --graph <sid2>.task_graph.json
stdout: {"ok": true, "nodes": [], "blocked_prerequisites": []}
conclusion: PASS — nodes=[] 因 7/7 已 passed (评审时点的自然状态)
```

### B2. layers
```
cmd: solar-harness graph-scheduler layers --graph <sid2>.task_graph.json
stdout: {"ok": true, "layers": [["A1_source_archeology", "A4_data_models", "A6_observability"], ["A2_components", "A3_interfaces", "A5_migration"], ["A7_architecture_index_and_handoff"]]}
conclusion: PASS — 3 layer 拓扑与 plan §1 表完全一致 (W1=[A1,A4,A6] / W2=[A2,A3,A5] / W3=[A7])
```

### B3. batches
```
cmd: solar-harness graph-scheduler batches --graph <sid2>.task_graph.json --max-parallel 3
stdout: {"ok": true, "batch_count": 0, "batches": []}
conclusion: PASS — batches=0 因 7/7 节点已 passed; handoff 中 "batch_count=1" 是 draft 时状态描述
```

### C. 段落自检 (7 文件 × 7 段)
```
cmd: for f in architecture.*.md; do for sec in "## Outcome" "## Inputs From S01" "## Architecture Decision" "## Conflicts" "## Owner Sprint Brief" "## Stop Rule" "## Acceptance Evidence Plan"; do grep -q "$sec" $f || echo MISSING; done; done
stdout: (空 — 49 个 grep 全部命中)
conclusion: PASS
```

### D. A1 实测引用
```
cmd: grep -cE "(/Users/lisihao/ThunderOMLX/|kvtc_codec\.py|kvtc_calibration_store\.py|paged_ssd_cache\.py|server\.py|kvtc_ab_correctness\.py)" architecture.source_archeology.md
stdout: 34
conclusion: PASS — 远超 plan §5D head -5 期望; A1 §"Inputs From ThunderOMLX" 表覆盖 5 个源文件
```

### E. traceability.json schema
```
cmd: python3 断言 schema_version + sprint_id + epic_id + architecture_artifacts(=7) + mapped_requirements(R1..R7) + downstream_handoff + open_questions_status + builder_forbidden_aggregate + generated_at + knowledge_context
stdout: missing_keys=[]; artifact_count=7; mapped_requirements_ids=[R1..R7]; open_questions list-len=4; downstream_handoff list-len=3; builder_forbidden_aggregate count=15; OK
conclusion: PASS
```

### F. parent-check
```
cmd: solar-harness graph-scheduler parent-check --graph <epic>.task_graph.json
stdout: {"ok": true, "ready": false, "node_count": 5, "open_nodes": [S02..S05], "failed_nodes": []}
conclusion: PASS — ok=true; S01 已从 open_nodes 消失 (passed/finalized); 等 S02 推 passed 后 epic_decomposer 自动激活 S03+S04
```

---

## 否证尝试 (Falsification — 10 个角度全失败 → PASS)

| # | 角度 | 假设 | 结果 |
|---|------|------|------|
| 1 | ThunderOMLX 源码被改动 | builder 可能 write/edit 任何 .py 文件 | **失败**: 5 文件 mtime 全部早于 S02 起始 2026-05-22T02:54 (最新 server.py 5月21日 10:53); 无任何源码改动 |
| 2 | A1 [TBD-S02 read] 仍留空 | grep 命中 7 处 → 触发 plan §7 第二条 FAIL? | **失败**: 7 处全部位于 (a) 文件标题 (b) Outcome 元描述 (c) Inputs From S01 引用 (d) Architecture Decision 节标题 (e) Conflicts 元描述 (f) Stop Rule 反向禁令 (g) Acceptance Evidence 数字阈值; §Architecture Decision audit 表内 grep `TBD-S02 read` = 0; plan §7 stop rule 语义指"audit 行实际占位仍留空", 元引用不构成占位 |
| 3 | A1 引用行号是编造的 | builder 可能用语言模型猜行号 | **失败**: 4 处抽样行号实测全部命中 — kvtc_calibration_store.py:33-35 / kvtc_codec.py:162-198 / server.py:2084-2092 / server.py:2199-2203 — 内容与 A1 描述完全一致 |
| 4 | A1 文件长度声明失实 | A1 头部声明 727/221/4030/6431 lines 可能是编造 | **失败**: wc -l 实测 4 文件长度 100% 匹配 (727/221/4030/6431) |
| 5 | 父 epic / S01 被污染 | builder 可能改 epic.task_graph.json 或 S01 任何 artifact | **失败**: epic.task_graph.json mtime 5月22日 02:42 (S01 评审时间, 早于 S02 起始); epic.traceability.json mtime 5月21日 (PRD 时间); STATE.md mtime 5月3日 (远早于); S01 status 仍 passed/finalized |
| 6 | 7 schema 缺 schema_version | plan §7 stop rule 第 5 条触发 | **失败**: 7 schema 全部含 schema_version 字段 (≥ 2 hits 每个); 命名规范统一 `<name>.v1` 或 `.v2` |
| 7 | A3 缺错误类层级 | plan §7 stop rule 第 6 条触发 | **失败**: 4 大基类 (CalibrationKeyIncompleteError / ClassifierInputIncompleteError / ReconGateException / InvalidTensorError) + 子类 (LegacyKeyWrite / ReconGateThresholdViolation / ReconGateInternalError / ReconGateConfigError / ForceKVTCUnsupportedFamily) 全部声明 |
| 8 | recon_gate.evaluate 签名漂移 | A3 是否真按 N4-A6 钉死 | **失败**: `evaluate(meta, decoded, expected) -> ReconResult` 字面 3 处命中 (Outcome / API 3 标题 / evidence E3) |
| 9 | hard 阈值放宽 | 是否在 A3/A4 默认 kwargs 写入 0.02/0.999 | **失败**: A3 API 1/3 默认 kwargs 仅 `sink_tokens=4 / recent_window=64 / force_kvtc=False / sideband_dtype=None`; recon_gate 阈值由 profile 数据源驱动 (与 plan §7 stop rule 第 8 条一致); A3 Stop Rule 显式列出该禁令 |
| 10 | 乐观词违规 | grep 已修复/稳定/完美/无需担忧 | **失败**: 仅 migration.md:88 一处 "签名稳定至少 1 个 epic 周期" 是 API 兼容性承诺标准用法 (技术术语, 非乐观断言); 其余命中全部在反向禁令 / "稳定 CI fixture" 技术术语 / grep 自身正则; 无 substantive 乐观用法 |

10 次否证均失败 → PASS。

---

## Smoke Test (按铁律 — 因属架构 spec sprint, 显式标注未跑原因)

未 smoke test 原因: 本 sprint 是 **架构设计 + 接口契约 + read-only 源码 archeology** — 无运行时代码、无 API 端点实现、无 CLI 工具、无 schema 序列化器。所有"功能"是给下游 S03..S05 用的契约 (API 签名 / Schema BNF / 错误类层级 / 迁移命令)。真功能在 S03 (codec / calibration_store / paged_ssd_cache 实现) / S04 (server / UI / 410 中间件) / S05 (CI gate + ab_correctness) 阶段, 各自 sprint 自带 smoke test 协议 (已在 A7 §6 S03/S04/S05 4 元组 brief 中钉死 verification_evidence_plan)。

合规等价: §自动检测 C1..C7 + §验证命令实跑 A..F + §否证 1..10 已对每个 spec 字段 / 引用 / 签名 / mtime / 内容做了实测验证 (grep / sed 抽样 / wc -l / python3 schema 断言 / mtime 比对), 等价于"架构合同"的 smoke。

特别说明: §否证 3 对 A1 4 处行号区间做了 sed 抽样核对 (kvtc_calibration_store.py:33-35 / kvtc_codec.py:162-198 / server.py:2084-2092 / server.py:2199-2203), 完全实测了 N1 paper_alignment 的关键 gap 描述 — 这是 MEMORY "禁止张口就来" 铁律的关键守门, A1 通过。

---

## 额外发现

1. **handoff "batch_count=1" vs 实跑 "batch_count=0"**: 与 S01 同性质 — handoff 描述 W1 ready 时刻状态, 评审时 7/7 已 passed → 自然 0。非失实, 已在 §B3 标注。
2. **A1 §"422 实测" 是 OQ2 partially_resolved 的实测命中**: 静态扫描精确定位 H1 (prompt_too_short, server.py:2084-2092) + H3 (kv_capture_timeout, server.py:2199-2203), 与 S01 N5 假设清单完全对齐。H2 (鉴权 / 路径绑定) 未静态显现, 由 S04 staging 验证 — 这是合规的 partial resolution。
3. **A3 API 6 双签名 6a/6b**: 修分支 (wait_for_kv_seconds 字段) + 禁用分支 (前置 middleware 拦截 410) 共存, 符合 S01 N5-A5 决策树双支保留要求。S04 在 staging 复现后选定即可。
4. **A1 §"K/V 分离" 实测结论**: "plan 分离 ✓; basis 同源 ✗ (两套独立); config 同源 ✓ (现有缺陷); per-shape/family/rope_state 分离 ✗"。这是 R2/R3 S03 实施的关键输入, A1 给出了精确的当前状态 vs 目标状态差异。
5. **bit=4 vs 论文 6-8 bit**: A1 N1-A7 实测发现 KVTCCodecConfig.bits=4 默认偏低, max_rank=64 在 head_dim=128 上是 50% 截断, zero_bit_energy_fraction=0.015 激进。这些都是直接驱动 S03 调参的 actionable finding, 不是泛泛"对齐论文"。
6. **paged_ssd_cache:1785-1795 silent mix-basis 风险**: A1 显式标出 "≤2 distinct feature_dims" 容错是当前的隐蔽缺陷, 与 N3 决策表 "unknown/hybrid → lz4" 直接冲突。S03 必须在该处加 classifier 主动拒收, 而不是被动跳过。
7. **R4 R5 多 owner 表达**: A7 §2 R4 (S03+S05 双 owner) 与 R5 (单 owner S04) 表达一致, traceability.json downstream_handoff list-len=3 (S03/S04/S05 三 brief), 全部含 4 元组 (verified via E)。

---

## 风险 (本 sprint 边界外, 不阻塞 PASS)

- **A1 局限**: read-only 静态扫描, 未实测加载 Qwen3.6 模型; 真实 head_dim / num_heads / num_kv_heads 在源码内无硬编码; S05 在 CI fixture 拉取时必须从 model card / config.json 抓取实际值并写入 calibration manifest (与 N2 一致, 与 MEMORY "禁止张口就来" 铁律一致)。
- **N5 决策延迟**: A1 命中 H1+H3, 但 H2 未静态显现; S04 staging 复现可能发现 H2 同样命中 (例如鉴权层在某些路径意外剥离), 需扩 root cause 假设并回写 N5 acceptance (S01 N5 Stop Rule 已要求此回写)。
- **paged_ssd_cache v2 metadata 兼容窗**: v1 旧块永久兼容 (A5 M2); 但旧 .kvtc header `kvtc_version="1"` 与 v2 共存期间 reader 必须分流; S03 实施时若分流分支漏掉, 可能 silently 漂移。
- **ATLAS hook 自激风险**: A6 §4 已设 7 天频次上限 + 不允许 auto-merge; 但若 S05 实施时漏掉该上限, 连续 FAIL fixture 可能反复触发; 建议 S05 单测覆盖。
- **`force_kvtc` 越权风险**: A3 API 1 + N3-A7 双重约束 (仅 kwargs); 若 S03 在实施时不慎接入 env / model card, 会形成绕过 N7 UI gate 的隐蔽通道; S05 必须单测验证 F7 critical 路径。
- **mirage / qmd 持续降级**: 本节点 self-contained (事实来自 A1 实测), 但若降级持续到 S03/S04 实施期, 相关知识库检索 fallback 可能影响 evidence 取证流程。

---

## 未验证 (下游 sprint 责任, 不阻塞 PASS)

- N2-A1..A7 (7 单测) / N3-A1..A8 (8 单测) / N4-A1..A7 (7 单测) → 由 S03 在 core-runtime sprint 实施 + pytest 跑
- N5 staging 复现 422 与决策 (修 / 禁用) → 由 S04 在 orchestration-ui sprint
- N6 5×3 覆盖矩阵 + 12+ stable-ci fixtures + CI YAML + hard/soft SLO → 由 S05 verification-release
- N7 UI 4 状态 e2e 截图 + auto block_by_gate_fail 60s 阈值 → 由 S04 + S05 联合
- 真实 Qwen3.6 block A/B 修复后 `decision=kvtc_accept` 子集 p95_rel_rmse ≤ 0.02、min_cos ≥ 0.999 → 由 S05 final regression
- A3 API 7 `THUNDEROMLX_KVTC_UI_AB_SOURCE` 切到 manifest / mocked 演练 → 由 S04 staging

---

## 后续待办 (给协调器)

1. **本 sprint**: PASS。协调器把 status 推 `passed`, 由 epic_decomposer 自动激活 S03_core_runtime + S04_orchestration_ui (两条 architecture 依赖路径同时 ready)。
2. **S03 sprint round-1**: 必读 A1 + A2 D1..D5 + A3 API 1/2/3/4/5/8 + A4 Schema 1/2/4/5/6 + A5 M1/M2/M5/M6 + A6 F1..F7+F11/F12 (按 A7 §6 handoff brief); 不许放宽 hard 阈值; 不许跳过 N3 hybrid→lz4。
3. **S04 sprint round-1**: 先在 staging 复现 N5 422 + 选定修/禁用分支; UI 4 状态机不允许 default ≠ default_off / 不允许跨态直跳; A3 API 6/API 7 schema_version 与 A4 Schema 7 严格一致。
4. **S05 sprint round-1**: 实施 N6 5×3 矩阵 + CI YAML + ATLAS hook (7 天频次上限) + 5 issue label + reports/kvtc-ab/<ts>/ 路径; 不许 fixture 直 commit; 不许 hard 阈值放宽。
5. **epic 关闭门禁**: S05 passed 后 parent-check `ready=true` 才允许 epic close; 本 sprint 不预 close。
