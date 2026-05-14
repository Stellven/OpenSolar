# PRD: Solar DeepResearch 产品线 · S05 验证与发布 (Verification & Release)

epic_id: `epic-20260513-solar-deepresearch-product-line`
sprint_id: `sprint-20260513-solar-deepresearch-product-line-s05-verification-release`
slice: `verification-release` (epic 5/5)
priority: P0
lane_hint: delivery
author: Solar PM
date: 2026-05-14
Knowledge Context: solar-harness context inject used (Mirage + QMD + Obsidian + Solar DB)

---

## 1. 背景 / Context

Solar DeepResearch 产品线由 5 个切片串成：
S01 需求 → S02 架构 → (S03 核心 runtime ∥ S04 编排 UI) → **S05 验证与发布**.

S01-S04 解决的是「能跑」的问题：spec、schema、storage、connector、CLI、autopilot intent、DAG template、capability plane 都已逐层就位.
S05 解决的是「能交付」的问题——把前四个切片粘合成**端到端可复现验证 + 负控防伪 + benchmark smoke + 文档 + Knowledge 归档**，作为父 epic 的关闭闸门 (close gate).

历史教训驱动 S05 的必要性 (历史优先于现状):
- Control Plane v2 sprint 死于 S1-S3 PASS、S4-S8 没人收口 (followup.md F4 已记录).
- MEMORY: 「验证交付物不信声明」「测试用 mock 数据库被 prod migration 打脸」.
- 父 epic stop rule 第 3 条: parent sprint 在 evidence/claims/fact-check gates 未过前不能 `passed`. S05 是这个 gate 的唯一 owner.

S05 不再设计新能力, 也不重写已交付能力, 只做**收口 + 防伪 + 归档**.

## 2. 用户问题 / Problem Statement

监护人 (昊哥) 给 DeepResearch 产品线的核心 P0 验收清单是「证据可复现」, 但当前 epic 距离 close 仍有 5 个验证缺口:

| # | 缺口 | 风险 |
|---|---|---|
| P1 | 单测覆盖不足 | schema/storage/hashing 任何字段漂移无法被自动捕获 |
| P2 | 集成测缺失 | fixture source → final.md 全链路从未跑通过 |
| P3 | 负控空白 | unsupported claim / span mismatch / connector failure 可能静默通过 |
| P4 | benchmark smoke 缺失 | 没有 2-3 section 报告 + research_eval.json, 无法证明产品「能写真东西」 |
| P5 | Knowledge 归档缺失 | accepted artifact 没写入 `~/Knowledge/_raw/`, 未来 RAG 检索不到 |

不闭这五个缺口, epic 关闭就是「假完成」, 父 sprint 会偷跑.

## 3. 用户目标 / User Goals

- **真测试可复现**: `pytest harness/tests/research -v` 本地任何时刻可跑、全绿、断言 ≥ 30.
- **三类负控硬 fail**: unsupported claim / citation span mismatch / connector failure, 任一类静默通过 = N3 fail.
- **smoke benchmark 真有内容**: 用 fixture connector 产出 2-3 section 报告 (≥ 100 行) + `research_eval.smoke.json` 包含 unsupported_claim_rate / citation_span_accuracy 两个键.
- **Knowledge 沉淀可索引**: accepted artifact + final eval + architecture decision 写入 `~/Knowledge/_raw/deepresearch-accepted-<date>.md`, 文件名带 sid + 日期唯一化.
- **epic 关闭单线串行**: 只有 N5 一个节点能改 `epic-*.traceability.json` 和 `Knowledge/_raw/`, 防止并发污染.

## 4. 用户故事 / User Stories

