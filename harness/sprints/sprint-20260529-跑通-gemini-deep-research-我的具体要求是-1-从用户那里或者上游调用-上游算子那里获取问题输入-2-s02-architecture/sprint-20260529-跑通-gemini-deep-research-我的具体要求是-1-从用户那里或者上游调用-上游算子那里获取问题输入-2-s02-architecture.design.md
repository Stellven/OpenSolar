# Design — S02 架构设计与接口契约

> Epic: 跑通 Gemini Deep Research 浏览器自动化算子 · slice = architecture
> epic_id: `epic-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2` · depends_on: S01_requirements (passed 前不得派 builder)
> Knowledge Context: solar-harness context inject used (degraded: mirage_path:no_results)

## 0. 切片定位

本切片把 S01 的 outcome 矩阵 (O1-O6) 转成**系统分层、接口契约、数据模型、失败恢复、观测、兼容/迁移**。
不写实现代码 (实现在 S03_core_runtime / S04_orchestration_ui)。本切片产出设计文档供 S03/S04 落地。

## 1. 上游输入 (来自 S01, 尚未闭环 — 必须在本切片钉死)

S01 已标记三个开放项, 本切片**必须**给出确定设计:
- **O1 上游算子输入契约**: 上游调用形态 (函数 / 队列 / 文件 dispatch / HTTP) — 本切片定为接口契约的第一项。
- **O5 成功判据**: DR「执行成功」的机器可判定义 (DR 完成标志 + 末尾分类文献块存在 + 文献条数下限)。
- **重试边界**: 最大次数 / 超时 / 退避策略, 防死循环。

## 2. 系统分层 (control plane / data plane)

| 平面 | 组件 | 职责 |
|---|---|---|
| Control | Operator Orchestrator (状态机) | 驱动 O1→O6 状态流转, 重试决策, 成功判定 |
| Control | Input Adapter | 统一用户输入与上游算子调用两源 (O1) |
| Data | Prompt Optimizer Stage | 注入「李教授」系统提示, 取回优化后提示词 (O2) |
| Data | Gemini Browser Session | 网页自动化: new chat / 提交 / 点「确定研究」/ 轮询 (O2-O5) |
| Data | DR Result Collector | 抓取 DR 输出 + 分类文献 (标题+链接) (O6) |
| Cross | Observability | 状态/事件/截图/日志, 供监控与回归证据 |

## 3. 接口边界与数据模型 (要点, 细化在 builder 节点)

- **输入契约**: `ResearchRequest{ source: user|upstream_operator, raw_question, options }`。
- **阶段交接**: `OptimizedPrompt` (O2→O3), `DRPlan` (O3→O4 确认), `DRRunHandle` (O4→O5 监控)。
- **结果**: `DRResult{ status, body, references[]{category,title,url} }`。
- **状态机**: states = INPUT→OPTIMIZE→SUBMIT→CONFIRM→MONITOR→{DONE|RETRY|FAIL}; 状态可由事件重建 (对齐 S03 验收)。

## 4. 失败恢复与观测

- 每个阶段定义可重试错误 vs 终止错误; MONITOR 阶段失败 → 退避重试到上限 → 标 FAIL。
- 观测: 状态转移事件流 + 关键截图 + DR 轮询日志; 供 S05 做 activation-proof / 回归。

## 5. 兼容、冲突、降级策略 (contract 硬性)

- **兼容**: 不破坏现有 harness wake/dispatch/status 主路径; operator 作为新组件接入, 不改既有 API。
- **冲突回写**: S01 已指出父 epic task_graph 的 write_scope (`lib/ types/ status-server/ ui/`) 偏通用模板, 与浏览器自动化算子领域不完全贴合 → 本切片须核对并在需要时**回写父级 traceability.json** (Stop Rule)。
- **降级**: Gemini 不可用 / 登录态失效 / ToS 限制 → 降级为「返回明确失败 + 人工接管信号」, 不静默成功。

## 6. Stop Rules (contract)
- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标 passed。
- 发现 scope 冲突必须回写父级 traceability。
- 只交付本切片, 不得声称父 Epic 已完成。
