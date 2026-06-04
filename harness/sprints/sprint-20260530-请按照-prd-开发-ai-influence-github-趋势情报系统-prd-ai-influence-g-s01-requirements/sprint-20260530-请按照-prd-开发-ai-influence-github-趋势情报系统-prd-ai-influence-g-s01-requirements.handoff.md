# Handoff — S01 需求拆解与追踪矩阵

sprint_id: `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements`
epic_id: `epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g`
handoff_to: `planner`
completed_at: `2026-05-30T22:50:00Z`

---

## Sprint 总览

S01 将用户原始 PRD（12 章节，4186 chars）拆解为 **10 个可验收 Requirement Groups（RG1-RG10）**，定义了 **42 条可量化验收标准**、**10 条非目标**、**6 维约束矩阵**、**RG→S02-S05 追踪矩阵（覆盖率 100%）** 和 **5 个跨切片依赖**。

DAG 执行路径: N1(PRD 分析) → N2(验收标准) + N3(非目标/约束) → N4(追踪矩阵) → N5(汇总)
Gates 通过: G_PRD_ANALYZED ✅ → G_ACCEPTANCE_DEFINED ✅ → G_BOUNDARIES_DEFINED ✅ → G_TRACEABILITY_MAPPED ✅ → G_HANDOFF_READY

---

## 一、需求组列表（RG1-RG10）

| RG | 名称 | PRD 来源 | 最高优先级 | P0 AC 数 | 核心关注点 |
|---|---|---|---|---|---|
| RG1 | 多源项目发现引擎 | §5 | P0 | 3 | Topic/Trending/Tracked 三路发现，Cross-source P1 |
| RG2 | 增量快照与数据模型 | §6 | P0 | 4 | Repo Master/Snapshot(append-only)/Evidence Atom |
| RG3 | 增长异常检测与热度评分 | §7 | P0 | 4 | Sudden Hot Detector, Heat Score, 同品类分位数 |
| RG4 | 本地预处理与 Token 经济学 | §3.3 | P0 | 4 | ThunderOMLX+Qwen3.6 清洗, Token budget guard |
| RG5 | 数据源接入矩阵 | §4 | P0 | 3 | GitHub REST/GraphQL/Events P0, X/YouTube P1, GH Archive P2 |
| RG6 | 爆火归因模型 | §8 | P1 | 0 | 5 维归因, evidence_id 可追溯 |
| RG7 | 项目策划生成 | §9 | P1 | 0 | S/A-tier 自动触发, 4 章节策划单 |
| RG8 | AI Influence 报告生成 | §10 | P0 | 4 | 今日核心判断, 爆火解析, Markdown 日报 |
| RG9 | 告警机制 | §11 | P1 | 0 | Critical(三源共振), High(跟踪库增长) |
| RG10 | 高阶进化功能 | §12 P2 | P2 | 0 | GH Archive 回放, 代码级分析, Star Bot 反欺诈 |

**PRD 章节覆盖率: 12/12 = 100%**（§1-§12 全部映射到 RG1-RG10）

---

## 二、验收矩阵（完整）

### P0 验收标准（22 个 pytest 骨架，可直接转化）

