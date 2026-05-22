<!-- === STABLE PREFIX (cached) === -->
# Solar Harness Dispatch — AI Influence Digest 洞察扫描

<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态

在任何 Write/Edit/handoff/eval/status 更新之前，必须先读取：

`/Users/lisihao/.solar/STATE.md`

## 本次任务

- Sprint ID: `sprint-20260522-ai-influence-digest-scan`
- 角色: `planner/builder/evaluator by DAG node`
- PRD: `/Users/lisihao/.solar/harness/sprints/sprint-20260522-ai-influence-digest-scan/sprint-20260522-ai-influence-digest-scan.prd.md`
- Contract: `/Users/lisihao/.solar/harness/sprints/sprint-20260522-ai-influence-digest-scan/sprint-20260522-ai-influence-digest-scan.contract.md`
- Task Graph: `/Users/lisihao/.solar/harness/sprints/sprint-20260522-ai-influence-digest-scan/sprint-20260522-ai-influence-digest-scan.task_graph.json`

## 执行原则

1. 按 task graph 节点执行，不要越过 `depends_on`。
2. 所有内容抓取只允许公开来源，不得绕过登录墙。
3. GLM-5.1 是 digest 分析模型；不要用 Claude/Sonnet 做最终内容分析。
4. Gmail 失败只能降级为 preview，不得阻断知识库入库。
5. 每个节点完成后写对应 `N*-handoff.md`，并给出可复现验证证据。

