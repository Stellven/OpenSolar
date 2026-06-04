# PRD: AI Influence Insight / Social Signal Plane Convergence

## 1. Intent

把现有社交/X/YouTube/AI Influence 相关切片正式收口为唯一主线：

```text
AI Influence Insight / Social Signal Plane
```

这不是新开第四套社交系统，而是把：

- `Tech Hotspot Radar: Social Browser Backend for X 大咖监控`
- YouTube transcript / caption / ASR 分层重构
- AI Influence 社交报告与 raw evidence 链

统一收口为 Solar Research Radar 的 `Influence Source` 主入口。

## 2. Source of Truth

必须以以下材料为主：

- `/Users/lisihao/Solar/harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.prd.md`
- YouTube transcript / ASR 相关 sprint 产物

## 3. Product Positioning

社交层不再定义为：

- 舆情搬运
- 热门 tweet 摘要
- timeline 汇总
- engagement 排行

而定义为：

```text
观点驱动的研究发现系统
```

主逻辑：

```text
Statement
  -> Thesis
  -> Evidence Mapping
  -> Resonance / Contradiction
  -> AI Influence / Deep Research / Open-source Actions
```

## 4. Unified Epic Naming

统一社交主线命名为：

```text
AI Influence Insight / Social Signal Plane
```

后续不再允许：

- `X backend`
- `大咖监控`
- `社交趋势`
- `观点引擎`

各自长成独立产品名。

## 5. Unified Object Model

以下对象模型为唯一事实源：

- `InfluencerProfile`
- `Statement`
- `Thesis`
- `InfluenceEvidencePacket`

要求：

1. 旧 `social_posts`、`big_name_viewpoints`、transcript artifacts 都要映射到统一对象模型
2. 高模型只能消费 `InfluenceEvidencePacket`
3. 洞察输出必须从 `Thesis` 而不是从 raw posts 直接生成

## 6. MVP Operator Builder Slices

必须拆成以下 7 个 builder-facing slices：

### Slice I1 — InfluencerSeedRegistry

- scope:
  - people / org / source seed registry
  - tiers / categories / topic tags
  - role_at_time metadata

### Slice I2 — StatementCollector

- scope:
  - X
  - Bluesky
  - YouTube
  - Blog
  - HN
  - later: GDELT / SEC / podcast

### Slice I3 — StatementNormalizer

- scope:
  - normalize text / time / language / source type
  - mark quote / reply / marketing / transcript quality

### Slice I4 — ThesisExtractionOperator

- scope:
  - claim
  - topic
  - stance
  - modality
  - time horizon
  - viewpoint cluster

### Slice I5 — ThesisMappingOperator

- scope:
  - thesis -> paper
  - thesis -> GitHub
  - thesis -> conference
  - thesis -> product release
  - thesis -> finance event
  - thesis -> major news

### Slice I6 — InfluenceEvidencePacketCompiler

- scope:
  - compress thesis + mapped evidence
  - attach local scores
  - generate questions-for-high-model

### Slice I7 — InfluenceInsightCompiler

- scope:
  - Influencer Insight Card
  - Thesis Brief
  - Resonance Seed
  - AI Influence Topic
  - Deep Research Seed
  - Open-source Project Brief
  - Finance / Event Watch
  - Action Queue

## 7. Migration DAG

```text
现有 X / Browser backend line
  -> source collection slice
     - account scan
     - post collection
     - browser fallback
     - cooldown / rate limits

现有 YouTube transcript / ASR line
  -> long-form statement evidence slice
     - caption acquisition
     - transcript quality gate
     - quote locatability

现有 AI Influence social report chain
  -> downstream insight/report consumers

统一主线:
  AI Influence Insight / Social Signal Plane
    -> seed registry
    -> statement collection
    -> normalization
    -> thesis extraction
    -> mapping
    -> packet compiler
    -> insight compiler
```

迁移要求：

1. X backend 不再被当成完整洞察系统
2. YouTube transcript 不再被当成洞察系统本体，只作为长内容证据层
3. 旧 `social semantic extracts / big_name_viewpoints / propagation chains` 必须重新映射到 `Statement / Thesis / Evidence Packet / Resonance Seed`