- **作为监护人 (昊哥)**, 我希望「Solar DeepResearch 产品线 P0 验收清单」是一张一目了然的勾选表, 而不是一堆 sprint id, 这样我能 30 秒判断「能不能上线」.
- **作为下一个 builder**, 我希望本地跑 `pytest harness/tests/research -v` 就能复现所有验证, 不需要装额外服务或拿任何线上 key.
- **作为 evaluator**, 我希望能 grep 出 ≥ 30 个 `assert`、≥ 3 个 `pytest.raises`/`xfail`, 这样不会被「测试空跑」骗.
- **作为未来的 Solar Master Brain**, 我希望从 `~/Knowledge/_raw/deepresearch-accepted-*.md` RAG 搜索时能命中本 epic 的架构 decision 和负控样例, 不要让本次工作只活在 sprint 文件里.
- **作为 epic_decomposer**, 我希望 handoff 里有显式 `epic_can_close: true` 信号, 不需要我做语义解析.

## 5. 功能性需求 / Functional Requirements

- **FR-1**: 单测套件 `harness/tests/research/unit/` 覆盖 schemas / ids / hashing / storage migrations / evidence span hash / claim-evidence link, 真 SQLite (`:memory:` 或 `tmp_path`), 禁止 mock.
- **FR-2**: 集成测 `harness/tests/research/integration/test_pipeline.py` 用 fixture source → evidence.jsonl → claims.jsonl → report_ast.json → final.md, 产物 `tests/research/fixtures/_out/final.md` 非空.
- **FR-3**: 负控 `harness/tests/research/negative/test_neg_controls.py` 至少 3 条 testcase, 使用 `pytest.raises` 或 `xfail`, 分别覆盖 unsupported claim / citation span mismatch / connector failure.
- **FR-4**: smoke benchmark 产物两份: `harness/reports/research-smoke-bench.md` (≥ 100 行, 含引用, 2-3 section) 和 `harness/reports/research_eval.smoke.json` (必含键: `unsupported_claim_rate`, `citation_span_accuracy`, `section_count`).
- **FR-5**: 用户文档 `harness/README.research.md` 含: 安装步骤、CLI 5 子命令示例、operator runbook、troubleshooting 段; 文档语言双语 (英 + 中).
- **FR-6**: Knowledge 归档 `~/Knowledge/_raw/deepresearch-accepted-<YYYYMMDD>-<sid>.md`, 至少 1 份, 内容包含 epic 摘要 + 5 个 sprint 链接 + 关键 decision 摘录.
- **FR-7**: handoff `…s05.handoff.md` 必须含: 5 份产物路径、4 套测试 pass 率摘要、`research_eval.smoke.json` head、`epic_can_close: true` 显式标记、P0 验收清单 (markdown 表), 以及给 epic_decomposer 的关闭信号.
- **FR-8**: N5 节点写 handoff 前必须 read N1-N4 全部 `passed` 状态; 任一未 passed 时, handoff 写 `epic_can_close: false` 并列出阻塞项.
- **FR-9**: `task_graph.json` 通过 `solar-harness graph-scheduler validate` 且 prerequisites 显式声明 `S03_passed ∧ S04_passed`.

## 6. 验收标准 / Acceptance Criteria

