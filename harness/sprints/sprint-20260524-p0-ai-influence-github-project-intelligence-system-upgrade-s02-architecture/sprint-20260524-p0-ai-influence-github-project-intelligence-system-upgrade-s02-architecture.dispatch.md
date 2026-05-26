# 协调器恢复指令 (Wake)

<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态 (防写入 hook 卡死)

在任何 Write/Edit/handoff/eval/status 更新之前，必须先用 Claude/Codex 的 **Read 工具**读取：

`~/.solar/STATE.md`

不要用 `cat` 替代这一步；本地 `state-read-enforcer.sh` hook 只认 Read 工具标记。

如果 Write/Edit hook 仍阻断，立刻 Read 上面的 STATE 文件后重试原写入一次，不要停在“已读”等待。

---

Sprint sprint-20260524-p0-ai-influence-github-project-intelligence-system-upgrade-s02-architecture 恢复：Workflow Guard 判定 PM+Planner 产物齐全，请读取 task_graph.json 并按 DAG/并行 builder 流程执行，不要绕开 graph scheduler。