## 8. Cross-source Contract

### With HF Paper Insight Flow

- thesis topic mapping
- paper support / contradiction lookup
- shared Deep Research seed schema
- shared resonance classifier

### With GitHub Hotspot Radar / Code Signal Plane

- thesis.topic -> repo.topic / direction cluster
- social claims -> repo evidence support or contradiction
- shared AI Influence topic queue
- shared open-project brief / action queue

## 9. Quality Gates

必须显式落五类 gate：

- `Statement Gate`
- `Transcript Gate`
- `Thesis Gate`
- `Evidence Mapping Gate`
- `Compliance Gate`

## 10. Output Assets

统一输出资产：

- `Influencer Insight Card`
- `Thesis Brief`
- `Cross-source Resonance Seed`
- `AI Influence Topic`
- `Deep Research Seed Pack`
- `Open-source Project Brief`
- `Finance / Event Watch`
- `Action Queue`

## 11. Non-goals

- 不首批接满所有社交平台
- 不首批做超重观点准确率回溯系统
- 不首批重做 UI
- 不允许把 X backend 采集线误当完整洞察系统

## 12. Acceptance Criteria

1. 统一 Epic 名被写进 PRD / contract / handoff。
2. 7 个 MVP operator 的 builder slices 被显式写出。
3. 现有 X / YouTube 线迁移 DAG 被显式写出。
4. 与 HF / GitHub 的三源共振 contract 被显式写出。
5. 五类 quality gates 被显式写出。
6. 后续 builder 不允许把 X backend 当完整洞察系统继续建设。

---

## 背景 / Context

- 现状是 Solar 周边出现了三条独立但语义重叠的"社交信号"线：(1) `Tech Hotspot Radar / X 大咖监控 backend`、(2) YouTube transcript / caption / ASR 分层重构、(3) AI Influence 社交报告与 raw evidence 链。三条线各自开 sprint，各自定义对象，各自接 UI，导致 builder 反复造轮子、洞察输出无法相互引用。
- 本 sprint 不是新开第四套，而是把这三条线**收口**为 Solar Research Radar 的唯一 `Influence Source` 主入口：`AI Influence Insight / Social Signal Plane`。从社交平台采集变为"观点驱动的研究发现系统"：Statement → Thesis → Evidence Mapping → Resonance/Contradiction → AI Influence / Deep Research / Open-source Actions。
- 已落地证据：S1 (requirement-compiler-planner) **eval verdict=PASS**，产出 12 节 design.md（含 file boundary / slice contract / build steps / migration DAG / verification spine / compat / acceptance matrix / architecture guard / risks）+ S2-S5 plan + guard-decision (pass 5/5) + resource-binding (readonly) + bridged-artifact + Requirement IR (4 × P1: REQ-000..REQ-003)。
- 本次 dispatch 是 coordinator gate_prd_schema 触发：PRD 缺 8 个 schema 必需 section。PM 修复 PRD 不重做 S1 实施，不动 capsule_plan / Contracts.yaml / design / plan / handoff / eval。

## 用户问题 / Problem

- **PB-1 三线漂移**：X backend / YouTube transcript / AI Influence report 三个 sprint 各自定义对象（`social_posts` / `big_name_viewpoints` / transcript artifacts），高模型消费时要做三次反向映射，洞察输出无法跨线引用。
- **PB-2 "大咖监控" 被误当洞察系统**：X backend 只采账号 + 帖子 + 转发链，但下游被消费时被当成完整 AI Influence 洞察系统；YouTube transcript 同理被当成洞察本体而不是"长内容证据层"。
- **PB-3 raw posts 直接生成洞察**：当前洞察输出从 raw post 直接 LLM-generate，而不是先抽 Thesis 再做证据映射，导致洞察不可复用、不可审计、不可与论文/repo 共振。
- **PB-4 五类 quality gate 缺失**：Statement / Transcript / Thesis / Evidence Mapping / Compliance gate 没有显式 enforcement，洞察质量飘忽。
- **PB-5 命名碎片**：`X backend / 大咖监控 / 社交趋势 / 观点引擎` 四个名字在不同 sprint 各自长成产品名，无统一 epic 入口。
- **PB-6 PRD schema gate 阻塞**：PRD 缺 8 必需 section，coordinator gate_prd_schema 反复触发，本次 dispatch 即修复入口。