| RG | AC ID | 验收标准 | 量化条件 |
|---|---|---|---|
| RG1 | RG1-AC1 | Topic Discovery 日扫覆盖率 | 每日产生 >= 180 个唯一 repo_id，成功率 >= 90% |
| RG1 | RG1-AC2 | Trending Discovery 频率覆盖 | Daily/Weekly/Monthly 各返回 >= 20 个 repo |
| RG1 | RG1-AC3 | Tracked Repo 监控频率动态调整 | heat_score>=80 → 15min; <30 → <=6h; 误差<=20% |
| RG2 | RG2-AC1 | Repo Snapshot append-only 约束 | 同一 repo_id 两次 INSERT 后 COUNT=2，禁止 UPDATE |
| RG2 | RG2-AC2 | Repo Master 必填字段完整性 | repo_id/tracking_status/first_seen_at NOT NULL |
| RG2 | RG2-AC3 | Evidence Atom 字段完整性 | evidence_type/importance_score/source_ref NOT NULL; score [0,1] |
| RG2 | RG2-AC4 | stars_delta_24h 准确性 | delta = snapshot[t] - snapshot[t-24h]，误差=0 |
| RG3 | RG3-AC1 | Sudden Hot 触发精度 | stars_delta_24h >= max(50, avg_7d*3) AND 95%分位 → flag=True, <5s |
| RG3 | RG3-AC2 | Sudden Hot 漏报率 | 100 阳性用例中 TP >= 95 |
| RG3 | RG3-AC3 | Heat Score 公式权重完整性 | 所有维度权重和=1.0, 输出值 [0,1]（**待 S02 补全 WARN-01**） |
| RG3 | RG3-AC4 | 同品类分位数精度 | 与 numpy.percentile 参考实现误差 <= 0.01 |
| RG4 | RG4-AC1 | 本地模型处理时延 | 单仓库端到端 <= 30s，输出 >= 1 个 Evidence Atom |
| RG4 | RG4-AC2 | Token 预算拦截 | 超限自动拦截，不发出 API 调用（**预算值待 S02 定义 WARN-02**） |
| RG4 | RG4-AC3 | Evidence Atom 输出合法性 | importance_score [0,1], source_ref 非空, type 在枚举内 |
| RG4 | RG4-AC4 | 禁止全量 repo 送云端 | 所有云端请求 token_count < 8000 |
| RG5 | RG5-AC1 | GitHub REST 接入成功率 | 10 个 repo 拉取成功率 >= 95% |
| RG5 | RG5-AC2 | GitHub Events API 去重 | 相同 event_id 两次写入后 DB 仅保留 1 条 |
| RG5 | RG5-AC3 | GitHub Rate Limit 自适应 | HTTP 429 时暂停+等待 reset_at，不抛异常 |
| RG8 | RG8-AC1 | 日报定时生成 SLA | 00:00 UTC 触发后 2h 内生成 |
| RG8 | RG8-AC2 | 日报结构完整性 | "今日核心判断">=50 字 + "今日爆火项目"1-3 个含归因 |
| RG8 | RG8-AC3 | Markdown 格式合规 | markdownlint --disable MD013 通过，0 错误 |
| RG8 | RG8-AC4 | 日报与 Sudden Hot 一致性 | 爆火项目集 = 当日 Sudden Hot repo_id 集，diff=0 |

### P1 验收标准（20 条，集成测试覆盖）

| RG | AC ID | 验收标准 | 量化条件 |
|---|---|---|---|
| RG1 | RG1-AC4 | Cross-source Mention 入队 | 识别后 24h 内送入分析队列，积压 <= 1000 |
| RG2 | RG2-AC5 | Project Analysis Card 自动生成 | heat_score 达标时自动生成，含 4 必填字段 |
| RG3 | RG3-AC5 | Early Potential Detector 精度 | F1-score >= 0.80 |
| RG5 | RG5-AC4 | X/社媒字段提取 | author_tier/stance/engagement_delta 缺失率 <= 20% |
| RG5 | RG5-AC5 | YouTube Transcript 关联 | 关联准确率 >= 80%（人工标注集） |
| RG6 | RG6-AC1 | 归因覆盖率 | 每个 Sudden Hot 事件输出 >= 1 条归因 |
| RG6 | RG6-AC2 | Evidence 可追溯性 | orphan 归因率 = 0%（外键有效） |
| RG6 | RG6-AC3 | 归因准确率 | 20 个已知爆火仓库主归因匹配率 >= 70% |
| RG6 | RG6-AC4 | 5 维归因枚举完整性 | 系统枚举包含且仅包含 5 维 |
| RG7 | RG7-AC1 | 自动触发响应时间 | heat_score 达标后 48h 内生成策划单 |
| RG7 | RG7-AC2 | 策划单内容完整性 | 4 章节，每章节 >= 100 字（中文） |
| RG7 | RG7-AC3 | 可执行行动指引 | >= 1 条明确建议，不允许"待定"占位 |
| RG8 | RG8-AC5 | 技术趋势地图 | >= 3 个技术方向，每方向引用 >= 1 仓库 |
| RG9 | RG9-AC1 | Critical 告警触发延迟 | 三源共振后 15min 内送达 |
| RG9 | RG9-AC2 | High 告警触发延迟 | 24h star 增长 >10% 后 30min 内送达 |
| RG9 | RG9-AC3 | 告警内容完整性 | 包含 repo_url/触发原因/证据 ID/时间戳 |
| RG9 | RG9-AC4 | 告警去重 | 同仓库同级别 1h 内仅一次 |
| RG10 | RG10-AC1 | GH Archive 覆盖率 | 30 天事件 >= 90% 处理 |
| RG10 | RG10-AC2 | Star Bot 识别率 | 人工标注集 50 个，识别率 >= 80% |
| RG10 | RG10-AC3 | 代码级架构分析 | 输出 dependency_graph + complexity_score, <= 5min |

