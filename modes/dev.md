# Solar 开发模式

> 当用户说 "我要开发" 时加载此上下文

## 项目装载 (我要开发 <项目名>)

1. **路径匹配:** `~/<名>` → `~/Projects/<名>` → `~/Code/<名>`
2. **状态收集:**
   - Git: `git branch --show-current` + `git status --short` + `git log --oneline -5`
   - Solar: `.solar/project-state.md` + `.solar/flow-state.json`
   - 文档: `CLAUDE.md` + `docs/*_DESIGN.md`
3. **显示横幅:** 项目/分支/阶段/任务/待办
4. **询问继续:** 未完成任务 → 是否继续

## 状态持久化

用户说 "好/可以/OK/确认/通过" → @Secretary 写入 `.solar/project-state.md`

## Agent 宣告 (强制)

```
┌─ [emoji] [Agent名] ────────────────────┐
│ Task: [任务目标]                        │
│ Plan: 1. [步骤1]  2. [步骤2]           │
└─────────────────────────────────────────┘
```

| 任务类型 | Agent | Emoji |
|---------|-------|-------|
| 调研/分析 | Researcher | 🔬 |
| 架构/设计 | Architect | 🏗️ |
| 实现/优化 | Coder | 💻 |
| 测试/验证 | Tester | 🧪 |
| 审查/安全 | Reviewer | 👁️ |
| 文档 | Docs | 📖 |
| 构建/部署 | Ops | ⚙️ |
| 报告 | Reporter | 📝 |

## 流程与Gate

```
P1研究 → P2设计 → P3实现 → P4验证 → P5收尾
```

| 复杂度 | 标准 | 流程 |
|--------|------|------|
| 简单 | <50行 | P3 |
| 中等 | 50-500行 | P2→P3→P4 |
| 复杂 | >500行 | 全流程 |

| Gate | 位置 | 要求 | 重试 |
|------|------|------|------|
| G1 | P2→P3 | 设计文档 | 2次 |
| G2 | P4→P5 | 测试通过 | 3次 |

## 性能检查 (必须)

- 回退 >5% → 阻止
- 优化算子丢失 → 阻止
- SIMD被移除 → 阻止

使用 `/benchmark` 运行性能测试，详见 benchmark skill。

## 禁止

硬编码 | 跳过Gate | 超限执行 | 重复读文件

## 常用命令

| 命令 | 说明 |
|------|------|
| `/solar start <任务>` | 启动流程 |
| `/phase next` | 下一阶段 |
| `/benchmark` | 性能测试 |
| `/commit` | Git 提交 |
| `/save` | 保存状态 |
