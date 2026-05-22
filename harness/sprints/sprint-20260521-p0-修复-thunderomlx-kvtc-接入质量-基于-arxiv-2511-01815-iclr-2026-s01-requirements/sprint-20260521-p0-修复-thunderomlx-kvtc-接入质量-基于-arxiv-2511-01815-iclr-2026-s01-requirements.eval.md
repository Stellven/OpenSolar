# Evaluation — S01 Requirements (KVTC 接入质量修复需求矩阵)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s01-requirements`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
evaluator: 审判官 (Solar Evaluator pane / pane 2)
round: 1
ts: 2026-05-22T05:45:00Z
verdict: **PASS**

Knowledge Context: solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback) — inherited from builder; evaluator did not re-inject (本 sprint 为纯文档评审, 无新查询需求)
Session Log: solar-harness session evaluate **未运行** — pane 2 没有挂接 session_log 子系统; 已用 Read/Bash 验证全部产物。`verify_all_invoked=false`, `verify_all_verdict=SKIPPED` (Skill tool 未注册 verify-all)。@FALLBACK_MANUAL

Harness Modules Used: harness-knowledge (沿用 builder context inject 标记), harness-graph (graph-scheduler validate / batches / parent-check)

---

## 总判定: PASS

合约 Acceptance 3 条全部满足；plan §5 五条验证命令全部 PASS；否证 5 个角度均未推翻 PASS。Stop Rules 全部满足。

---

## Done 条件逐条

| # | Acceptance | 判定 | 证据 |
|---|------------|------|------|
| D1 | 每个 outcome 都有验收标准和风险边界 | **PASS** | N1..N7 共 7 个 requirements.*.md 全部含 `## Outcome` / `## Acceptance Matrix` / `## Risk Boundary` 三个必备段落。bash grep 段落自检脚本在 N1..N7 上 missing_count=0 (见 §自动检测 C1)。 |
| D2 | 明确哪些工作不能直接派 builder | **PASS** | (a) `traceability_map.md §5 Not in Scope` 列 10 条; (b) `traceability.json.not_in_scope` 数组长度=10 (NIS1..NIS10); (c) `traceability.json.builder_forbidden_aggregate` 9 条; (d) 每个 N 节点 .md 都含 `## Stop Rule` 段落。 |
| D3 | 生成父 epic 到子 sprint 的 traceability map | **PASS** | (a) `traceability_map.md §1` 三层对照表（父 epic 8 项 → N1..N7/N8 → 下游 S02..S05 sprint）; (b) `traceability.json.requirements` 7 条 (R1..R7) 每条含 `matrix_node` / `downstream_owner_sprint` / `downstream_owner_role` / `matrix_file` / `acceptance_ids` / `evidence_ids`; (c) `traceability.json.requirements_blocking_epic` 4 条 (S02..S05) 含 `must_consume` 节点清单。 |

---

## 自动检测 (verify-all SKIPPED, 手工等价覆盖)

| 项 | 内容 | 判定 | 证据 |
|----|------|------|------|
| C1 段落齐全 | N1..N7 七个 .md 各含 7 段 (Outcome/Maps to PRD/Acceptance Matrix/Risk Boundary/Stop Rule/Owner Sprint Brief/Acceptance Evidence Plan) | PASS | 见 plan §5C 抗扰自检 |
| C2 N8 异构段落 | N8 traceability_map.md 用 plan §4 末尾定义的特殊结构 (3 层对照 / open_questions / not_in_scope / forbidden) 而非 7 段模板 | PASS | 与 plan §4 一致, 不是 FAIL |
| C3 JSON schema | traceability.json 含 schema_version + sprint_id + epic_id + requirements(7) + open_questions(4) + not_in_scope(10) + requirements_blocking_epic(4) | PASS | python3 断言全 OK |
| C4 PRD §7 open question 1:1 携带 | OQ1..OQ4 全部出现在 traceability_map.md §4 与 traceability.json.open_questions | PASS | grep `^\| OQ` count=4 |
| C5 scope 越界 | 是否有 sprint_dir 外的写入或 ThunderOMLX 源码改动 | PASS | sprint_dir 内 20 个相关文件; ~/ThunderOMLX 目录 mtime 5月20日早于 sprint 起始 5月21日 → 0 改动 |
| C6 乐观词扫描 (DoD 6) | 全部出现的「稳定/已修复/完美」均为 (a) PRD 原文引用 (b) 反向声明禁止 (c) 决策树分支描述 (d) `稳定 CI fixture` 技术固定术语 | PASS | 无违规乐观断言 (见 §否证 4) |
| C7 持久化 | task_graph 8 节点全 `status=passed`, gate `G_S01_requirements_passed=passed` | PASS | task_graph.json node_results 验证 |

