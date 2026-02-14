# DECISIONS.md - 决策账本

> 只记"会影响后续"的选择，格式固定

---

## 2026-02-12

### 采用三文件抗失忆架构

**决策**: 使用 STATE.md + DECISIONS.md + CLAUDE.md 三文件分离，而非单一状态文件

**原因**:
- STATE.md 变化频繁（每次任务进展都更新）
- DECISIONS.md 追加式（只增不改，审计友好）
- CLAUDE.md 相对稳定（项目级常驻指令）
- 职责分离便于维护和 git diff

**影响**:
- 每次启动需读 2 个文件（STATE + DECISIONS）
- 压缩前需更新 STATE.md
- 重大决策需追加 DECISIONS.md

**回滚方案**:
- 合并为单一 PROJECT_STATE.md
- 删除 DECISIONS.md，决策内嵌 STATE.md

---

### 对话降级为缓存 (第零原则)

**决策**: 把 Claude 对话从"数据库"降级为"L0 缓存"，文件系统作为唯一真相源

**存储层级**:
- L0 Cache = Claude 对话 (最易失)
- L1 Cache = 工作区文件 (持久)
- L2 Cache = .solar/ 状态文件 (结构化)
- WAL+CKP = git 历史 (不可变)

**唯一真相源**:
- .solar/STATE.md
- .solar/DECISIONS.md
- .solar/LOG/cmd.md | bench.md | errors.md
- .solar/EXPERIMENTS/ (可选)

**铁律**: 感觉要压缩 → 先写文件 → 再让它压

**影响**:
- 心智模型转变：对话丢了不可怕
- 任何有价值信息必须落盘才算存在
- git = WAL，每个 commit = checkpoint

**回滚方案**: 无需回滚，这是认知层面的升级

---

### "先读后写"强制机制 (Hook 阻断)

**决策**: 使用 PreToolUse hook + exit 2 强制 Claude 先读 STATE.md 再允许 Write/Edit

**原因**:
- 规则注入 (Option 2) 已实现，但"注入 ≠ 使用"
- 需要给规则装上"牙齿"，真正强制执行
- PreToolUse hook 支持 exit 2 阻断操作

**实现**:
- `state-read-tracker.sh` (PostToolUse): 读 STATE.md 后写 marker 文件
- `state-read-enforcer.sh` (PreToolUse): Write/Edit 前检查 marker，没有就 exit 2 阻断
- marker 位置: `/tmp/solar-state-markers/state-read-$SESSION_ID`

**影响**:
- 新会话如果不先读 STATE.md，任何文件写入都会被阻断
- 强制恢复态势感知，从流程上杜绝失忆

**回滚方案**:
- 从 settings.json 移除两个 hook
- 删除 ~/.claude/hooks/state-read-*.sh

---

### Prompt 策略绕过小爱任务队列

**决策**: 修改 email-monitor.sh 的 prompt 开头为"收到！立即执行命令。"

**原因**:
- 小爱的任务管理系统会拦截"【邮件任务】"类 prompt
- 导致任务被加入队列而非立即执行
- 直接命令式语言可绕过队列

**影响**:
- 小爱立即执行邮件整理任务
- 不再返回"已加入队列"

**回滚方案**:
- 恢复原 prompt 格式
- 或修改小爱的任务队列判断逻辑

---

### Task-Specific SOP 体系

**决策**: 为 5 类任务建立专用 SOP，把"感觉"变成"证据链"

**5 类任务**:
1. **性能优化/Profiling**: 每轮必交 Bottleneck Table + Hypothesis + Fix Plan + Validation
2. **大规模重构/架构改造**: RFC 驱动，4 Phase (兼容层→双写→切流量→删旧)
3. **多文件 Feature 开发**: 先读 ARCH.md，按模块逐个落地 + checkpoint
4. **调参/实验/Benchmark**: registry.md 汇总，可排序比较
5. **Bug 修复/紧急热修**: Reproduce→RootCause→Fix→Test→Verify

**新增文件**:
- `.solar/ARCH.md` - 架构文档 (模块边界/数据流/约定)
- `.solar/RFC/_TEMPLATE.md` - RFC 模板 (4-phase 迁移)
- `.solar/EXPERIMENTS/_TEMPLATE.md` - 实验模板
- `.solar/EXPERIMENTS/registry.md` - 实验注册表
- `~/.claude/rules/task-sop.md` - SOP 铁律文件

**原因**:
- 性能结论没有 commit hash 和环境信息 = 无法复现
- 大重构没有分阶段 = 容易"改完更烂"
- 多文件开发没有接口契约 = 模块边界混乱
- 实验结果散落 = 无法横向比较

**影响**:
- 任务开始前需识别类型，匹配对应 SOP
- 输出更结构化，可追溯可回滚
- 开发节奏更可控

**回滚方案**:
- 删除相关模板文件
- 从 rules/ 移除 task-sop.md

---

### 报告工程化流水线 (长文报告抗压缩)

**决策**: 为 2-5万字深度报告创建专用模板系统 (STATE/OUTLINE/SOURCES/NOTES/CLAIMS)

**原因**:
- 长报告最容易被上下文压缩"干碎"
- 需要把"大脑"搬到文件系统
- 文献管理、证据追踪需要结构化
- /insight skill 当前输出是任务导向，不是报告导向

**模板结构**:
- `REPORT/STATE.md` - 态势板 (Topic/Thesis/Progress/Risk)
- `REPORT/OUTLINE.md` - 大纲=编译目标 (每节claim/sources/artifacts)
- `REPORT/SOURCES.md` - 文献总账 (citation key/结论/可信度/thesis关系)
- `REPORT/NOTES/*.md` - 单篇笔记 (Problem/Method/Results/Weakness)
- `REPORT/CLAIMS.md` - 主张-证据矩阵 (支撑/反例)

**影响**:
- /insight skill 需要集成此模板
- 长报告生成需按模板流程执行
- 检查点机制与 STATE.md 联动

**回滚方案**:
- 删除 `~/.claude/templates/REPORT/` 目录
- /insight 恢复原有输出方式

---
