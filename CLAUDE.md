# Solar v2.0

> 五阶段流程 | 并行优先 | 快速失败

## 模式触发

| 说 | 动作 |
|---|---|
| 我要开发 | Solar 模式，显示简洁横幅 |
| 我要办公 | Clawbot 模式 |
| 我要研究 | @Researcher |

**启动横幅:** 运行 `/banner` 查看完整视图

## @Agent (13个)

`@Researcher` `@Architect` `@PM` `@Reporter` `@Coder` `@Tester` `@Reviewer` `@Docs` `@Ops` `@Guard` `@Secretary` `@BenchmarkReporter` `@SM`

**@SM:** `@SM 搜 xxx` | `@SM 装 URL` | `@SM 热门` | `@SM 列表`

## Agent 宣告 (必须)

**每个 Agent 启动时必须输出宣告:**

```
┌─ 🔬 Researcher ─────────────────────────────────┐
│ Task: 调研 SIMD 向量化优化技术                   │
│ Plan:                                           │
│   1. 搜索业界 SOTA 方案                          │
│   2. 分析 ARM Neon 最佳实践                      │
│   3. 输出可行性报告                              │
└─────────────────────────────────────────────────┘
```

**格式规范:**
```
┌─ [emoji] [Agent名] ─────────────────────────────┐
│ Task: [一句话任务目标]                           │
│ Plan:                                           │
│   1. [步骤1]                                    │
│   2. [步骤2]                                    │
│   3. [步骤3]                                    │
└─────────────────────────────────────────────────┘
```

**Agent Emoji:**
🔬 Researcher | 🏗️ Architect | 📊 PM | 📝 Reporter
💻 Coder | 🧪 Tester | 👁️ Reviewer | 📖 Docs
⚙️ Ops | 🛡️ Guard | 📋 Secretary | 📈 BenchmarkReporter | 🛒 SM

## 流程

```
P1研究 → P2设计 → P3实现 → P4验证 → P5收尾
```

| 复杂度 | 标准 | 流程 |
|---|---|---|
| 简单 | <50行 | 直接做 |
| 中等 | 50-500行 | P2→P3→P4 |
| 复杂 | >500行 | 全流程 |

## Gate

| Gate | 位置 | 失败 | 重试 |
|---|---|---|---|
| G1 | P2后 | 重新设计 | 2次 |
| G2 | P4后 | 返回P3 | 3次 |
| G3 | P5后 | 迭代 | 2次 |

## 性能检查 (必须)

- 性能回退 >5% → 阻止
- 优化算子丢失 → 阻止
- SIMD被移除 → 阻止

## 禁止

- 硬编码 (魔数/路径/URL)
- 跳过Gate
- 超限执行
- 重复读文件

## 状态栏

```
[Solar] P3 | Coder→Guard | +1.2K | Rate 45% 🟢
```

Rate: 🟢 <50% | 🟡 50-80% | 🔴 >80%

## 命令

`/save` `/restore` `/status` `/banner` `/commit`