---

## 验证命令实跑证据 (plan §5 全部 5 条)

### A. DAG schema validate
```
cmd: solar-harness graph-scheduler validate --graph <sid>.task_graph.json
stdout: {"ok": true, "sprint_id": "...", "node_count": 8, "errors": [], "warnings": []}
conclusion: PASS
```

### B. ready batches
```
cmd: solar-harness graph-scheduler batches --graph <sid>.task_graph.json --max-parallel 3
stdout: {"ok": true, "batch_count": 0, "batches": []}
conclusion: PASS — batch_count=0 因 8/8 节点已 passed; handoff 中"batch_count=3"是 draft (W1 起跑前) 状态描述, 当前状态自然为 0 (无待派发节点)
```

### C. 段落自检 (N1..N7)
```
cmd: for f in <sid>.requirements.{paper_alignment,calibration_key,family_classifier_bypass,reconstruction_gate,named_prompt_cache_422,ci_regression_gate,ui_default_off_gate}.md; do for sec in "## Outcome" "## Maps to PRD" "## Acceptance Matrix" "## Risk Boundary" "## Stop Rule" "## Owner Sprint Brief" "## Acceptance Evidence Plan"; do grep -q "$sec" $f || echo MISSING; done; done
stdout: (空 — 7 节点 × 7 段 = 49 个 grep 全部命中)
conclusion: PASS
```

注：若机械地对 `requirements.*.md` 通配 (含 traceability_map.md) 跑 grep, 会对 N8 报 7 段全缺。这是 plan §5 脚本写法过宽与 plan §4 (N8 异构段落) 的合同口径差异, **不是 builder 缺陷** — N8 按 plan §4 末段定义有独立结构 (3 层对照 + open_questions + not_in_scope + builder_forbidden), 验证另列。

### D. traceability.json schema
```
cmd: python3 断言 schema_version + sprint_id + epic_id + requirements(len==7) + open_questions + not_in_scope
stdout: OK; schema_version=solar.sprint.requirements_traceability.v1; requirements_count=7; open_questions_count=4; not_in_scope_count=10; requirements_blocking_epic_count=4
conclusion: PASS
```

### E. parent-check
```
cmd: solar-harness graph-scheduler parent-check --graph <epic>.task_graph.json
stdout: {"ok": true, "ready": false, "node_count": 5, "open_nodes": [S01..S05], "missing_gates": [5 个 sprint:passed gate 全缺]}
conclusion: PASS — ok=true 表示 graph 合法; ready=false 因 S01..S05 全部未挂 `:passed` gate (符合 epic_decomposer 期望; S01 完成 + epic_decomposer 自动激活 S02 后, missing_gates 才会逐项消减)
```

---

## 否证尝试 (Falsification — 5 个角度全失败 → PASS)

| # | 角度 | 假设 | 结果 |
|---|------|------|------|
| 1 | 路径越界 | builder 可能写到 sprints/ 外 (ThunderOMLX 源码 / STATE.md / epic.* 文件) | 失败: find 显示所有写入文件都在 sprints/<sid>* 命名空间; ~/ThunderOMLX 目录 mtime 5月20日早于 sprint 起始; ~/.solar/STATE.md mtime 远早于 sprint, 未被改动 |
| 2 | PRD 第 7 节 open question 漏携带 | grep `OQ1..OQ4` 是否真出现 4 条 | 失败: traceability_map.md §4 中 `^\| OQ` 行数=4; traceability.json.open_questions 数组长度=4, id 严格 OQ1..OQ4 |
| 3 | 乐观词违规 (DoD 6) | 是否真有「已修复 / 完美 / 稳定」违规断言 | 失败: 全部命中点为 (a) PRD 原文引用 (b) 反向禁令 (c) 决策树描述 "修后稳定 → 通过" 是分支判定不是断言 (d) "稳定 CI fixture" 是术语; 无违规 |
| 4 | builder 替代 S02 填表 | 是否在 N1 audit 表 [TBD-S02 read] 占位被擅自填值 | 失败: paper_alignment.md 7 行 audit 表 [TBD-S02 read] 占位完整保留, 第 33 行显式声明 "本节点禁止替代该 verification" |
| 5 | handoff "batch_count=3" 与实跑 "batch_count=0" 矛盾是否构成欺骗 | 是否描述失实 | 失败: 8 个节点全 `status=passed`, 自然 batch_count=0; handoff 描述是 draft 时 (W1 启动前) 状态, 非 evaluator 评估时状态; 时序差异不是失实 |