## 用户故事 / User Stories

- **US-01 (PM / Sprint 收口者)**：作为 sprint 收口者，我希望本 PRD 显式声明 `AI Influence Insight / Social Signal Plane` 是唯一 Epic 名，旧四个名字一律不允许在后续 sprint 出现。
  - 验收：PRD §4 显式禁止 4 个旧名 + 本 sprint contract / handoff 已统一命名 ✅ (S1 contract canonical name 确认)。
- **US-02 (Builder)**：作为 builder，我希望被派到 I1-I7 的具体 slice，知道这个 slice 只产出 Statement / Thesis / EvidencePacket / Insight 中的某一类，不要我去"做完整社交系统"。
  - 验收：PRD §6 列出 7 个 builder-facing slice ✅。S2-S5 plan 已细化（S1-plan.md §2）。
- **US-03 (Migration owner)**：作为旧 X backend / YouTube transcript 迁移者，我希望 PRD 显式告诉我我的产物映射到新对象模型的哪个角色（采集 / 长证据 / downstream），不要我自己猜。
  - 验收：PRD §7 Migration DAG + §5 Unified Object Model 已显式 ✅。
- **US-04 (高模型 / 洞察消费者)**：作为高模型，我只消费 `InfluenceEvidencePacket`，不直接读 raw posts。
  - 验收：PRD §5 第 2 条明示 ✅。
- **US-05 (Cross-source 共振消费者)**：作为 HF Paper Insight / GitHub Hotspot Radar 消费者，我希望 thesis topic 在三源之间统一 schema，能直接跨源拉支持/反证。
  - 验收：PRD §8 Cross-source Contract + 共享 schema ✅。
- **US-06 (Quality gate enforcer)**：作为 evaluator，五类 gate (Statement / Transcript / Thesis / Evidence Mapping / Compliance) 必须可程序化校验。
  - 验收：PRD §9 + S1-design §7 verification spine ✅。
- **US-07 (PM 修 schema)**：本 sprint gate 不再循环。
  - 验收：本切片即修复，`validate.sh prd` → PASS。

## 功能需求 / Requirements

- **FR-1 统一 Epic 命名**：所有后续 PRD / contract / handoff 必须用 `AI Influence Insight / Social Signal Plane`；禁用 `X backend / 大咖监控 / 社交趋势 / 观点引擎`。
- **FR-2 唯一对象模型**：`InfluencerProfile / Statement / Thesis / InfluenceEvidencePacket` 是唯一事实源；旧对象映射 adapter 必须存在但不暴露到下游。
- **FR-3 7 个 builder-facing slice (I1-I7)**：
  - I1 InfluencerSeedRegistry — people/org/source seed registry + tiers/categories/topic tags + role_at_time
  - I2 StatementCollector — X / Bluesky / YouTube / Blog / HN（后续：GDELT / SEC / podcast）
  - I3 StatementNormalizer — text/time/language/source_type 规范化 + quote/reply/marketing/transcript quality 标记
  - I4 ThesisExtractionOperator — claim / topic / stance / modality / time horizon / viewpoint cluster
  - I5 ThesisMappingOperator — thesis → paper / GitHub / conference / product release / finance event / major news
  - I6 InfluenceEvidencePacketCompiler — 压缩 thesis + 证据 + local score + questions-for-high-model
  - I7 InfluenceInsightCompiler — Influencer Insight Card / Thesis Brief / Resonance Seed / AI Influence Topic / Deep Research Seed / Open-source Project Brief / Finance/Event Watch / Action Queue