| # | Criterion | Verification |
|---|---|---|
| **A1** | 单测可复现, 断言 ≥ 30 | `pytest harness/tests/research/unit -v` exit 0, `grep -rc assert harness/tests/research/unit` ≥ 30 |
| **A2** | 集成测 fixture → final.md 全链路 | `pytest harness/tests/research/integration -v` exit 0, `[[ -s tests/research/fixtures/_out/final.md ]]` |
| **A3** | 三类负控全部 fail-by-design | `pytest harness/tests/research/negative -v` exit 0; `grep -rE "pytest\.raises\|xfail" harness/tests/research/negative` ≥ 3 命中 |
| **A4** | smoke benchmark 2-3 section + ≥ 100 行 | `wc -l harness/reports/research-smoke-bench.md` ≥ 100; `jq '.section_count' research_eval.smoke.json` ∈ [2,3] |
| **A5** | research_eval.smoke.json 含必要键 | `jq 'has("unsupported_claim_rate") and has("citation_span_accuracy")' research_eval.smoke.json` = true |
| **A6** | Knowledge 归档存在 | `ls ~/Knowledge/_raw/deepresearch-accepted-*.md` ≥ 1 |
| **A7** | epic traceability.json children[4] status=passed + artifact_links ≥ 5 | `jq '.children[4].status, (.children[4].artifact_links \| length)'` 返回 "passed" 和 ≥ 5 |
| **A8** | task_graph.json validate 通过 | `solar-harness graph-scheduler validate` exit 0 |
| **A9** | handoff.md 含 `epic_can_close: true` 信号 | `grep -E "^epic_can_close:\s*true" handoff.md` 命中 |
| **A10** | 整套测试不依赖任何线上 key | `git grep -E "OPENAI_API_KEY\|BRAVE_API_KEY\|OPENALEX_TOKEN"` 在 tests/ 下零命中 |

## 7. 非目标 / Non-Goals

- **不写 10w 字最终报告**: 这是产品上线后实际研究 sprint 的事, 不是 S05 验证范围.
- **不接活体 connector key**: 所有集成测/负控/smoke 使用 fixture 数据; 活体 connector 留给后续 release-X sprint.
- **不重做 architecture/runtime**: S02 / S03 是唯一来源, 本切片只验证它们的产物, 不重新设计.
- **不重新注册 capability plane**: S04 已经把 research.* capability 注册完毕; 本切片只校验注册结果.
- **不绕过 graph_scheduler**: 所有测试 dispatch 必须走 task_graph.json + validate.
- **不替换 evaluator**: sprint eval 仍由现有 evaluator + `solar-harness session evaluate` 完成; 本切片只补 `research_eval.smoke.json` 这个产物.
- **不改 S03 的实现代码**: 即便测试发现 bug, 也通过 followup sprint 修, 不在 S05 内联修.

## 8. 约束 / Constraints

- **C1**: 测试**禁止 mock 数据库** (MEMORY 教训), 必须真 SQLite + tmp_path fixture; evaluator grep `@mock.patch` 在 tests/research/ 下零命中.
- **C2**: 测试**禁止空跑** — 函数 body 为空 / 只 `pass` / 只 `assert True` 视为 fail; 每个 testcase 必须有真断言.
- **C3**: 测试**禁止依赖线上服务** — 不调真 LLM, 不调真 OpenAlex/Brave/GitHub API, 全部 fixture 化, 目标 5 分钟内本地跑完.
- **C4**: write_scope 互斥 — N1/N2/N3/N4 写不同目录, 不允许任何节点跨写; N5 独占文档 + Knowledge + epic traceability.
- **C5**: smoke benchmark 的 fixture 必须真有 `source_text` + `span_start/end`, 不允许 hardcode span_text 但 source 对不上 (会被 negative test 抓到).
- **C6**: 全部节点路由 **Sonnet**, 禁止 GLM (历史已踩 5 次 1210 + 中文长上下文崩盘).
- **C7**: N5 是唯一可改 `epic-*.traceability.json` 和 `~/Knowledge/_raw/` 的节点 (write_scope 锁), 防止 epic 提前 close.
- **C8**: 测试产物 (final.md / research_eval.smoke.json) 必须能离线复跑, 不允许「跑过一次拍照」.

## 9. 风险 / Risks

