# Mission
**DistributedScheduler** - 任务调度与智能路由，验收口径：多牛马并行任务分发 + 负载均衡 + 失败重试机制

# Constraints
- 监护人信任是最高原则
- 上下文 = 生命，让牛马干活保持自我空间
- 复杂任务(>40%上下文)必须先规划再执行
- 涉及自己的事情要专家团队审核

# Current Plan (Top-5)
1) **🔥 DistributedScheduler** - 任务调度与智能路由 (P95)
2) 强化长时运行能力 (P95)
3) 身份验证 - 监护人白名单机制 (P92)
4) 外置记忆服务 v2 - 实际落地使用 (P90)
5) Solar Web Dashboard v2 - 实时监控 (P85)

# Decisions (Why)
- [2026-02-10] **修复 Claude Code Hook 配置格式**：发现 settings.json 中 `"PostToolUse:Write": ["script.sh"]` 格式完全错误，Claude Code 不认识！正确格式需要嵌套结构 `{"matcher":"Write","hooks":[{"type":"command","command":"script.sh"}]}`。这解释了为何所有 PostToolUse hooks 从未被触发。
- [2026-02-09] 采用 STATE.md 而非 session.md：STATE.md 结构固定、短而硬，专注任务状态；session.md 是自动检查点，内容较杂。两者分工明确。
- [2026-02-09] 状态持久化机制核心：CLAUDE.md=长期制度，STATE.md=短期态势。对话丢了不怕，这两根柱子还在。
- [2026-02-09] 结构化快照而非散文摘要：五段式槽位(Mission/Constraints/Decisions/Progress/Next Actions)强制输出结构，压缩也丢不了关键变量。
- [2026-02-09] SessionEnd 自动 git WIP commit：会话结束时自动保存代码变更，不依赖人工记忆。
- [2026-02-09] **外置记忆服务设计 (专家审核后)**：
  - 采用 MVP 策略：Layer 1 (Event Log) + Lite Layer 3 (简化 State Updater) 先行，2周内可用
  - Event schema_version 字段解决事件版本演进问题
  - mem_snapshots 快照表避免全量重放性能问题
  - 置信度评分 (0-1) 标注编译状态可靠性
  - Human Override Manager 处理手动 STATE.md 修改优先级
  - 审核专家：技术宅(Gemini 2.5 Pro)、千里马(Gemini 3 Pro)、思考驼(DeepSeek R1)

# Progress

**In-Progress**: 无

**Blocked**: 无

**本周完成** (2026-02-11):
- /insight 状态持久化修复 ✅ (checkpoint + 断点恢复)
- ThunderMLX FlashAttention 演示 ✅ (阶段性验收)
- /insight v3.0 升级 (八阶段+四专家互评)
- CLAUDE.md Token 优化 (-76%体积)
- 人格注入机制 (personality-injector.sh + 考核日志)
- STATE.md 优化 (可验收目标格式)

<details>
<summary>历史完成 (点击展开)</summary>

- Docker Sandbox
- Intent Engine
- Solar Web Dashboard
- STATE.md 状态持久化机制
- 外置记忆服务 v1.0 (四层架构)
- Master Brain 身份保护机制
- Observation Compressor

</details>


<!-- AUTO-PROGRESS -->
**自动进度追踪** (2026/2/11):
- 当前: /insight 状态持久化修复 ✅ 已完成
- 上次: ThunderMLX 演示 ✅ (阶段性验收)
<!-- /AUTO-PROGRESS -->
# Next Actions (Exact)

## 待定 - 等待昊哥指示下一步

可选方向 (Current Plan):
1. DistributedScheduler - 任务调度与智能路由
2. 强化长时运行能力
3. 身份验证 - 监护人白名单机制

## 待办归档 (已完成项)

<details>
<summary>已完成 (点击展开)</summary>

- [x] 创建 ~/.claude/STATE.md
- [x] 创建 rules/state-persistence.md 固化规则
- [x] 确认 CLAUDE.md 已有状态持久化规则
- [x] 验证：compact 后成功从 STATE.md 恢复状态
- [x] Hook 自动提醒更新
- [x] SessionEnd 自动检查 + Git WIP commit
- [x] 结构化快照指令写入 rules 和 Hook 提醒
- [x] 外置记忆服务设计 + 专家审核
- [x] 实现 Layer 1: Event Sourcing
- [x] 实现 Lite Layer 3: 简化版 State Updater
- [x] Hook 集成
- [x] STATE.md 自动更新三机制

</details>