5 次否证均失败 → PASS。

---

## Smoke Test (按铁律 — 因属纯文档矩阵, 显式标注未跑原因)

未 smoke test 原因: 本 sprint 是 **需求拆解文档矩阵 sprint** — 不含运行时函数、不含 codec/calibration 实现、不含 HTTP/CLI 入口、不含 UI 状态机。所有"功能"是给下游 S02..S05 用的合同 (schema / 阈值 / 决策树 / 字段定义)。真功能在 S03 (codec + calibration_store + paged_ssd_cache 实现) / S04 (server + UI) / S05 (CI gate) 阶段, 各自 sprint 自带 smoke test 协议 (jsonl 抽样 / 单测 / staging 复现 / e2e 截图等已写入各 N 节点的 `Acceptance Evidence Plan` 段)。

合规等价: §自动检测 C1..C7 已对每个 schema/字段/段落做了实测验证 (grep / json 断言 / mtime / path scope), 等价于"文档接入合同"的 smoke。

---

## 额外发现

1. **handoff batch_count 描述时序**: handoff 写 `batch_count=3` 反映 draft 时 W1 待派发状态; 我跑时 8/8 passed → 0 batches。已在 §B 标注, 非 FAIL。建议未来 handoff 在 batches 输出附时间戳避免误读。
2. **plan §5C 验证脚本通配过宽**: `for f in requirements.*.md` 会把 N8 traceability_map.md 拉入 7 段 grep, 与 plan §4 定义 N8 异构段落矛盾。Builder 正确理解为"7 个 N 文件", 但脚本本身应限定到 N1..N7 文件名清单, 避免下次 evaluator 机械跑 FAIL。**这是 plan 缺陷, 非 builder 缺陷**; 建议在 N8 完成后续 sprint 升级 plan template 时修正。
3. **R4 双 owner 表达**: traceability.json `R4.downstream_owner_sprint` 是 list (S03 + S05), 其余 6 条是 string。schema 一致性可接受 (因 R4 确实有两个下游 owner), 但若未来引入严格 typed schema, 建议统一为 `Union[str, List[str]]` 或永远 list。
4. **knowledge_context 降级链**: mirage degraded → qmd/obsidian/solar_db fallback, 已在 7 个 N 文件头部统一标注; N1 论文章节号引用 (§3 / §3.1 / §3.2 / §3.3 / §4 / §4.3 / §5) 来自 fallback 源, S02 在 architecture 阶段需要二次核对 paper 原文章节号是否一致 (本 sprint 不能验证, 已记为后续待办)。

---

## 风险与未验证项 (本 sprint 边界外, 不阻塞 PASS)

- [未验证] N1 [TBD-S02 read] 占位 7 行 → 由 S02 读 ThunderOMLX 源码填表
- [未验证] N2..N4 acceptance 单测 → 由 S03 在 core_runtime 阶段 pytest 实跑
- [未验证] N5 staging 复现 422 raw response → 由 S04 在 staging 跑 curl 抓 detail.loc/type
- [未验证] N6 stable-ci 15 fixture 物理拉取 + 体积 ≤ 100MB 约束 → 由 S05 实施
- [未验证] N7 UI 4 状态 e2e 截图 + state api 翻转 → 由 S04 staging
- [未验证] 真实 Qwen3.6 block 修复后 p95_rel_rmse ≤ 0.02 / min_cos ≥ 0.999 → S05 final regression
- [风险] N1 论文章节号引用源于 fallback 知识库 (mirage degraded); S02 必须二次核对
- [风险] N5 staging 复现可能发现 root cause 不在 H1/H2/H3 (例如 500/404/网络层) → N5 已留 Stop Rule 强制回写, 不会 silent

---

## 后续待办 (给协调器)

1. **本 sprint**: 已 PASS。协调器把 status 从 `reviewing/builder_done/evaluator` 推到 `passed`, 由 epic_decomposer 自动激活 S02_architecture。
2. **下一波**: S02_architecture sprint 必读 N1 paper_alignment.md + N8 traceability_map.md/json, 产出 design.md (填 [TBD-S02 read] 占位)。
3. **plan template 修正** (可选): 在通用 planner template 中把 §5C 的 `requirements.*.md` 通配改为 N1..N7 文件名清单, 避免 N8 异构段落与机械 grep 冲突。
