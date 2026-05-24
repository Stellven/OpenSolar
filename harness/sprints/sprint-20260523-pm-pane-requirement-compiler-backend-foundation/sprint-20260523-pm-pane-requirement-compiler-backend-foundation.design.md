# Design — PM Pane Requirement Compiler — Backend Foundation

sprint_id: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
priority: `P0`
lane: `strategy`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-24T03:15:00Z`
knowledge_context: `solar-harness context inject used (mirage timeout -> qmd/obsidian/solar_db fallback)`
parallel_protect: pane-as-physical-operator-architecture / physical-operator-taxonomy-truthification / operator-class-compatibility-cutover / actor-host-runtime-completion-audit (全部 in-flight，read-only 引用)

## 0. 本切片的边界（强制 read-first + wake violation 修复）

- **Wake guard 已报**：`violations=["invalid_task_graph:node_S1_missing_write_scope"]` — 现有 task_graph.json 是 generic boilerplate，本轮 **重写 task_graph** 为 PRD 要求的 N1..N5 + N_E2E sink。
- **Backend foundation sprint**（C4）：本 sprint 只产 schema 草案 + adapter/compiler/gate/compat 规则设计 + E2E walkthrough；**实际 compiler/adapter lib 代码归 follow-up sprint**。
- **允许 Write/Edit**：
  - `sprints/<sid>.{design, plan, task_graph, planning_html}.{md,json,html}`（本轮）
  - `sprints/<sid>.workstream-N{1..6}-*.md`（N1..N_E2E 产出）
  - `sprints/<sid>.adapter-mapping.md`（N2 必交 — PRD 列出的必备产物）
  - `sprints/<sid>.e2e-trace.md`（N_E2E 产出）
  - `~/.solar/harness/schemas/requirement-ir.schema.v1.draft.json`（N1 必交 — PRD 列出的必备产物）
- **严格禁止**（per Hard Rules + Constraints C1..C12 + Non-Negotiables）：
  - 重构 PM pane UI（C4 + Non-Negotiables §1）
  - 用 LLM agent 编译 IR（C9 + Non-Negotiables §2）
  - raw 需求绕过 Compiler 直派 Builder（C2 + Non-Negotiables §3）
  - 破坏旧 codex-pm-router / PM template 路径（C1 + Non-Negotiables §4）
  - 跳 evaluator / architect 二审（Non-Negotiables §5）
  - 实际改 `lib/*.py`（compiler 代码归 follow-up sprint）
  - 改 `~/.solar/harness/schemas/validate.sh` 真代码（本 sprint 只产 enhancement spec）
  - 改 `templates/prd.template.md / product-brief.template.md / sprint-contract.md`（IR 是 superset，旧 template 不变）
  - 写 `/tmp`（C7）
  - 引入新 PyPI 依赖（C6 — stdlib only）
  - secret 入 IR（C12 + 父 sprint C2）
  - 持 in-flight sprint 的 lock 或 mutate 其 artifact（C10）
  - 改 `~/.solar/STATE.md` / epic.*
- 知识库降级 `mirage:timeout`：本 sprint self-contained。

## 1. 当前问题与 IR 解决方案

**三类 pipeline 现状**（PRD §背景）：

```
1. 用户口述需求 → codex-pm-router → 稀疏 PRD          （字段不齐）
2. PM pane 手写 PRD → PM template                     （格式风格不同）
3. chain-watcher / autopilot self-trigger             （可能无 PM 校验）
   ↓ ↓ ↓
   各产物（PRD / contract.yaml / task_graph.json / handoff.md）漂移
```

**IR 解决方案**：

```
任何来源
   ↓ (Input Adapter — 4 类)
Requirement IR (唯一事实源, requirement-ir.schema.v1.draft.json)
   ↓ (Deterministic Compiler — 规则 + template substitution, 不允许 LLM)
4 输出: prd.md / contract.yaml / task_graph.json / handoff.md
   ↓ (Gate Enhancement)
validate.sh 校验: section 必需 + IR 存在 + acceptance 全映射 + research-type evidence ledger
   ↓ pass → Planner 派发
```

## 2. Requirement IR Schema v1（N1 产出）

`requirement-ir.schema.v1.draft.json` 必须含 14 必填字段（PRD Handoff 设计点 1）：

| 字段 | 类型 | 用途 |
|------|------|------|
| `id` | string | sprint-id 或 IR 唯一标识 |
| `source` | enum: `verbal / codex-pm-router / pm-template / chain-watcher` | 4 类需求源（per C1） |
| `type` | enum: `delivery / research / strategy` | research 强制 evidence ledger（per C8） |
| `title` | string | 简短标题 |
| `problem` | string | 问题陈述（≥ 1 句） |
| `goals[]` | list[string] | ≥ 1 条；非空 |
| `non_goals[]` | list[string] | ≥ 0 条；显式列出 |
| `user_stories[]` | list[{persona, story}] | ≥ 1 条 |
| `acceptance[]` | list[{id, criterion, mapped_to[]}] | ≥ 1 条；每条 acceptance 必带 id（A1/A2/...）和 mapped_to（指向 validation/gate） |
| `constraints[]` | list[{id, constraint, rationale}] | ≥ 0 条；ID 如 C1/C2 |
| `risks[]` | list[{severity, risk, mitigation}] | ≥ 0 条 |
| `planner_handoff` | object: {target_role, mode, stop_rules[], non_negotiables[]} | 强制 PM → Planner 路径（C2） |
| `evidence_refs[]` | list[{kind, path/url}] | research-type 必填（per C8） |
| `created_at` / `compiled_from` / `compiled_at` | timestamps + provenance | 可追溯（per C5 superset） |

**额外 schema 约束**：

- secret 字段（含 `(?i)(api[_-]?key|bearer|token|password|cookie|oauth)\s*[:=]`）→ schema validator reject（per C12）
- 字段冗余 OK（compat 旧 PRD 字段允许，但不在 schema 必填里）
- 旧 PRD 字段 import 走 N5 backward-compat best-effort

## 3. 4 类 Input Adapter（N2 产出 → `adapter-mapping.md`）

| Source | Adapter | 输入示例 | 缺字段策略 |
|--------|---------|---------|-----------|
| `verbal` (用户直接打字 / 桌面通知) | `verbal_adapter` | "把 PM pane 改成 Compiler" 一句话 | 缺 problem/goals → prompt-back PM pane 确认；不允许 default fill |
| `codex-pm-router` (本 sprint 自己的入口) | `router_adapter` | router 已结构化的稀疏 PRD | 缺字段 → default empty 但 validator 必报 gate FAIL（per C11） |
| `pm-template` (PM 手写完整 PRD) | `template_adapter` | 完整 prd.md（含全部 section） | 缺字段 → fail-loud；提示补 |
| `chain-watcher` (自动触发) | `chain_watcher_adapter` | 触发 metadata + parent reference | 缺字段 → 从 parent sprint inherit（best-effort），剩余 prompt-back PM |

**Adapter 输出对齐**：4 adapter 全部输出符合 §2 schema 的 IR JSON。

**Adapter Mapping rules（核心）**：

```yaml
verbal:
  title: <first 50 chars of input>
  problem: <full input + 若 prompt-back 后补充>
  source: verbal
  type: <inferred from keywords: research/delivery/strategy>
  default_planner_handoff: {target_role: planner, mode: standard}

codex-pm-router:
  # 直接 map router 已有字段 → IR
  acceptance: extract from "## 9. Acceptance Criteria" or "## Acceptance"
  ...

pm-template:
  # 直接 map prd.template.md 全字段 → IR
  ...

chain-watcher:
  # 从 dispatch.md 解析 parent + 触发原因
  parent_sprint_id: <from dispatch>
  inherited_fields: [problem, goals, constraints, planner_handoff]
```

## 4. Deterministic Compiler（N3 产出）

**IR → 4 outputs derivation rules**（每条输出字段必含 `compiled_from: ir.<path>` provenance comment）：

```
IR → prd.md:
  ## 1. Problem       ← ir.problem
  ## 2. Users         ← ir.user_stories[].persona (deduped)
  ## 3. Goals         ← ir.goals[] + Non-goals from ir.non_goals[]
  ## 9. Acceptance    ← ir.acceptance[].criterion
  ## 11. Constraints  ← ir.constraints[]
  ## 12. Risks        ← ir.risks[]
  Planner Handoff     ← ir.planner_handoff

IR → contract.yaml (Canonical Sources + Product Contract + Interface Contract):
  goal           ← ir.problem
  success_metrics ← ir.acceptance[].criterion (前 3 条)
  non_goals      ← ir.non_goals
  invariants     ← ir.constraints[]
  forbidden_paths ← derived from ir.planner_handoff.non_negotiables
  stop_conditions ← ir.planner_handoff.stop_rules

IR → task_graph.json:
  nodes          ← ir.acceptance[] → 1:1 mapping to node id (e.g., A1 → N1_<slug>)
  每 node.acceptance[0] ← ir.acceptance[<id>].criterion
  每 node.depends_on ← ir.acceptance[<id>].mapped_to.depends_on (默认 linear)
  required_gates ← ir.planner_handoff.stop_rules → gate names

IR → handoff.md:
  Handoff Target ← ir.planner_handoff.target_role
  Handoff Mode   ← ir.planner_handoff.mode
  Stop Rules     ← ir.planner_handoff.stop_rules
  Non-Negotiables ← ir.planner_handoff.non_negotiables
```

**Deterministic 实现要求（C9）**：

- 必须 100% rule-based + template substitution
- 禁止任何 LLM/agent 调用做 IR 字段对齐
- 禁止字符串模糊匹配（必须 schema-driven）
- 输出 reproducible：同 IR 输入 → 同 4 outputs（byte-exact）

## 5. Gate Enhancement (N4 产出 — `validate.sh` 升级 spec)

`~/.solar/harness/schemas/validate.sh` 必须增加 IR-aware 检查（spec only — 实际改 validate.sh 归 follow-up）：

```bash
# 现有：section 必需检查
# 新增：
1. IR 存在性: test -f sprints/<sid>.requirement-ir.json
   缺 IR → 仅旧 PRD 路径，warn 而非 fail（C5 superset 兼容）
2. acceptance 全映射: 每条 ir.acceptance[].id 必须出现在 task_graph.json 某 node.acceptance 中
   缺映射 → fail-loud（C11 acceptance coverage 硬阻断）
3. research-type evidence ledger: 若 ir.type=="research"，必须 test -d sprints/<sid>.evidence/ + tail sprints/<sid>.evidence/ledger.jsonl
   缺 → fail-loud（C8）
4. secret scan on IR: ! grep -E "(api[_-]?key|bearer|token|password)\s*[:=]" sprints/<sid>.requirement-ir.json
   命中 → fail + 立即删除（C12）
5. provenance check: prd.md / contract.yaml / task_graph.json 至少一处含 `compiled_from: ir.<path>` 注释
   缺 → warn（标识旧 PRD 兼容路径）
```

**Backward compatibility（C3）**：现有 validate.sh 调用方（coordinator / autopilot / chain-watcher）的 exit code 语义保持；新检查仅扩失败原因，不改成功路径。

## 6. Backward Compatibility (N5 产出 — 旧 PRD → IR import strategy)

旧 sprint（无 IR）的兼容路径：

```python
def import_legacy_prd_to_ir(prd_md_path) -> dict:
    """Best-effort 把旧 PRD 字段提取为 IR；缺字段 → warn 而非 fail。"""
    ir = {
        "id": derive_sprint_id_from_path(prd_md_path),
        "source": "pm-template",  # 假设旧 PRD 来自 template
        "type": "delivery",  # 默认；可由 grep "research" 提升为 research
        "compiled_from": str(prd_md_path),
        "compiled_at": now(),
    }
    # parse markdown sections
    sections = parse_markdown_sections(prd_md_path)
    ir["title"] = extract_h1(sections)
    ir["problem"] = sections.get("## 1. Problem", "")
    ir["goals"] = extract_list(sections.get("## 3. Goals", ""))
    ir["acceptance"] = [
        {"id": f"A{i+1}", "criterion": line, "mapped_to": []}
        for i, line in enumerate(extract_list(sections.get("## 9. Acceptance Criteria", "")))
    ]
    # ... 类似处理 constraints / risks / handoff
    # 任何字段缺失 → warn (not fail)
    return ir
```

**兼容期**：旧 sprint 不强制 migrate 到 IR；validate.sh 仅 warn。新 sprint（本 sprint 之后）必须有 IR。

## 7. End-to-End Smoke（N_E2E 产出 — 真实 sample 走完整链路）

用一个真实 sample 需求（例如本 sprint 的 PRD 自身或一个迷你示例）做 design-time walkthrough：

```
Input (verbal):
   "把 PM pane 改成 Requirement Compiler"

Step 1: verbal_adapter → IR (含 14 字段，最小可用)
Step 2: deterministic_compiler IR → 4 outputs (prd / contract / dag / handoff)
Step 3: validate.sh 增强版校验 → 全 PASS
Step 4: solar-harness graph-scheduler validate task_graph.json → ok

Walkthrough doc 落 sprints/<sid>.e2e-trace.md，含：
- 每 step 输入/输出/中间状态
- 缺字段触发的 prompt-back / fail-loud 实例
- secret 触发 reject 实例
- 旧 PRD import 兼容实例
```

**E2E 不要求真跑代码**（compiler lib 归 follow-up sprint）；只要 walkthrough doc 能让 evaluator 跟着复现 mental flow 即可。

## 8. 模块图

```
~/.solar/harness/schemas/                            （N1 写）
└── requirement-ir.schema.v1.draft.json              schema 草案（14 必填字段）

~/.solar/harness/sprints/                            （N2-N6 写）
├── <sid>.adapter-mapping.md                         4 类 input adapter rules
├── <sid>.workstream-N1-ir-schema.md                 schema design rationale
├── <sid>.workstream-N2-adapters.md                  adapter mapping spec
├── <sid>.workstream-N3-compiler.md                  deterministic compiler rules
├── <sid>.workstream-N4-gate-enhancement.md          validate.sh upgrade spec
├── <sid>.workstream-N5-backward-compat.md           legacy PRD import strategy
├── <sid>.workstream-N6-e2e-smoke.md                 e2e walkthrough design
└── <sid>.e2e-trace.md                               实际 sample trace

后续 follow-up sprint 产（不在本 sprint 范围）：
~/.solar/harness/lib/requirement_compiler/{ir_schema.py, adapters.py, compiler.py, gate.py, legacy_import.py}
~/.solar/harness/schemas/validate.sh                 真改 (本 sprint 仅产 spec)
```

## 9. 与 in-flight sprint 共存（C10）

| In-flight sprint | 状态 | 本 sprint 影响 |
|------------------|------|---------------|
| pane-as-physical-operator-architecture | drafting | 不动；本 sprint IR schema 不绕过其 schema v2 草案 |
| physical-operator-taxonomy-truthification | reviewing | 不动；本 sprint task_graph node 仍按 logical_operator 路由（per 该 sprint contract） |
| operator-class-compatibility-cutover | active | 不动；本 sprint task_graph 用 canonical operator class（per N2 mapping） |
| actor-host-runtime-completion-audit | active | 不动；本 sprint 不在 audit 范围内（audit scope 已锁） |

本 sprint 不持任何 in-flight sprint 的 lock；不 mutate 任何 in-flight sprint 的 artifact。

## 10. PRD Acceptance ↔ DAG 节点映射

| PRD A# | 描述 | DAG 节点 |
|--------|------|---------|
| A1 | PRD、contract、TaskDAG 互相对齐 | N3 (Compiler 输出对齐) + N_E2E (walkthrough 证明对齐) |
| A2 | 实施、验证、兼容/发布路径均已显式表达 | N1 (planner_handoff 字段) + N4 (gate 表达) + N5 (兼容路径) |
| A3 | 每条验收标准能追溯到验证或 gate | N1 (acceptance.mapped_to[] 字段) + N4 (gate 校验 acceptance 全映射) + N_E2E |

## 11. Open Questions / 隐含 acceptance

per PRD §10 Open Questions + Handoff:

| Q | 答案归宿 |
|---|---------|
| 当前请求缺显式 success metric → 在 PRD 补齐 | **本 sprint 隐含**：IR schema acceptance[] 含 ≥1 条 criterion；N3 compiler 必须产 success_metrics 段；N4 gate 校验 acceptance 数量 ≥1 |

隐含 acceptance（PRD Handoff 列出）：
- IR schema valid（自一致 + secret scan）
- adapter 全覆盖 4 source
- 编译可逆（IR ↔ 4 outputs；旧 PRD → IR best-effort）

## 12. 非目标（per Non-Goals + Constraints + Non-Negotiables）

- 不在首批做完整 4 区 PM pane UI 重构
- 不绕过 planner 直接派 builder
- 不允许 raw 需求 → builder
- 不破坏现有 codex-pm-router / PM template 路径
- 不允许 LLM 做 IR 编译（C9 + Non-Negotiables §2）
- 不引入新 PyPI 依赖（C6）
- 不写 /tmp（C7）
- secret 不入 IR（C12）
- 不 mutate in-flight sprint artifact（C10）
- 本 sprint 不真改 `lib/*.py` 或 `validate.sh`（属 follow-up）
- 不改 `~/.solar/STATE.md` / epic.* / 其他 sprint
- 不使用乐观词

## 13. 接力 evaluator / architect 二审 / follow-up sprint

evaluator 必须按 PRD ## 9 + Handoff 必备产出物 + acceptance gates 逐项核（plan §5 提供命令）。

architect (pane 3 opus) 二审：跨 sprint 一致性（本 sprint IR schema vs pane-as-physical-operator schema v2 草案）。

follow-up sprint：实施 `lib/requirement_compiler/` Python 模块（5 文件）+ 真改 `validate.sh` + 真跑 e2e（不只 walkthrough）。
