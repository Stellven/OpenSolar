# Execution Plan — sprint-20260524-solar-research-os-v1-core

## 0. 计划目标

把需求编译器产出的 generic research sprint，收敛成一个可派发、可验证、可迭代的 **Solar Research OS v1 Core implementation plan**。

总原则：

1. 先修默认可靠性，再扩展功能。
2. 先打通 claim-verified compiler 主链，再谈 Lab / Memory。
3. 任何 builder 节点都必须绑定文件边界、测试、acceptance。

---

## 1. Phase 拆分

### P0 止血

目标：把 Deep Research 从“默认可能漏 gate”修到“默认可靠”。

- 修 quality gate / closeout 回归
- evidence ledger 默认 `required`
- survey/final gate 默认 `required`
- 禁止 model-generated citation

### P1 核心编译链

目标：把 Deep Research 从 report writer 升级成 claim-verified compiler。

- `ResearchTaskSpec` + dynamic half-year window
- `ResearchStateMachineRunner`
- `SourceConnectorRegistry`
- `Claim Compiler v2` seam
- `ContradictionSearchOperator` seam
- `ReportBlueprint + SectionContract`
- `FinalCloseoutGate` 单入口

### P2 图表与趋势

目标：图不是装饰，而是 evidence artifact。

- `FigureSpec`
- architecture diagram IR / renderer seam
- figure grounding gate
- trend / timeline artifact seam

### P3 Lab / Memory seams

目标：先留扩展缝，不在本 sprint 实装完整平台。

- `DeltaManifest`
- `ResearchLabContract`
- `ResearchMemoryContract`
- `AIInfraPackContract`

---

## 2. 节点执行顺序

```text
N1 审计与文件边界
  -> N2 P0 gate/default 修复
  -> N3 task contract + state machine
  -> N4 connector registry + claim/contradiction seam
  -> N5 report compiler + final closeout contract
  -> N6 figure/diagram grounding minimum path
  -> N7 delta/lab/memory/pack seams
  -> N8 evaluation + rollout handoff
```

---

## 3. 节点与文件

### N1 架构审计

- 读取：`lib/research/*`, `graph_node_dispatcher.py`, `status-server/research_routes.py`, `graph_scheduler_research.py`
- 输出：现状审计、P0/P1 文件边界、测试清单

### N2 P0 默认可靠

- 主要文件：
  - `/Users/lisihao/Solar/harness/lib/research/storage.py`
  - `/Users/lisihao/Solar/harness/lib/research/cli.py`
  - `/Users/lisihao/Solar/harness/lib/research/survey/evaluator.py`
  - `/Users/lisihao/Solar/harness/lib/graph_node_dispatcher.py`
  - `/Users/lisihao/Solar/harness/tests/research_integration/test_deepresearch_quality_gate_verdict.py`
- 目标：
  - 修 closeout regression
  - 打开 required defaults
  - 禁止 model citation

### N3 Task Contract / State Machine

- 主要文件：
  - `/Users/lisihao/Solar/harness/lib/research/state_machine.py`
  - `/Users/lisihao/Solar/harness/lib/research/cli.py`
  - `/Users/lisihao/Solar/harness/schemas/draft/`
- 目标：
  - `ResearchTaskSpec`
  - dynamic lookback
  - `ResearchStateMachineRunner`

### N4 Connector / Claim / Contradiction

- 主要文件：
  - `/Users/lisihao/Solar/harness/lib/research/sources/`
  - `/Users/lisihao/Solar/harness/lib/research/cli.py`
  - `/Users/lisihao/Solar/harness/lib/operator_runtime.py`
  - `/Users/lisihao/Solar/harness/schemas/draft/`
- 目标：
  - registry 收口 provider
  - claim compiler v2 seam
  - contradiction-first seam

### N5 Report Compiler / Final Gate

- 主要文件：
  - `/Users/lisihao/Solar/harness/lib/research/evaluator.py`
  - `/Users/lisihao/Solar/harness/lib/research/cli.py`
  - `/Users/lisihao/Solar/harness/lib/graph_node_dispatcher.py`
  - `/Users/lisihao/Solar/harness/schemas/draft/`
- 目标：
  - blueprint / section contract
  - single-source final verdict

### N6 Figure Minimum Path

- 主要文件：
  - `/Users/lisihao/Solar/harness/lib/research/`
  - `/Users/lisihao/Solar/harness/status-server/research_routes.py`
  - `/Users/lisihao/Solar/harness/schemas/draft/`
- 目标：
  - `FigureSpec`
  - architecture diagram / timeline seam
  - figure grounding gate

### N7 Future Seams

- 主要文件：
  - `/Users/lisihao/Solar/harness/schemas/draft/`
  - `/Users/lisihao/Solar/harness/docs/architecture/`
  - `/Users/lisihao/Solar/harness/lib/research/`
- 目标：
  - delta / lab / memory / AI Infra pack contract

### N8 Eval / Handoff

- 主要文件：
  - sprint handoff / status / final rollout note
  - regression test outputs

---

## 4. 验收命令

最低验收：

```bash
python3 /Users/lisihao/Solar/harness/lib/graph_scheduler.py validate \
  --graph /Users/lisihao/.solar/harness/sprints/sprint-20260524-solar-research-os-v1-core.task_graph.json
```

builder 执行阶段至少补这些：

```bash
pytest -q /Users/lisihao/Solar/harness/tests/research_integration/test_deepresearch_quality_gate_verdict.py
pytest -q /Users/lisihao/Solar/harness/tests -k deepresearch
```

---

## 5. 风险与回退

- 风险 1：`cli.py` 继续承担过多职责
  - 回退：先加 runner/registry seam，不一次重写全部 research runtime
- 风险 2：claim compiler v2 改动过大
  - 回退：允许 v1 fallback，但 fallback claim 不得进入 final critical conclusion
- 风险 3：图表链拖慢主线
  - 回退：P2 只交付 FigureSpec + grounding + mermaid IR，不强做全部 renderer

---

## 6. Planner 结论

这次“开工”不等于立刻把 Research OS 全写完，而是把它编译成一个 builder 可执行的实现主链。只要 N2-N5 打穿，Solar 就已经从“研究脚本增强版”切到“claim-verified research compiler”赛道。
