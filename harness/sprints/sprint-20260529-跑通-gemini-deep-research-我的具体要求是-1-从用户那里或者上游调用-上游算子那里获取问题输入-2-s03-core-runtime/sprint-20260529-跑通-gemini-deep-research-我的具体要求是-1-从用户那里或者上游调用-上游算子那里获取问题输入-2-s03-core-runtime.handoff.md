# Handoff — S03 核心实现与数据模型

Sprint: `sprint-20260529-跑通-gemini-deep-research-...-s03-core-runtime`
Nodes: C1 → C2 → (C3, C4) | Gates: schemas-and-persistence / core-state-machine / backward-compat / unit-tests-and-replay
Knowledge Context: solar-harness context inject used
Session Log: n/a (builder slice, evaluator 评审时执行 session evaluate)
Harness Modules Used: harness-knowledge

## Summary

按 S02 架构实现 Gemini Deep Research 核心 runtime，落新增独立包
`lib/capabilities/gemini_deep_research/`（PACKAGE_PREFIX 白名单内），**未改任何 PROTECTED_CORE**。
实现 schema/持久化(C1) + 状态机/O1-O6 控制器/事件重建(C2) + 真实算子兼容适配(C3) + 单测/replay 证明(C4)。
真实 Gemini 网页调用由人工授权开关 `GEMINI_DR_REAL_CALLS=1` 控制，**默认关闭**；
默认走既有 `browser_job_runtime` 的 mock 轨迹，证明接线真实而不消耗 DR 额度。

## 交付物 (15 个 .py，全部在 write_scope 内)

- C1 `schemas/`: `models.py`(6 个 dataclass + 4 enum + InvalidResearchRequest 校验), `persistence.py`(append-only JSONL EventLog + secret 拒写), `__init__.py`
- C2 `core/`: `state_machine.py`(ControllerState 8 态 + 合法转移表), `retry.py`(RetryPolicy 三参数 + A3 成功判据), `ports.py`(BrowserOperatorPort 抽象), `controller.py`(GeminiDRController O1-O6 + 事件落盘 + `rebuild()` event-replay), `__init__.py`
- C3 `compat/`: `operator_adapter.py`(DeepResearchBrowserAdapter 绑定既有 browser_job_runtime), `status_projection.py`(只读投影到既有 status/monitor 字段), `__init__.py`
- C4 `tests/`: `test_core.py`(28 测试), `conftest_path.py`(sys.path 引导), `__init__.py`

## 已验证 (实际执行的命令 + 结果)

1. **单测全绿** — `python3 -m unittest gemini_deep_research.tests.test_core -v`
   → `Ran 28 tests in 0.012s / OK`。覆盖: schema 校验、persistence secret 拒写、状态机全 8 态可达 + 非法转移抛错、retry backoff/分类、A3 成功判据、控制器 happy/optimize-guard/waiting_human/attempts-exhausted/incomplete 五条路径、event-replay 重建 == live 快照(happy+fail)。
2. **C3 真实算子接线** — 用 `DeepResearchBrowserAdapter` + 真实 `browser_job_runtime` mock 轨迹跑通 submit→poll→collect:
   - 真实创建 `run/browser_jobs/job-c4ba88cc.../state.json`(execution_mode=mock, state=done)；
   - 控制器到达 async_state=done 后，因 mock 无真实文献 → 诚实返回 `failed/incomplete_result`（**不伪造 references**）；
   - `project_status()` 从事件日志只读重建出 controller_state/async_state/terminal。
3. **状态机覆盖** — 测试 `test_every_state_reachable_from_input` 用 BFS 证明 8 个 ControllerState 全部从 INPUT 可达。
4. **event-replay 一致性** — `GeminiDRController.rebuild(run_ref, log)` 重建的 state/result.status/handle.async_state 与 live `snapshot()` 完全相等。

## Diff 自审 (每个文件目的)

- `schemas/models.py` — A2 字段级 schema 落 dataclass；O1 空/超长/非法编码 → InvalidResearchRequest；DRResult succeeded 强制 references+report。
- `schemas/persistence.py` — 事件即真相源；secret-like key 拒写(NB1)；默认存 `~/.solar/harness/var/...`（不入 /tmp）。
- `core/state_machine.py` — INPUT→OPTIMIZE→SUBMIT→CONFIRM→MONITOR→{DONE|RETRY|FAIL}，RETRY 回 SUBMIT。
- `core/retry.py` — A3 三参数(max_attempts=3/timeout=30min/指数退避 cap5min) + 机器可判成功判据(MIN_REFS=3+分类块+http url)。
- `core/ports.py` — 六边形端口；core 不直接 click，委托算子(A1)。
- `core/controller.py` — O1 entrypoint `submit_research` + monitor 循环 + collect + `rebuild` 重建。
- `compat/operator_adapter.py` — 绑定既有 browser_job_runtime；真实调用 env 开关默认关。
- `compat/status_projection.py` — 只读投影，不写 harness 核心状态。
- `tests/test_core.py` — 28 测试，含 replay 等价性证明。

## Scope Compliance

- 仅写入 `lib/capabilities/gemini_deep_research/{schemas,core,compat,tests}/`（各节点 write_scope）+ 包根 `__init__.py` + 本 handoff。
- PROTECTED_CORE(solar-harness.sh/coordinator.sh/graph_scheduler.py 等 8 文件)**未编辑**（仅调用 graph_scheduler mark）。
- 无 scope 冲突，未回写父级 traceability.json（沿用 A4 判定）。

## 未验证 / 风险

- **真实 Gemini DR 端到端未跑**：`GEMINI_DR_REAL_CALLS=1` 真实浏览器路径未执行（需人工授权 + 登录健康 + DR 额度，NB1/NB2）。mock 路径证明接线，**不等于**真实研究成功。
- `optimize_prompt` 当前为本地「李教授」模板渲染（确定性构造合规 prompt）；A1 设想的「经 DeepResearchBrowser 普通会话精炼」属真实调用路径，gated off，未跑。
- 重试三参数为 A3 设计默认值，**最终数值待人工/planner 确认**(NB6)。
- `MAX_QUESTION_LEN=8000` 为 builder 默认上限（A3 未拍数），可调，非业务定值。

## 后续待办

- S04 orchestration-ui: 编排 O1→O6 链 + 监控可视化（可消费 `project_status`）。
- S05 verification-release: 人工开 `GEMINI_DR_REAL_CALLS=1` 做真实 activation-proof（async_state 轨迹 + DRResult + evidence_refs）。
- 人工确认重试默认值、凭证/ToS 合规、真实调用授权边界。

状态: C1–C4 全部置 reviewing，交 evaluator。本切片为核心实现 + 单测，**不声称**父 Epic 已端到端跑通（真实 DR 调用 gated off）。
