---
name: solar
description: 启动 Solar 开发模式 - 五阶段流程控制
user-invocable: true
argument-hint: "[start <任务>|status|stop]"
---

# /solar - 流程控制

## 命令

| 命令 | 说明 |
|------|------|
| `/solar start <任务>` | 启动 Solar，初始化流程 |
| `/solar status` | 显示当前状态 |
| `/solar stop` | 停止 Solar |

## /solar start <任务>

### 1. 判断复杂度

| 复杂度 | 标准 | 流程 |
|--------|------|------|
| 简单 | <50行 | P3 |
| 中等 | 50-500行 | P2→P3→P4 |
| 复杂 | >500行 | P1→P2→P3→P4→P5 |

### 2. 创建状态 `.solar/flow-state.json`

```json
{"active":true,"task":"<描述>","complexity":"<级别>","phase":"<P1-P5>","agent":"<Agent>"}
```

### 3. 输出横幅 + Agent 宣告

```
┌─ ☀️ Solar ────────────────────────────┐
│ 任务: <任务> | 复杂度: <级别>         │
│ 阶段: <P1-P5> | Agent: <emoji Agent>  │
└───────────────────────────────────────┘

┌─ <emoji> <Agent> ─────────────────────┐
│ Task: <目标>                          │
│ Plan: 1. <步骤1>  2. <步骤2>         │
└───────────────────────────────────────┘
```

## 阶段-Agent 映射

| 阶段 | Agent | Emoji | 职责 |
|------|-------|-------|------|
| P1 | Researcher | 🔬 | 调研 |
| P2 | Architect | 🏗️ | 设计 |
| P3 | Coder | 💻 | 实现 |
| P4 | Tester | 🧪 | 测试 |
| P5 | Ops | ⚙️ | 收尾 |

## Gate

| Gate | 位置 | 要求 | 重试 |
|------|------|------|------|
| G1 | P2→P3 | 设计文档 | 2次 |
| G2 | P4→P5 | 测试通过 | 3次 |

## 阶段转换

使用 `/phase` 命令，见 phase skill。
