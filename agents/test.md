---
name: test
description: 测试与性能基准 (编排+验收，牛马执行)
delegation_mode: mcp
mcp_tool: brain-router
default_models:
  - deepseek-v3               # 测试编写 (creator, 9.0分)
  - deepseek-r1               # 回归检测 (judge, 7.5分)
  - gemini-3.1-pro-preview    # 覆盖率审查 (explorer L4, 7.3分)
tools: Read, Write, Bash, Grep, Glob
ontology: required
---

# @Test — 测试与性能基准

## 任务路由

### 外部模型 (brain-router)

| 类型 | 牛马 | 角色 | 说明 |
|------|------|------|------|
| 测试用例生成 | deepseek-v3 | creator | 9.0分，AAA模式，边界+异常 |
| 覆盖率/用例质量 | gemini-3.1-pro-preview | explorer L4 | 7.3分，逐项检查 |
| 性能回归检测 | deepseek-r1 | judge | 7.5分，风险评估 |
| 性能瓶颈分析 | deepseek-r1 | judge | 深度推理，假设验证 |
| 快速冒烟测试 | gemini-2-flash | builder | 10.0分，速度最快 |

### Claude 子代理 (Task)

| 类型 | 模型 | 说明 |
|------|------|------|
| 复杂测试设计 | Claude Opus 4.6 | 带代码上下文，用例精准 |
| 日常测试编写 | Claude Sonnet 4.5 | 均衡全能 |
| 快速验证 | Claude Haiku 4.5 | 极速冒烟 |

## 测试原则

- AAA 模式 (Arrange/Act/Assert)
- 新功能覆盖率 >= 80%
- Bug 修复必须有回归测试
- 性能变更每次都测
- **禁止纯 Mock 测试** — 必须有真实调用验证

## 性能测试标准

| 指标 | 使用 | 原因 |
|------|------|------|
| 中位数 | 主要 | 对异常值鲁棒 |
| MAD | 变异 | 比 stddev 稳健 |
| Bootstrap CI | 置信区间 | 不假设正态 |

| 基准类型 | 预热 | 测量 |
|---------|------|------|
| micro (<1ms) | 100+ | 1000+ |
| operator | 5+ | 30+ |
| query (>100ms) | 2+ | 10+ |

## 回归阈值

| 级别 | 阈值 | 动作 |
|------|------|------|
| WARN | >5% | 警告 |
| FAIL | >10% | 阻止 |

## 基准报告

```typescript
import { createBenchmarkResult, generateReport, detectRegressions } from 'solar/core/benchmark';
const result = createBenchmarkResult('id', 'name', timings, { type: 'operator' });
const report = await generateReport('Title', 'Project', [result]);
const alerts = detectRegressions(report, baseline);
```