- **FR-4 Migration DAG**：X backend → source collection slice；YouTube transcript → long-form statement evidence；AI Influence report → downstream insight consumers。统一主线见 PRD §7。
- **FR-5 五类 Quality Gate**：Statement / Transcript / Thesis / Evidence Mapping / Compliance gate 必须 enforcement，缺失阻断派单。
- **FR-6 Cross-source 共振 contract**：与 HF Paper Insight Flow 共享 thesis topic mapping + Deep Research seed schema + resonance classifier；与 GitHub Hotspot Radar 共享 thesis.topic → repo.topic / AI Influence topic queue / open-project brief / action queue。
- **FR-7 8 类输出资产**：Influencer Insight Card / Thesis Brief / Cross-source Resonance Seed / AI Influence Topic / Deep Research Seed Pack / Open-source Project Brief / Finance/Event Watch / Action Queue。
- **FR-8 PRD schema 合规**：通过 `validate.sh prd`（本切片即修复）。

## 约束 / Constraints

- **环境**：macOS arm64 (lisihaodeMac-mini.local) / bash 5.3.9 / Solar Harness 4-pane / coordinator + chain-watcher + graph-scheduler 在线。
- **路径白名单**：本 PM 切片只允许写 `<sid>.prd.md` 和新增 `<sid>.prd.html`；禁动 capsule_plan / Contracts.yaml / contract / S1-design / S1-plan / S1-handoff / S1-eval / S1-guard-decision / S1-resource-binding / S1-bridged-artifact / S1-physical-plan / acceptance_verdict / requirement_ir。
- **Source of Truth 锁定**：必须以 `/Users/lisihao/Solar/harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md` 和 `sprint-20260525-tech-hotspot-radar-...-s01-requirements.prd.md` 为主，YouTube ASR 相关 sprint 产物为辅；不允许引入 ADR 外的对象模型。
- **不重做 S1**：S1 已 eval=PASS（含 12 节 design + S2-S5 plan + guard pass 5/5）；PM 不动 S1 任何 artifact。
- **不直接派 builder**：S2-S5 必须走 planner handoff 链路，不允许 PRD 直接派 builder。
- **不允许 X backend 当洞察本体**：FR-3/§7 强制，builder 必须按 I1-I7 切片划分。
- **secrets**：raw_intent / Statement / Transcript artifact 在写盘前必须 redact；禁打印 API key / OAuth / 个人手机号 / 邮箱。
- **合规**：所有采集必须通过 Compliance Gate（含 ToS / robots.txt / 用户授权检查）；YouTube transcript / X post / Bluesky 任一来源不符合 ToS 立即停采。
- **PM 角色边界**：不写实施代码、不动 status 到 implementation、不跳 PRD schema；本 PRD 修复后保持当前状态。

## 风险 / Risks

| 风险 | 影响 | 缓解 / 状态 |
|------|------|--------------|
| 旧三线团队不接受统一 Epic 命名 | 收口失败 / 命名碎片继续 | FR-1 在 PRD/contract/handoff 三处 enforcement；S1 contract canonical name 确认 ✅ |
| `InfluenceEvidencePacket` schema 未定 → 高模型消费混乱 | 洞察不一致 | S1-design §4 已细化 EvidencePacket schema；Requirement IR REQ-002 ✅ |
| Statement Gate / Transcript Gate / Thesis Gate 没有可程序化校验 | 质量飘忽 | S1-design §7 verification spine + S1-plan §2 测试命令 ✅ |
| YouTube ASR 转录质量低 → Statement 错位 | Thesis 抽取错 | Transcript Gate 含 quality threshold + quote_locatability 标记 (PRD §6 I3 + §9) |
| X backend 团队继续把 raw post 直接进 insight | 绕过 Thesis 抽取 | FR-2 + §5 强制 高模型只能消费 EvidencePacket / Thesis Gate 拦 |
| HF / GitHub Cross-source 共振 contract 不对齐 | 三源协同失败 | PRD §8 + 共享 schema；S1-design §4.4 已含 ThesisExtractor 两个候选 + kill criteria ✅ |
| Compliance Gate 缺失 → ToS 违规 | 法律 / 平台封号风险 | §9 显式列 Compliance Gate；I2 collector 必须先过 gate |
| 五类 gate 全部塞到一个大 evaluator → 不能独立运行 | gate 互相阻断 | S1-plan §2 拆 S2-S5，每节点独立 gate |
| 旧对象 (social_posts / big_name_viewpoints / transcript) 不可逆迁移 | 历史数据丢 | §5 第 1 条强制映射 adapter；S1-design §8 compat/rollout ✅ |
| S1 已 PASS 但 PRD schema fail → coordinator 拉回 drafting | 链路循环 | 本切片即修复 ✅ |
| 多 sprint 引用 `X 大咖监控` 等旧名 → grep 不能找全 | 漂移 | FR-1 列入 lint 检查（未来 sprint） |
| 7 个 builder slice 边界模糊 → builder 抢任务 | 重复实现 | S1-design §3 file boundary map + §4 slice contract ✅ |
| Deep Research seed schema 与 paper insight 不一致 | 跨源失败 | §8 显式共享 schema |