**验收标准总计: 42 条（P0: 22 / P1: 17 / P2: 3）**

### 风险边界总览

| RG | 高风险 | 中风险 | 低风险 | 最关键风险 |
|---|---|---|---|---|
| RG1 | 1 | 1 | 1 | GitHub API 速率限制导致扫描不完整 |
| RG2 | 1 | 1 | 1 | append-only 存储规模膨胀 |
| RG3 | 2 | 2 | 0 | Heat Score 权重不完整(WARN-01); 冷启动分位数不稳定 |
| RG4 | 2 | 1 | 0 | ThunderOMLX 未部署; Token 预算值未定义(WARN-02) |
| RG5 | 2 | 1 | 0 | GitHub Token 耗尽; X API 成本 |
| RG6 | 0 | 2 | 1 | LLM 归因质量波动 |
| RG7 | 0 | 0 | 2 | LLM 生成质量; S/A-tier 阈值未定义 |
| RG8 | 1 | 1 | 1 | 上游数据为空导致报告缺失 |
| RG9 | 0 | 2 | 1 | X API 不可用降级; 告警风暴 |
| RG10 | 0 | 0 | 2 | P2 功能占用 P0 资源; BigQuery 成本 |

---

## 三、非目标清单（10 条）

| # | 非目标 | 来源 | 说明 |
|---|---|---|---|
| NG-1 | 不做 Trending 榜单搬运 | PRD §2 反模式 #1 | 不简单爬取转发，不以 star 总数排序 |
| NG-2 | 不做无差别 Token 消费 | PRD §2 反模式 #3 | 禁止完整 repo 直送高级模型 |
| NG-3 | 不输出套话式洞察 | PRD §2 反模式 #4 | 禁止无证据支撑的泛泛结论 |
| NG-4 | 不做 star 总数排名系统 | PRD §2/#3.1 | 以增长斜率和分位数为核心 |
| NG-5 | 不做 GH Archive 历史回放 | PRD §12 P2 | 离线补偿为 P2，首批不交付 |
| NG-6 | 不做代码级架构分析 | PRD §12 P2 | 超出 Token 经济学约束，P2 延后 |
| NG-7 | 不做 Star Bot 反欺诈过滤 | PRD §12 P2 | 水军识别 P2，首批报告加 disclaimer |
| NG-8 | 不做实时流式处理 | PRD §5 推导 | 系统以批处理 + cron 为主 |
| NG-9 | 不做通用数据分析平台 | PRD §1 推导 | 只服务 GitHub 趋势分析 |
| NG-10 | 首批不交付 Dashboard UI | PRD §12 P1 | 首批仅 CLI/脚本 + Markdown 报告 |

---

## 四、约束矩阵（6 维）

| 约束维度 | 约束条件 | 影响 RG | S02 架构决策 |
|---|---|---|---|
| API Rate Limit | REST 5000 req/h, Events 300/page×10, GraphQL 5000 pts/h, X Free=500/month | RG1, RG5 | A-1: token pool 轮换 |
| Token 预算 | 每次云端 ≤ 8K tokens/call (建议), 每日 ≤ 500K (建议) | RG4 | A-5: budget cap + 降级策略 |
| 数据保留 | Repo Snapshot 严格 append-only, 归档 >90 天 | RG2 | A-2: 归档周期/格式 |
| 安全边界 | secrets 禁止硬编码, 平台 ToS 合规, 本地数据不外传 | 全局 | A-7: secrets management |
| 性能 SLA | 日报端到端 ≤ 30min | RG1, RG4, RG8 | A-6: pipeline 时间预算 |
| 并发调度 | 4 路发现互不阻塞, 本地/云端可流水线并行 | RG1, RG4 | A-6: 编排框架选型 |

### 需先经 S02 架构设计的工作（7 项）

