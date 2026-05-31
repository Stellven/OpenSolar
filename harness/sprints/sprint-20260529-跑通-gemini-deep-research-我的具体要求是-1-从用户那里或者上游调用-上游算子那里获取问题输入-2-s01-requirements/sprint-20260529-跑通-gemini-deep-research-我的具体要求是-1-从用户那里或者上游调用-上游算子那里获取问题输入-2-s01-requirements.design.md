# Design — S01 需求拆解与追踪矩阵

> Epic: 跑通 Gemini Deep Research 浏览器自动化算子 · slice = requirements
> epic_id: `epic-20260529-跑通-gemini-deep-research-我的具体要求是-1-从用户那里或者上游调用-上游算子那里获取问题输入-2`
> Knowledge Context: solar-harness context inject used (degraded: mirage_path:no_results — 无该 sprint 直接命中, 仅 obsidian-wiki 旁系条目)

## 0. 切片定位 (本切片做什么 / 不做什么)

本切片是 **需求工程**, 不是实现。产出是「可验收 outcome 矩阵 + 风险边界 + 非-builder 工作清单 + epic→子sprint 追踪矩阵」。
系统分层/接口在 S02_architecture, 实现在 S03/S04, 端到端验证在 S05。本切片**绝不**实现任何浏览器自动化代码。

## 1. 用户原始需求解构 (DECONSTRUCT)

目标系统 = 一个驱动 Gemini 网页版 Deep Research 的自动化算子, 完整链路:

| ID | Outcome (功能结果) | 一句话 |
|----|-------------------|--------|
| O1 | 输入获取 | 从用户**或上游算子调用**获取问题输入 (双输入源: 人工 + 上游算子接口) |
| O2 | 提示词优化 | 打开 Gemini 网页 → new chat → 注入「李教授」提示词优化系统提示 + 原始问题 → 取回优化后提示词 |
| O3 | 调用 Deep Research | 用优化后提示词触发 Gemini Deep Research 模式并提交任务 |
| O4 | 确认研究计划 | DR 产出规划后, agent 点击「开始/确定研究」按钮 |
| O5 | 监控 + 失败重试 | 监控 DR 执行直到产出; 失败则重新调用, 直到成功为止 |
| O6 | 端到端流程测试 | 完成一次完整链路测试; 最终输出按类别整理的文献 (论文/新闻/博客) 标题+链接 |

附属规格 (约束输入, 不是身份): 「李教授」提示词优化器 = 4-D 方法论 (解构/诊断/开发/交付), 工作语言英文, 强制要求 DR 尽力搜索高价值文献并在末尾分门别类输出 标题+链接, 优先源 = 指定期刊/实验室/会议/工业展清单。

## 2. 诊断: 清晰度与缺口 (DIAGNOSE)

- **输入契约模糊**: 「上游算子调用」的接口形态 (函数/队列/文件/HTTP) 未定义 → 必须在 S02 钉死, 本切片标为开放项。
- **成功判据主观**: O5「执行成功」缺机器可判定义 (DR 完成标志? 文献条数下限? 末尾分类块存在?) → 必须给出可验收阈值。
- **第三方实时站点**: Gemini 网页 DOM/按钮会变, 需登录态, 受 ToS 约束 → 高脆弱、需人工凭证, 属非-builder 边界。
- **重试边界缺失**: 「一直重试到成功」需上限 (最大次数/超时/退避), 否则死循环。
- **提示词优化器与 DR 的边界**: O2 产出的「优化后提示词」如何回灌到 O3, 是否同会话, 未定义。

## 3. 本切片交付物结构 (DEVELOP)

builder 在本切片产出三份分析文档 + 一份 handoff:
1. **outcome 矩阵** (`*.requirements-matrix.md`): O1–O6, 每条含 [验收标准] + [风险边界] + [可机器验证信号]。
2. **非-builder 工作清单** (`*.non-builder-work.md`): 列出不能直接派 builder 的工作 (Gemini 账号/登录态/凭证, ToS 合规判断, 实时 DOM 选择器维护, 浏览器自动化技术栈拍板, 「成功」语义的人工确认) + 理由。
3. **epic→子sprint 追踪矩阵** (`*.traceability-map.md`): O1–O6 映射到 S02–S05, 标注上游依赖 / 下游影响 / 未闭环项。
4. **handoff** (`*.handoff.md`): 汇总, 写明上游依赖、下游影响、未闭环项 (PRD scope 硬性要求)。

## 4. 验收对齐 (DELIVER)

| 契约验收项 | 由哪个节点满足 | 机器可验证信号 |
|---|---|---|
| 每个 outcome 都有验收标准和风险边界 | R1 | matrix 含 6 行, 每行有「验收/风险」两列非空 |
| 明确哪些工作不能直接派 builder | R2 | non-builder 清单 ≥1 项且每项有理由 |
| 生成父 epic 到子 sprint 的 traceability map | R3 | map 覆盖 O1–O6 且映射到 S02–S05 |

## 5. 风险与停止规则 (来自 contract)

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标 passed。
- 发现 scope 冲突必须回写父级 traceability。
- 只交付本切片, 不得声称父 Epic 已完成。