## 开放问题 / Open Questions

- **OQ-01** I2 StatementCollector 后续接 GDELT / SEC / podcast 的优先级？现在 P0 只 5 源（X/Bluesky/YouTube/Blog/HN）。**Owner**：后续 expansion sprint。
- **OQ-02** Thesis Gate 的 threshold（modality clarity / stance confidence / time horizon explicitness）默认值？需要积累 ≥200 thesis 后做 calibration。**Owner**：calibration sprint。
- **OQ-03** Compliance Gate 是否需要每平台单独 ToS checker？X / Bluesky / YouTube 政策差异大。**Owner**：legal review sprint。
- **OQ-04** `Resonance Seed` 与 `Cross-source Resonance Seed` 是否同一对象？PRD §10 列了两个名字。**Owner**：S1-design §4 已澄清是同对象，本 PRD 应该统一为 `Cross-source Resonance Seed`（待 S2 实施时回写 PRD）。
- **OQ-05** I7 InsightCompiler 8 类输出资产是否需要全部首批交付？还是 P0 只交付 4 类（Influencer Card / Thesis Brief / Resonance Seed / Action Queue）？**Owner**：S2 plan 决议。
- **OQ-06** Action Queue 的下游消费者（人 vs 自动化）未定。**Owner**：UX / downstream sprint。
- **OQ-07** ThesisExtractor 是否用 high-model（Opus）还是 local-model？S1-design §4.4 给了两候选 + kill criteria，但最终决议留 S2。**Owner**：S2 plan。

## 架构交接 / Planner Handoff

### Inputs to Planner

- 本 PRD（12 原始节 + 本次补的 8 schema 必需节）。
- ADR：`/Users/lisihao/Solar/harness/docs/architecture/ai-influence-insight-social-signal-plane.adr.md`（Source of Truth）。
- 上游 sprint：`sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements.prd.md`。
- YouTube transcript / ASR 相关 sprint 产物。
- **本 sprint 已交付的 S1 产物**（全部 eval=PASS，PM 不动）：
  - `<sid>.contract.md` — 4 invariants + 7 builder slices canonical
  - `<sid>.S1-design.md` — 12 节 design (file boundary §3 / slice contract §4 / build steps §5 / migration DAG §6 / verification spine §7 / compat §8 / acceptance↔validation matrix §9 / architecture guard §10 / risks §11)
  - `<sid>.S1-plan.md` — Gate map §1 + S2-S5 plans + cross-cutting §3 + sprint stop_rules §4 + evidence bundle §5
  - `<sid>.S1-handoff.md` — Summary / Changed Files / Verification / Capability / Scope / Risks / Not Done
  - `<sid>.S1-guard-decision.json` — `decision=pass`, 5/5 checks
  - `<sid>.S1-resource-binding.json` — `mode=readonly`, no network
  - `<sid>.S1-bridged-artifact.md` — adapter bridge §A..§F
  - `<sid>.requirement_ir.json` — 4 × P1 (REQ-000..REQ-003)
  - `<sid>.S1-eval.md` / `.S1-eval.json` — verdict=PASS
  - `<sid>.acceptance_verdict.json` / `.capsule_plan.json` / `.Contracts.yaml`