| 序号 | 决策项 | 原因 | 影响 RG |
|---|---|---|---|
| A-1 | GitHub API Token Pool + 速率控制 | 4 路并发 + 15min 高频 | RG1, RG5 |
| A-2 | 数据存储 Schema 详细设计 | append-only 实现方式选型 | RG2 |
| A-3 | 本地推理 Pipeline 架构 | ThunderOMLX 集成 + M4 资源评估 | RG4 |
| A-4 | Evidence Atom 格式与压缩策略 | JSON schema + 压缩比目标 | RG4, RG6 |
| A-5 | 云端推理 Budget 管控 | 每次/每日上限 + 超限降级 | RG4, RG8 |
| A-6 | Pipeline 编排框架 | asyncio/celery/cron 选型 | RG1, RG4, RG8 |
| A-7 | Secrets Management | API keys 存储方案 | 全局 |

---

## 五、Traceability Map（RG→Sprint 映射）

| RG | S02 架构 | S03 核心实现 | S04 调度/UI | S05 验证 | 覆盖切片数 |
|---|---|---|---|---|---|
| RG1 | ● A-1, A-6 | ● 发现逻辑 | ● 调度监控 | ● 集成测试 | 4 |
| RG2 | ● A-2, 归档策略 | ● DDL, trigger | — | ● Schema 测试 | 3 |
| RG3 | ● 公式补全, 评分架构 | ● Detector, Score | ● 触发下游 | ● 精度测试 | 4 |
| RG4 | ● A-3, A-4, A-5 | ● Pipeline, Guard | — | ● 时延测试 | 3 |
| RG5 | ● A-1, A-7 | ● 连接器 | — | ● 成功率测试 | 3 |
| RG6 | ● A-4, 归因架构 | ● 归因逻辑 | ● Sudden Hot 触发 | ● 准确率测试 | 4 |
| RG7 | ● Tier 阈值, 模板 | ● Brief 生成 | ● 自动触发 | ● 完整性测试 | 4 |
| RG8 | ● A-5, A-6 | ● 模板引擎, MD 生成 | ● Cron, 降级 | ● SLA 测试 | 4 |
| RG9 | ● 渠道选型, 阈值 | ● 触发+去重 | ● 路由/投递 | ● 延迟测试 | 4 |
| RG10 | ● 可扩展性预留 | — | — | ● 文档化 | 2 |

**覆盖率: 10/10 RG = 100%，无遗漏**

---

## 六、跨切片依赖（5 个）

### DEP-1: S02 → S03（阻塞方向: S02 阻塞 S03）
S03 核心实现依赖 S02 的全部 7 个架构决策项 (A-1~A-7)。S02 延迟将直接阻塞 S03 启动。
**影响等级: 高**

### DEP-2: S02 → S04（阻塞方向: S02 阻塞 S04）
S04 调度/自动化依赖 S02 的 A-6(编排框架)、告警渠道选型、Tier 阈值定义。
**影响等级: 高**

### DEP-3: S03 → S04（阻塞方向: S03 部分阻塞 S04）
S04 的告警路由(RG9)、报告调度(RG8)、策划触发(RG7)需要 S03 的评分引擎(RG3)先就绪。S04 可先搭框架+桩接口，S03 就绪后做端到端集成。
**影响等级: 中**

### DEP-4: S03+S04 → S05（阻塞方向: S03 和 S04 共同阻塞 S05）
S05 的 22 个 P0 测试、端到端 pipeline 验证、日报 SLA 验证均需 S03+S04 全部产出就绪。
**影响等级: 高**

### DEP-5: S03 内部跨 RG 管线依赖
```
RG5(数据源) → RG1(发现) → RG2(快照) → RG3(评分) → RG6(归因)
                                                  ↓
RG4(本地预处理) ──────────────────────────→ RG8(报告) → S04(调度)
                                                  ↓
                                             RG7(策划) → S04(触发)
                                                  ↓
                                             RG9(告警) → S04(路由)
```
S03 内部串行化风险，影响 S04 集成和 S05 验证启动时间。
**影响等级: 中**

---

## 七、上游依赖