| # | Risk | Mitigation |
|---|---|---|
| **R1** | S03 / S04 尚未 passed 就启动 S05, builder 找不到实现 | task_graph.json 显式声明 `prerequisites: ["S03_passed","S04_passed"]`; coordinator dispatch 前检查 |
| **R2** | 测试覆盖率虚高 (大量 noop testcase) | A1 acceptance 加 `assert >= 30`; evaluator grep `assert` 数量 |
| **R3** | smoke benchmark 跑太慢 | N4 用 fixture connector + 本地 stub LLM (或纯规则), 目标 5 分钟内跑完 |
| **R4** | Knowledge 归档路径冲突 (多 sprint 同写 _raw/) | N5 文件名带 sprint sid + 日期, 唯一化 |
| **R5** | epic 提前 close | N5 是唯一可改 epic.traceability.json 的节点, 且必须先读 N1-N4 全 passed; A7/A9 acceptance 双重 check |
| **R6** | 负控被误写成「应该通过的测试」 | N3 用 `pytest.raises` 或 `xfail`, evaluator 检查 ≥ 3 个 raises/xfail 标记 |
| **R7** | 测试硬编码本地路径 | tests 用 `tmp_path` / `tmpdir` fixture; 不允许出现 `/Users/sihaoli` 等绝对路径 |
| **R8** | smoke 报告引用伪造 (无 evidence_id) | A5 + 集成测穿透检查: 报告里每个 claim 必须能 join 到 evidence.jsonl |
| **R9** | handoff `epic_can_close` 被误填 true | N5 必须程序化读 N1-N4 status; evaluator 复查 4 个 sub-status 文件 |

## 10. 开放问题 / Open Questions (给 Planner / 架构师)

1. smoke benchmark 的 LLM 用什么? 真 Sonnet/Haiku call 还是 stub 模板生成器? (建议 stub, 保持离线; 若真 call, 必须缓存 fixture).
2. `research_eval.smoke.json` 的指标计算逻辑放在 S03 lib 还是 S05 tests/? (建议 S03 lib 提供 evaluator 函数, S05 调用).
3. Knowledge `_raw/` 归档文件是否需要 YAML frontmatter 以便未来 obsidian-vault-index FTS? (建议: 是, frontmatter 含 `epic`/`sprints`/`date`/`tags`).
4. N3 负控的 fixture 数据放在哪? 三套独立 fixture 还是共用 (S03 提供) 的 fixture 加 mutator? (倾向共用 + mutator, 减少漂移).
5. P0 验收清单表格的字段定义? (建议: criterion / verification cmd / current status / blocking_sprint).
6. 测试套件是否需要 CI 集成 (GitHub Actions / 自建 runner)? 还是仅本地 pytest? (本切片只覆盖本地, CI 留作 followup).
7. handoff 的 `epic_can_close` 信号是否需要写入 events.jsonl 以便 epic_decomposer 自动监听? (建议: 是, type=epic_close_signal).
8. `Knowledge/_raw/deepresearch-accepted-*.md` 是否需要 mirage VFS 自动 mount 验证? (建议: 留 followup).
9. 如果 S03/S04 未通过, S05 是 abort (status=blocked) 还是 partial pass (N1/N2/N3 跑能跑的)? (倾向 abort, 防止部分通过被误报为 epic close).
10. handoff 是否要列「线上化前必须做的剩余 P1 工作」清单, 帮监护人决定上线节奏? (建议: 是, 单独一节列 P1/P2).

## 11. 架构交接 / Planner Handoff

**Planner 已在 design.md 完成 5-node DAG 设计**, 本 PRD 与其完全对齐, 不需要 planner 重做拓扑:

```text
N1 unit-tests          ──┐
N2 integration-tests   ──┤
N3 negative-controls   ──┤
N4 smoke-benchmark     ──┤
                         └── N5 docs-and-knowledge-archive ── handoff
```

| Node | 角色 | Write Scope | Model | 依赖 |
|---|---|---|---|---|
| **N1** | builder | `harness/tests/research/unit/**`, `harness/tests/research/fixtures/unit/**` | sonnet | S03 passed |
| **N2** | builder | `harness/tests/research/integration/**`, `harness/tests/research/fixtures/integration/**` | sonnet | S03 ∧ S04 passed |
| **N3** | builder | `harness/tests/research/negative/**`, `harness/tests/research/fixtures/negative/**` | sonnet | S03 passed |
| **N4** | builder | `harness/reports/research-smoke-bench.md`, `harness/reports/research_eval.smoke.json`, `harness/tests/research/fixtures/smoke/**` | sonnet | S03 ∧ S04 passed |
| **N5** | builder (collector) | `harness/README.research.md`, `Knowledge/_raw/deepresearch-accepted-*.md`, `…s05.handoff.md`, `epic-…traceability.json` | sonnet | N1 ∧ N2 ∧ N3 ∧ N4 passed |

