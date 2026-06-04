# 协调器恢复指令 (Wake)

<!-- SOLAR_STATE_READ_PREFLIGHT -->
## 必须先读状态 (防写入 hook 卡死)

在任何 Write/Edit/handoff/eval/status 更新之前，必须先用 Claude/Codex 的 **Read 工具**读取：

`~/.solar/STATE.md`

不要用 `cat` 替代这一步；本地 `state-read-enforcer.sh` hook 只认 Read 工具标记。

如果 Write/Edit hook 仍阻断，立刻 Read 上面的 STATE 文件后重试原写入一次，不要停在“已读”等待。

---

Sprint sprint-20260521-thunderomlx-anthropic-cache-usage-observability 恢复：Workflow Guard 判定 PRD 已就绪，请 Planner 读取 PRD/contract，产出 design.md、plan.md、task_graph.json；完成后再进入 builder DAG 派发。原因: pm_prd_ready; violations=[]