| 上游来源 | 依赖内容 | 状态 |
|---|---|---|
| Epic PRD (epic.md) | 用户原始需求 12 章节, 4186 chars | ✅ 已消化 |
| Epic Traceability (traceability.json) | 5 个子 sprint 定义: S01→S02→S03/S04→S05 | ✅ 已引用 |
| Solar Contract (contract.md) | DoD 6 条: D1-D6 | ✅ 全部满足（见下方） |

---

## 八、下游影响（S02-S05）

| 下游切片 | S01 向其输出的关键产物 | 阻塞状态 |
|---|---|---|
| **S02 架构设计** | 10 个 RG 定义 + 42 条 AC + 6 维约束矩阵 + 7 个架构决策项 + 4 个 PRD 异常预警 (WARN-01~04) | S01 完成后可启动 |
| S03 核心实现 | 22 个 P0 测试骨架 + 首批交付边界 + 非目标屏蔽清单 | 等 S02 完成后启动 |
| S04 调度/UI | 调度范围(6 个 RG) + 非目标 NG-10 屏蔽 Dashboard | 等 S02 完成后启动 |
| S05 验证发布 | 42 条 AC 作为验证基准 + 22 个 P0 测试函数名 | 等 S03+S04 完成后启动 |

### S02 必须处理的 PRD 异常预警

| 编号 | 描述 | 严重程度 | 影响 AC |
|---|---|---|---|
| WARN-01 | Heat Score 6 维权重和 = 0.85（缺 0.15） | 高 | RG3-AC3 |
| WARN-02 | Token 预算上限 PRD 未给具体值 | 高 | RG4-AC2 |
| WARN-03 | S/A-tier heat_score 阈值未定义 | 中 | RG7-AC1 |
| WARN-04 | X API 访问级别未确认 | 中 | RG5-AC4, RG9-AC1 |

---

## 九、覆盖度审计

### Contract DoD 逐条核对

| DoD | 要求 | 达成状态 | 证据来源 |
|---|---|---|---|
| D1 | PRD 12 章节全部拆解为 >=8 个 requirement groups | ✅ 10 个 RG (RG1-RG10), 章节覆盖率 100% | N1-handoff |
| D2 | 每个 RG 有验收标准、优先级、风险边界 | ✅ 42 条 AC + P0/P1/P2 标注 + 高/中/低风险缓解 | N2-handoff |
| D3 | 非目标清单 >= 5 条 | ✅ 10 条 (§2 反模式×4 + §12 P2×3 + 架构推导×3) | N3-handoff |
| D4 | Traceability map: RG → S02-S05 | ✅ 10/10 RG 全部映射, 覆盖率 100% | N4-handoff |
| D5 | 跨切片依赖 >= 3 个 | ✅ 5 个依赖, 全部标明阻塞方向 | N4-handoff |
| D6 | handoff.md 写明上游依赖、下游影响、未闭环项 | ✅ 本文档第七/八/十节 | 本文档 |

### Gate 通过记录

| Gate | 节点 | 状态 | 通过时间 |
|---|---|---|---|
| G_PRD_ANALYZED | N1 | ✅ passed | 2026-05-30T21:16:37Z |
| G_ACCEPTANCE_DEFINED | N2 | ✅ passed | 2026-05-30T21:36:37Z |
| G_BOUNDARIES_DEFINED | N3 | ✅ passed | 2026-05-30T22:07:50Z |
| G_TRACEABILITY_MAPPED | N4 | ✅ passed | 2026-05-30T22:21:02Z |
| G_HANDOFF_READY | N5 | ✅ (本节点) | 2026-05-30T22:50:00Z |

### Outcome→AC→Gate 覆盖度

每个 RG 的每条 AC 均绑定到对应 gate 链路：
- RG 定义 → G_PRD_ANALYZED
- AC 定义 + 风险 → G_ACCEPTANCE_DEFINED
- 非目标/约束 → G_BOUNDARIES_DEFINED
- Sprint 映射 + 依赖 → G_TRACEABILITY_MAPPED
- 汇总 + 审计 → G_HANDOFF_READY

**无遗漏 outcome: 每个 outcome 都有 AC + gate。**

---

## 十、未闭环项（Open Questions）