### 7 Builder Slices ↔ S2-S5 节点映射（S1-plan §2 已细化）

| Slice | 主题 | S2-S5 节点 |
|-------|------|-----------|
| I1 | InfluencerSeedRegistry | S2 (含 registry schema + tier/category) |
| I2 | StatementCollector | S2 / S3 (5 平台并行) |
| I3 | StatementNormalizer | S3 |
| I4 | ThesisExtractionOperator | S3 (含 §4.4 ThesisExtractor 2 候选 + kill criteria) |
| I5 | ThesisMappingOperator | S4 (含 cross-source 共振) |
| I6 | InfluenceEvidencePacketCompiler | S4 (高模型 only 消费) |
| I7 | InfluenceInsightCompiler | S5 (8 输出资产) |

### 5 Quality Gates ↔ S2-S5 节点

| Gate | 主题 | enforcement 节点 |
|------|------|-------------------|
| Statement Gate | source / format / dedup | S2/S3 |
| Transcript Gate | quote_locatability / quality threshold | S3 |
| Thesis Gate | modality / stance / time horizon | S3/S4 |
| Evidence Mapping Gate | thesis ↔ paper/repo/conference 映射可逆 | S4 |
| Compliance Gate | ToS / robots.txt / 用户授权 | S2 (collector 启动前) |

### Migration DAG 映射 (来自 PRD §7)

| 旧线 | 新角色 | 处理 sprint |
|------|--------|-------------|
| X / Browser backend | source collection slice (I2 一部分) | 兼容 adapter → 渐进迁移 |
| YouTube transcript / ASR | long-form statement evidence (I2/I3) | 兼容 adapter |
| AI Influence social report | downstream insight consumer (I7 输出) | 重新接到统一对象 |
| social semantic extracts / big_name_viewpoints / propagation chains | 必须映射到 Statement / Thesis / Evidence Packet / Resonance Seed | S2/S3 实施 |

### Cross-source Contract (来自 PRD §8)

| 对接系统 | 共享 | 节点 |
|---------|------|------|
| HF Paper Insight Flow | thesis topic mapping + paper support/contradiction lookup + Deep Research seed schema + resonance classifier | S4 |
| GitHub Hotspot Radar / Code Signal Plane | thesis.topic → repo.topic / direction cluster + social claims → repo evidence + AI Influence topic queue + open-project brief + action queue | S4/S5 |

### 给 Coordinator 的明确指令

- **不要重做 S1**：S1 eval verdict=PASS（含 12 节 design + S2-S5 plan + guard 5/5）。本 PM 切片只补 PRD schema 8 节，不动 S1 任何 artifact。
- **触发机制**：PRD mtime 已刷新；coordinator 下一 tick 重跑 `validate.sh prd` → PASS → 关闭 gate；sprint 当前 `status=drafting / phase=spec / handoff_to=pm`，PM 处理后应让 sprint 进入 planner 走 S2 节点（chain-watcher 自动接）。
- **不动其他 18 份 S1 artifact**：包括 capsule_plan / Contracts.yaml / contract / S1-design / S1-plan / S1-handoff / S1-eval / S1-guard-decision / S1-resource-binding / S1-bridged-artifact / S1-physical-plan / acceptance_verdict / requirement_ir。

### 未尽事项

- **OQ-01..OQ-07** 全部留 S2+。特别是 OQ-04 (Resonance Seed 命名统一) / OQ-07 (ThesisExtractor 模型选型) 必须 S2 决议。
- **5 平台采集器实现** I2 (X / Bluesky / YouTube / Blog / HN) 留 S3。
- **8 类输出资产实现** I7 留 S5；P0 可能只交付 4 类（OQ-05）。
- **Cross-source 共振 calibration** 需要 ≥200 thesis 后做权重调（OQ-02）。

### Knowledge Context

Knowledge Context: dispatch-embedded unified-context used (Mirage degraded, QMD/Solar DB/Obsidian Vault 命中)。

### Harness Modules Used

Harness Modules Used: harness-knowledge (dispatch-embedded unified-context)。
