# Solar 用户使用指南

> **Solar v2.0** — AI 管理 AI，阳光牧场自动化协作系统
>
> 更新日期：2026-04-29 | 系统状态：239 Skills | 77 Hooks | 26 Rules | 46 Passed Sprints

---

## 目录

1. [Solar 是什么](#1-solar-是什么)
2. [5 分钟快速上手](#2-5-分钟快速上手)
3. [触发词大全](#3-触发词大全)
4. [核心命令](#4-核心命令)
5. [MCP 工具调用](#5-mcp-工具调用)
6. [Skills 速查](#6-skills-速查)
7. [Sprint 工作流](#7-sprint-工作流)
8. [知识库系统](#8-知识库系统)
9. [远程模式 + Codex Pro](#9-远程模式--codex-pro)
10. [故障排查 FAQ](#10-故障排查-faq)
11. [进阶定制](#11-进阶定制)

---

## 1. Solar 是什么

**Solar** 是一个 AI 管理 AI 的协作系统，让你（监护人）像管理团队一样指挥多个 AI 协同工作。

### 核心理念

```
┌─────────────────────────────────────────────────────────┐
│  董事长 (你) — 战略、审批                                │
│      ↓                                                  │
│  CEO (Solar) — 编排、验收、质量把关 (40%)               │
│      ↓                                                  │
│  牛马团队 (GLM/Gemini/DeepSeek) — 执行具体任务 (60%)    │
└─────────────────────────────────────────────────────────┘
```

**三原则**：
1. **AI 管理 AI** — 分配、评估、调度
2. **AI 开发 AI** — 让牛马写 Skill/Agent/MCP
3. **AI 优化 AI** — 基于数据优化分配策略

### 系统能力概览

| 类别 | 数量 | 说明 |
|------|------|------|
| Skills | 239 | 可调用技能，覆盖编码、分析、设计等领域 |
| Hooks | 77 | 自动触发的事件处理器 |
| Rules | 26 | 核心铁律，约束系统行为 |
| Bin 命令 | 18 | 命令行工具 |
| Sprints | 76 | 历史任务，46 个已通过 |
| Cortex 知识 | 732 | 结构化知识条目 |

---

## 2. 5 分钟快速上手

### 安装

详见 [INSTALL-AGENT.md](./INSTALL-AGENT.md)，核心步骤：

```bash
# 1. 克隆仓库
git clone https://github.com/lisihao/Solar ~/Solar
cd ~/Solar

# 2. 运行安装脚本
./install.sh

# 3. 验证安装
solar-harness status
```

### 第一次对话

启动 Claude Code 后，输入：

```
solar
```

Solar 会加载状态并宣告当前工作内容。

### 常用操作

| 你说 | Solar 做 |
|------|----------|
| "帮我分析这个代码" | 调用审判官深度分析 |
| "实现一个登录功能" | 委派建设者编码 |
| "查看 Cortex 知识库" | 查询相关知识 |
| "开始一个 Sprint" | 创建任务合约 |

---

## 3. 触发词大全

### 系统触发词

| 触发词 | 效果 |
|--------|------|
| `solar` / `打开solar` | 加载 Solar 系统宣告 |
| `Solar-Max` | 切换到项目模式（五阶段流程） |
| `批准` / `approved` | 执行宣告中的请求 |
| `省钱` / `经济` | 切换到经济模式（GLM 优先） |
| `用GLM` / `智谱` | 切换到 GLM 专用模式 |
| `平衡` / `正常` | 恢复平衡模式 |

### 功能触发词

| 触发词 | 效果 |
|--------|------|
| `洞察分析：<主题>` | 快速洞察（3 专家会审） |
| `深入洞察 <主题>` | 完整报告（8 阶段 + 持久化） |
| `深度洞察：<主题>` | 强制深度研究 |
| `小爱` / `呼叫小爱` | 远程 Mac mini 执行任务 |
| `训练模型` / `微调` / `fine-tune` | 调用 ML 实习生 |
| `/plan <任务>` | Plan-Act 执行任务 |
| `/plan preview <任务>` | 预览计划 |
| `/plan metrics` | 查看指标 |

### gstack 技能触发词

| 触发词 | 技能 | 用途 |
|--------|------|------|
| `浏览` / `打开网页` | `/browse` | 网页浏览 |
| `审查代码` | `/review` | 代码审查 |
| `排查` / `调查` | `/investigate` | 根因分析 |
| `QA` / `测试` | `/qa` | 质量保证 |
| `发布` / `上线` | `/ship` | 发布部署 |
| `基准测试` | `/benchmark` | 性能测试 |
| `办公时间` | `/office-hours` | YC 办公模式 |
| `自动评审` | `/autoplan` | 自动评审 |
| `谨慎` / `生产环境` | `/careful` | 谨慎模式 |
| `守护` / `安全模式` | `/guard` | 守护模式 |
| `冻结` / `限制编辑` | `/freeze` | 冻结模式 |
| `设计审查` | `/design-review` | 设计评审 |
| `设计咨询` | `/design-consultation` | 设计咨询 |
| `回顾` / `复盘` | `/retro` | 回顾会议 |
| `安全审计` | `/cso` | 安全审计 |

### Superpowers 技能触发词

| 触发词 | 技能 | 用途 |
|--------|------|------|
| `头脑风暴` / `brainstorm` | brainstorming | 创意生成 |
| `写计划` / `制定计划` | writing-plans | 计划编写 |
| `TDD` / `测试驱动` | test-driven-development | 测试驱动开发 |
| `系统化调试` / `逐步排查` | systematic-debugging | 调试方法 |

### Agent 触发词

| 触发词 | Agent | 用途 |
|--------|-------|------|
| `@Dev` | 开发者 | 代码实现 |
| `@QA` | 测试工程师 | 质量保证 |
| `@Test` | 测试员 | 测试编写 |
| `@Write` | 写作者 | 文档编写 |
| `@PM` | 产品经理 | 产品规划 |
| `@Secretary` | 秘书 | 记录整理 |
| `@Researcher` | 研究员 | 调研分析 |

### 意图场景触发词

| 场景 | 触发词示例 |
|------|-----------|
| 开发 | "我要开发..." / "实现一个..." |
| 研究 | "我要研究..." / "分析..." |
| 部署 | "我要部署..." / "发布..." |
| 查代码 | "查代码" / "搜索..." |
| 设计 | "设计一个..." / "架构..." |
| 测试 | "测试..." / "QA..." |
| 优化 | "优化..." / "改进..." |
| 文档 | "写文档..." / "整理..." |

---

## 4. 核心命令

### solar-harness — 协调器管理

```bash
# 查看协调器状态
solar-harness status

# 启动协调器
solar-harness start

# 停止协调器
solar-harness stop

# 重启协调器
solar-harness restart

# 系统诊断
solar-harness doctor

# 查看 tmux session
solar-harness sessions

# 派发 Sprint
solar-harness dispatch <sprint-id>

# 唤醒崩溃的 session
solar-harness wake <session-id>
```

### solar-survey — 系统扫描

```bash
# 扫描系统能力并输出 JSON
solar-survey

# 输出到文件
solar-survey > /tmp/survey.json
```

### solar-verify — 验证工具

```bash
# 验证 Sprint 合约
solar-verify <sprint-id>

# 验证所有
solar-verify --all
```

### solar-cache — 缓存管理

```bash
# 查看缓存
solar-cache list

# 清理缓存
solar-cache clean

# 更新缓存
solar-cache update
```

### solar-intent — 意图解析

```bash
# 解析用户意图
solar-intent "用户输入"

# 创建 Sprint
solar-intent create "需求描述"
```

### solar-remote-run — 远程执行

```bash
# 推送任务到远程
solar-remote-run push "任务命令"

# 拉取结果
solar-remote-run pull

# 运行远程任务
solar-remote-run run "命令"
```

### solar-net-detect — 网络检测

```bash
# 检测网络状态
solar-net-detect

# 测试连接
solar-net-detect test
```

### brain — 牛马调用

```bash
# 调用模型
brain complete "模型" "提示"

# 查看可用模型
brain list

# 切换模式
brain switch <mode>
```

### evolve — 系统进化

```bash
# 运行进化流程
evolve run

# 查看改进建议
evolve suggestions
```

### trajectory — 轨迹管理

```bash
# 记录轨迹
trajectory record "操作描述"

# 查看轨迹
trajectory list

# 分析轨迹
trajectory analyze
```

### kb-health-check — 知识库检查

```bash
# 检查 Cortex 知识库
kb-health-check

# 修复问题
kb-health-check --fix
```

### token-track — Token 追踪

```bash
# 查看使用统计
token-track stats

# 实时监控
token-track monitor
```

---

## 5. MCP 工具调用

### Brain Router — 多模型调度

在对话中，Solar 会自动调用 `mcp__brain-router__complete`：

```
调用专家分析问题：
- deepseek-r1 (审判官) — 深度推理
- deepseek-v3 (创想家) — 创意编码
- gemini-2.5-pro (稳健派) — 架构审查
- glm-5 (建设者/智囊) — 日常编码/战略决策
```

### Codex — GPT-5.4 首席科学家

```typescript
// 调用 Codex 执行任务
mcp__codex__codex({
  prompt: "任务描述",
  model: "claude-opus-4-7",
  cwd: "/path/to/project"
})
```

### OpenAlex — 学术数据

```
搜索学术文献：
- mcp__openalex__search_works
- mcp__openalex__search_authors
- mcp__openalex__search_sources
```

### MemPalace — 记忆宫殿（未部署）

```
日记写入（L3 待激活）：
- mcp__mempalace__mempalace_diary_write
```

### Playwright — 浏览器自动化

```
网页浏览（gstack 后端）：
- mcp__playwright__browser_navigate
- mcp__playwright__browser_snapshot
- mcp__playwright__browser_take_screenshot
```

---

## 6. Skills 速查

### 按类别分组 Top 50

#### 编码开发 (15)

| Skill | 用途 |
|-------|------|
| python-patterns | Python 设计模式 |
| typescript-expert | TypeScript 专家 |
| react-best-practices | React 最佳实践 |
| test-driven-development | TDD 测试驱动 |
| code-review | 代码审查 |
| debugging | 调试技巧 |
| api-design | API 设计 |
| refactoring | 重构 |
| clean-code | 整洁代码 |
| design-patterns | 设计模式 |
| coding-standards | 编码规范 |
| tdd-workflow | TDD 工作流 |
| python-testing | Python 测试 |
| javascript-testing | JavaScript 测试 |
| sql-pro | SQL 专家 |

#### 架构设计 (10)

| Skill | 用途 |
|-------|------|
| architecture | 软件架构 |
| system-design | 系统设计 |
| microservices-architecture | 微服务架构 |
| event-sourcing | 事件溯源 |
| cqrs-implementation | CQRS |
| saga-orchestration | Saga 编排 |
| distributed-tracing | 分布式追踪 |
| circuit-breaker-pattern | 熔断器 |
| api-gateway-configuration | API 网关 |
| service-mesh-implementation | 服务网格 |

#### DevOps 部署 (8)

| Skill | 用途 |
|-------|------|
| kubernetes-specialist | K8s 专家 |
| docker-patterns | Docker 模式 |
| cicd-pipeline-setup | CI/CD |
| terraform-infrastructure | Terraform |
| deployment-automation | 部署自动化 |
| monitoring | 监控 |
| logging-best-practices | 日志 |
| sre-engineer | SRE |

#### 数据分析 (7)

| Skill | 用途 |
|-------|------|
| data-engineer | 数据工程 |
| data-scientist | 数据科学 |
| data-visualization | 数据可视化 |
| exploratory-data-analysis | 探索性分析 |
| statistical-analysis | 统计分析 |
| ml-pipeline-automation | ML 流水线 |
| database-schema-design | 数据库设计 |

#### 产品管理 (6)

| Skill | 用途 |
|-------|------|
| product-manager | 产品经理 |
| product-strategist | 产品战略 |
| agile-sprint-planning | 敏捷规划 |
| requirements-gathering | 需求收集 |
| roadmap | 路线图 |
| stakeholder-communication | 利益相关者沟通 |

#### 写作文档 (4)

| Skill | 用途 |
|-------|------|
| technical-writer | 技术写作 |
| documentation-engineer | 文档工程 |
| academic-paper-composer | 学术论文 |
| grant-writing | 基金申请 |

### 完整 Skills 列表

查看所有 239 个技能：

```bash
ls ~/.claude/skills/
```

或访问在线仓库：`https://github.com/lisihao/Solar/tree/main/skills`

---

## 7. Sprint 工作流

### Sprint 是什么

Sprint 是 Solar 的任务执行单元，采用**合约驱动**模式：

```
你说需求 → 规划者写合约 → 建设者实现 → 审判官审核 → 通过/修复
```

### Sprint 状态流转

```
drafting → planning → building → testing → reviewing → shipped
                                                         ↓
                                                    failed/cancelled
```

### 典型工作流

#### 1. 提出需求

你告诉 Solar：

```
我要开发一个用户登录功能
```

#### 2. 规划者 (Solar) 创建合约

Solar 自动调用 `solar-intent create` 生成 Sprint 合约：

```markdown
# Sprint Contract

## Requirements
实现用户登录功能：邮箱/密码、JWT、刷新令牌

## Definition of Done
- [ ] 登录 API
- [ ] JWT 验证中间件
- [ ] 刷新令牌机制
- [ ] 3 个测试用例
```

#### 3. 建设者 (牛马) 实现

Solar 调用 GLM-5 或 deepseek-v3 执行编码：

```
mcp__brain-router__complete({
  model: "glm-5",
  prompt: "实现用户登录 Sprint..."
})
```

#### 4. 审判官 (deepseek-r1) 审核

```
mcp__brain-router__complete({
  model: "deepseek-r1",
  prompt: "审核以下代码..."
})
```

#### 5. 结果

- **PASS**: Sprint 标记为 `passed`，代码合并
- **FAIL**: 返回建设者修复，进入 Round 2

### Sprint 历史精选

查看 46 个已通过的 Sprint：[SPRINTS-HIGHLIGHTS.md](./SPRINTS-HIGHLIGHTS.md)

---

## 8. 知识库系统

### 四层架构

```
Layer 1: MEMORY.md — 跨会话锚点（200 行以内）
Layer 2: Cortex SQLite — 结构化知识（732 条）
Layer 3: MemPalace ChromaDB — 向量检索（未部署）
Layer 4: Subconscious JSONL — 教训记忆（19 条）
```

### Cortex 查询

```bash
# 关键词搜索
bun ~/.claude/core/cortex/unified-query.ts search "关键词" 10

# 证据链查询
bun ~/.claude/core/cortex/unified-query.ts evidence "关键词"

# 知识图谱
bun ~/.claude/core/cortex/unified-query.ts graph "关键词"
```

### sys_favorites — 精选知识

高价值结论自动存入 `sys_favorites` 表：

```sql
SELECT title, question, answer, importance
FROM sys_favorites
WHERE importance >= 7
ORDER BY created_at DESC
LIMIT 20;
```

### MEMORY.md — 记忆锚点

跨会话关键记忆，记录在：

```
~/.claude/projects/-Users-sihaoli/memory/MEMORY.md
```

包含：
- 历史优先于现状
- 牛马默认 Sonnet
- 主动 watcher
- pane UI 会误导
- ...

### Subconscious — 教训记忆

19 条历史教训，自动注入对话：

```
~/.solar/harness/brain/lessons.jsonl
```

---

## 9. 远程模式 + Codex Pro

### 远程架构

```
┌─────────────────────────────────────────────────┐
│  本机 (MacBook)                                  │
│  - Solar 协调器                                  │
│  - 规划者 + 建设者 (GLM)                         │
└─────────────────────────────────────────────────┘
                    ↓ Tailscale VPN
┌─────────────────────────────────────────────────┐
│  远程 (Mac mini)                                 │
│  - 💝 小爱 (GPT-4o) — 秘书任务                   │
│  - Codex Pro (GPT-5.4) — 首席科学家             │
└─────────────────────────────────────────────────┘
```

### 三角分工

| 角色 | 模型 | 职责 |
|------|------|------|
| 规划者 | Solar (Sonnet) | 任务拆解、编排 |
| 执行者 | 建设者 (GLM-5) | 编码实现 |
| 顾问 | Codex Pro | 重大技术方案决策 |

### 远程命令

```bash
# 推送任务到小爱
~/.claude/scripts/xiaoai-remote.sh "发邮件给团队提醒开会"

# 远程运行 Codex
solar-remote-run push "codex-research 微服务架构最佳实践"
solar-remote-run pull
```

### Codex 调用方式

```typescript
// 研究
mcp__codex__codex({
  prompt: "研究微服务架构模式",
  model: "claude-opus-4-7"
})

// 规划
mcp__codex__codex({
  prompt: "制定登录功能实现计划",
  profile: "planner"
})

// 编码
mcp__codex__codex-reply({
  threadId: "xxx",
  prompt: "继续实现 JWT 部分"
})
```

---

## 10. 故障排查 FAQ

### Q: Hook 不触发？

```bash
# 检查 hook 权限
ls -la ~/.claude/hooks/

# 检查 hook 语法
bash -n ~/.claude/hooks/xxx.sh

# 查看 hook 日志
tail -f ~/.solar/harness/.coordinator.log
```

### Q: Coordinator 卡死？

```bash
# 检查 tmux session
tmux ls

# 检查进程
ps aux | grep coordinator

# 重启协调器
solar-harness doctor
solar-harness restart
```

### Q: GLM 1210 错误？

```bash
# 检查 API Key
grep "glm" ~/.config/brain-router/config.json

# 切换模式
brain switch balanced

# 或直接用其他模型
mcp__brain-router__complete({
  model: "deepseek-v3",
  prompt: "..."
})
```

### Q: Sprint 派发失败？

```bash
# 检查 Sprint 状态
cat ~/.solar/harness/sprints/sprint-xxx.status.json

# 手动派发
solar-harness dispatch <sprint-id>

# 检查协调器状态
solar-harness coord-status
```

### Q: 知识库查询无结果？

```bash
# 检查 Cortex
kb-health-check

# 重建索引
sqlite3 ~/.solar/solar.db "VACUUM; REINDEX;"

# 检查数据
sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM cortex_sources;"
```

### Q: Pane 消失？

```bash
# 检查 tmux
tmux ls

# 恢复 session
solar-harness wake <session-id>

# 检查 bash 版本（必须是 5.x）
bash --version
```

---

## 11. 进阶定制

### 添加自定义 Hook

在 `~/.claude/hooks/` 创建脚本：

```bash
#!/usr/bin/env bash
# ~/.claude/hooks/my-custom-hook.sh

HOOK_NAME="my-custom"
PAYLOAD=$(cat)

# 处理逻辑
echo "处理结果..." >&2

echo "$PAYLOAD" | jq '.'
```

### 添加自定义 Skill

1. 复制模板：

```bash
cp -r ~/.claude/skills/template ~/.claude/skills/my-skill
```

2. 编辑 SKILL.md 和实现文件

3. 重启 Claude Code

### 编写 Sprint 合约模板

在 `~/.solar/harness/templates/` 创建模板：

```markdown
---
name: 任务名称
description: 详细描述
triggers: [auto/manual]
---

## Requirements

具体需求...

## Definition of Done

- [ ] 完成项1
- [ ] 完成项2

## Constraints

约束条件...
```

### 修改 Solar 行为

编辑 `~/.claude/CLAUDE.md` 添加自定义规则。

---

## 附录

### 快捷命令表

| 命令 | 效果 |
|------|------|
| `solar` | 加载系统 |
| `Solar-Max` | 项目模式 |
| `/plan <任务>` | 执行任务 |
| `/browse <URL>` | 浏览网页 |
| `/review` | 代码审查 |
| `/ship` | 发布 |

### 获取帮助

- GitHub Issues: https://github.com/lisihao/Solar/issues
- 文档: https://github.com/lisihao/Solar/blob/main/README.md
- Sprint 历史: [SPRINTS-HIGHLIGHTS.md](./SPRINTS-HIGHLIGHTS.md)

---

**文档版本**: v1.0 | **最后更新**: 2026-04-29