**N1-N4 完全并行** (write_scope 互斥). **N5 唯一可触碰 cross-sprint 文件** (epic traceability + Knowledge _raw).

**给 builder 的关键 read 入口**:
- S03 实现: `harness/lib/research/{schemas,ids,hashing,storage}.py`, `harness/lib/research/{evidence,sources,extractors}/`, `harness/lib/research/cli.py`
- S04 接入: autopilot research intent, DAG template, capability plane research.*, `/research/<sid>` status UI
- S02 spec (验证标准来源): `architecture.md`, `schemas.md`, `storage.md`, `dag-template.json`
- 测试 fixture 命名: `tests/research/fixtures/{unit,integration,negative,smoke}/`

**Planner 三件套已就位**:
- `design.md` (10217 bytes, methodology)
- `plan.md` (7833 bytes, 5-node DAG narrative)
- `task_graph.json` (9974 bytes, machine-readable, 已通过 graph-scheduler validate)

**给 evaluator 的关键 grep**:
- `grep -rc assert harness/tests/research/unit` ≥ 30
- `grep -rE "pytest\.raises|xfail" harness/tests/research/negative` ≥ 3
- `git grep "@mock.patch" harness/tests/research/` = 0 命中
- `grep -E "^epic_can_close:\s*true" handoff.md` 命中且与 traceability.json children[4].status=passed 一致

**给 epic_decomposer 的关闭信号**: handoff 内 `epic_can_close: true` + events.jsonl `epic_close_signal` event (Open Question 7 确认后).

**S05 通过 = DeepResearch 产品线 epic 可关闭**. PM (本人) 不参与实现, 验收通过后归档.

---

## Appendix A. Epic Context (S01-S05 全景)

| Sprint | Slice | Status | 角色 |
|---|---|---|---|
| S01 | requirements | passed | 把用户原始 design doc 收敛为正式需求 |
| S02 | architecture | planning_complete (PRD 已补) | 0 代码的架构 spec: architecture / schemas / storage / dag-template |
| S03 | core-runtime | drafting (PRD 待补) | 第一行可执行 Python: 8 schemas + SQLite 7 表 + evidence ledger + 1 connector + CLI 5 子命令 |
| S04 | orchestration-ui | planning_complete (PRD 已补) | autopilot intent + DAG template + handoff schema + status UI + capability plane research.* |
| **S05** | **verification-release** | **本切片** | **端到端验证 + 负控 + smoke benchmark + 文档 + Knowledge 归档 + epic close gate** |

Epic stop rule 3: parent sprint 不能在 evidence / claims / fact-check gates 未过前 passed. **S05 是这个 gate 的唯一 owner**.

## Appendix B. Followups (给 sprint-20260514-coordinator-data-integrity 候选合并项)

- **F1**: 协调器 raw_extra '{}}' JSON 双闭合 bug (MEMORY 已记录)
- **F2**: PRD 被 contract-patrol 误删 (MEMORY 已记录)
- **F3**: S01 traceability=passed 但 autopilot 仍报 blocked_by_s01 — autopilot vs traceability 探活分裂
- **F7**: status.json `updated_at` 时钟回退被允许 (PM 在 S02 写入时踩到, 已用 `max(now, prev_max+1s)` 规避)

S05 通过后建议起一个 `sprint-20260514-coordinator-data-integrity` 合并修这 4 条; 不在 S05 内联修 (违反 C-NonGoal 6).