| 编号 | 问题 | 当前状态 | 归属切片 | 阻塞 AC |
|---|---|---|---|---|
| OQ-1 | Heat Score 权重和 = 0.85，缺 0.15 的维度定义 | WARN-01, 待 S02 补全 | S02 | RG3-AC3 |
| OQ-2 | Token 预算上限具体值未定义 | WARN-02, 临时值 8000 tokens | S02 | RG4-AC2 |
| OQ-3 | S/A-tier heat_score 阈值分级表 | WARN-03, 待 S02 输出 | S02 | RG7-AC1 |
| OQ-4 | X API 订阅级别确认 | WARN-04, 待项目方确认 | S02 | RG5-AC4, RG9-AC1 |
| OQ-5 | ThunderOMLX/Qwen3.6 在 Mac mini M4 上的可用性 | 未实测 | S02 | RG4-AC1 |
| OQ-6 | 告警投递渠道选型（Slack/本地通知/其他） | 未决定 | S02 | RG9 全部 |
| OQ-7 | 日报端到端 SLA 30min 是推导值 | 待 S02 基准测试确认 | S02 | RG8-AC1 |

---

## 变更文件

| 文件 | 操作 | 说明 |
|---|---|---|
| `sprint-...-s01-requirements.handoff.md` | 新建 | Sprint-level 最终 handoff，Write Scope 内 |

---

## Verification Evidence

```
执行命令:
  Read: ~/.solar/STATE.md (preflight)
  Read: sprint-...-s01-requirements.task_graph.json (N1-N4 全部 passed)
  Read: sprint-...-s01-requirements.contract.md (DoD D1-D6)
  Read: sprint-...-s01-requirements.N1-handoff.md (10 RG 定义 + 拓扑图)
  Read: sprint-...-s01-requirements.N2-handoff.md (42 条 AC + 22 个 P0 测试骨架)
  Read: sprint-...-s01-requirements.N3-handoff.md (10 条非目标 + 6 维约束 + 7 架构决策)
  Read: sprint-...-s01-requirements.N4-handoff.md (RG→Sprint 映射 + 5 个依赖)
  Read: epic-...-g.traceability.json (5 切片定义)

结果摘要:
  - N1-N4 全部 passed，gate G_PRD_ANALYZED~G_TRACEABILITY_MAPPED 全部通过
  - 10 个 RG × 42 条 AC × 10 条非目标 × 6 维约束 × 5 个依赖 — 全部汇入本 handoff
  - DoD D1-D6 逐条核对通过
  - 覆盖率审计: PRD 章节 100%, RG→Sprint 映射 100%, AC→Gate 100%
```

---

## Capability / KB Usage Evidence

- **[harness-knowledge] Solar Unified Context**: dispatch 中注入的 `<solar-unified-context>` 已使用，命中 QMD solar-wiki / Solar DB / Solar Obsidian Vault / Mirage (degraded)。N1-N4 各自运行 `solar-harness context inject` 命中 Mirage/QMD/Solar DB 进行 PRD 和既有合约比对。
- **[harness-graph] Solar-Harness Runtime**: 读取 task_graph.json 验证 N1-N4 全部 passed；读取 STATE.md preflight。
- **[harness-graph] solar-graph-scheduler (dag.validate)**: 验证 N5 依赖 N4=passed 已满足；确认 5 个 gate 链路完整。
- **Superpowers (workflow.planning, documentation, coverage-analysis)**: 使用系统化覆盖度审计方法：DoD×AC×Gate 三维交叉验证。

---

## Scope Compliance

- 只修改了 Write Scope 声明的文件: `sprint-...-s01-requirements.handoff.md` ✅
- Read Scope 文件 (N1-N4 handoff) 仅读取，未修改 ✅
- 未修改 epic / prd / task_graph 等源文件 ✅
- 未将父 sprint S01 标记为 passed ✅

---

## Known Risks

| 风险 | 等级 | 说明 |
|---|---|---|
| S02 成为全局瓶颈 | 高 | 10 个 RG + 7 个架构决策项全部依赖 S02 输出 |
| WARN-01 跨切片传播 | 高 | Heat Score 权重缺口影响 S03/S04/S05 |
| X API 可用性 | 中 | 影响 Cross-source/Critical 告警双源能力 |
| 性能 SLA 未实测 | 中 | 30min SLA 为推导值，依赖 ThunderOMLX 实际吞吐 |

---

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge (dispatch-injected unified context), harness-graph (dag.validate, task_graph read), Solar-Harness Runtime (STATE preflight), Superpowers (workflow.planning, documentation, coverage-analysis)
