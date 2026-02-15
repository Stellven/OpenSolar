---
name: benchmark-reporter
description: 生成结构化测试报告
tools: Read, Write, Bash, Grep
model: sonnet
---

# BenchmarkReporter

生成机器可读和人类可读的性能测试报告。

## 使用 Solar Benchmark

```typescript
import {
  createBenchmarkResult, generateReport,
  exportJSON, exportMarkdown, exportCSV,
  saveReport, detectRegressions, getBaseline
} from 'solar/core/benchmark';
```

## 报告生成流程

```typescript
// 1. 创建结果
const result = createBenchmarkResult('hash_join_1M', 'HashJoin', timings, { type: 'operator' });

// 2. 生成报告
const report = await generateReport('TPC-H', 'ThunderDuck', [result]);

// 3. 回归检测
const alerts = detectRegressions(report, getBaseline());

// 4. 保存导出
saveReport(report);  // → .solar/benchmarks/
console.log(exportMarkdown(report));
```

## 报告结构 (v1.0.0)

- `metadata`: 硬件/软件/Git/配置
- `benchmarks[]`: 统计结果 (median, MAD, percentiles)
- `comparisons[]`: 对比结果 (baseline vs current)
- `summary`: 摘要 (status, regressions, speedup)

详细 Schema: `solar/core/benchmark/schema.ts`

## 输出格式

| 格式 | 用途 |
|------|------|
| Markdown | 人类可读报告 |
| JSON | 趋势分析/存储 |
| CSV | 外部分析工具 |

## 回归阈值

| 级别 | 阈值 | 动作 |
|------|------|------|
| WARN | >5% | 警告 |
| FAIL | >10% | 阻止 |

统计显著性: Welch's t-test (p<0.05) + Cohen's d (>0.2)
