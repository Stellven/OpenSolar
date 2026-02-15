---
name: benchmark
description: 运行性能基准测试 (业界最佳实践)
user-invocable: true
context: fork
agent: tester
argument-hint: "[--type=micro|operator|query] [benchmark-target]"
---

# 性能基准测试 (Industry Best Practices)

> 基于 Google Benchmark, Criterion.rs, hyperfine 和 Gil Tene 的 "How NOT to Measure Latency"

## 核心原则

### 1. 统计方法

| 指标 | 使用 | 原因 |
|------|------|------|
| **中位数** | ✅ 主要指标 | 对异常值鲁棒 |
| **MAD** | ✅ 变异度 | 比标准差更稳健 |
| **IQR** | ✅ 异常值检测 | Tukey's Fences |
| **Bootstrap CI** | ✅ 置信区间 | 不假设正态分布 |
| 平均值 | ⚠️ 仅参考 | 受异常值影响大 |
| 标准差 | ⚠️ 仅参考 | 需要正态分布 |

### 2. 迭代次数要求

| 基准类型 | 预热 | 测量 | 说明 |
|----------|------|------|------|
| micro (<1ms) | 100+ | 1000+ | JIT/缓存稳定 |
| operator (1-100ms) | 5+ | 30+ | 算子级测试 |
| query (>100ms) | 2+ | 10+ | 查询级测试 |
| e2e | 1+ | 5+ | 端到端测试 |
| latency | 5+ | 100+ | **不剔除异常值** |

### 3. 永远不要忽略最大值

> "The maximum value is not noise, it is the signal." — Gil Tene

最大值揭示:
- GC 暂停
- 缓存未命中
- 上下文切换
- 真实最坏情况

## 执行流程

### Phase 1: 环境准备

```bash
# 1. 收集环境信息
sysctl -n machdep.cpu.brand_string  # CPU 型号
sysctl -n hw.ncpu                    # 核心数
sysctl -n hw.memsize                 # 内存大小

# 2. 检查系统负载
uptime  # 确保负载低

# 3. Git 信息
git rev-parse --short HEAD
git status --porcelain
```

### Phase 2: 运行基准测试

对于每个基准测试:

1. **预热阶段** (不计入统计)
   - 运行 N 次预热迭代
   - 等待 JIT/缓存稳定

2. **测量阶段**
   - 收集原始计时数据
   - 记录每次迭代时间

3. **统计分析**
   - 计算中位数、MAD、IQR
   - 检测异常值 (Tukey's Fences)
   - 生成 Bootstrap 置信区间

### Phase 3: 生成报告

使用 Solar Benchmark Schema:

```typescript
import {
  createBenchmarkResult,
  generateReport,
  exportMarkdown,
  exportJSON,
  exportCSV
} from 'solar/core/benchmark';

// 从原始数据创建结果
const result = createBenchmarkResult(
  'hash_join_1M',
  'HashJoin 1M rows',
  rawTimings,  // number[]
  {
    type: 'operator',
    unit: 'ms',
    description: '1M 行哈希连接',
    params: { rows: 1000000, selectivity: 0.1 }
  }
);

// 生成完整报告
const report = await generateReport(
  'TPC-H Benchmark Report',
  'ThunderDuck',
  [result],
  { baselineBenchmarks: previousResults }  // 可选: 对比基线
);

// 导出多种格式
console.log(exportMarkdown(report));  // 人类可读
writeFileSync('report.json', exportJSON(report));  // 机器可读
writeFileSync('report.csv', exportCSV(report));    // 外部分析
```

## 报告模板

### Markdown 输出格式

```markdown
# [Project] Benchmark Report

**Commit:** abc1234
**Generated:** 2026-01-30T12:00:00Z

## Summary

| Metric | Value |
|--------|-------|
| Status | ✅ PASS |
| Total Benchmarks | 10 |
| Regressions | 0 |
| Improvements | 3 |
| Geometric Mean Speedup | 1.85x |

## Benchmark Results

| Benchmark | Median | σ (MAD) | Min | Max | Samples |
|-----------|--------|---------|-----|-----|---------|
| HashJoin 1M | 12.34 ms | 0.45 ms | 11.2 ms | 15.8 ms | 30 |
| Filter 10M | 2.15 ms | 0.12 ms | 1.9 ms | 3.2 ms | 30 |

## Comparison vs Baseline

| Benchmark | Baseline | Current | Change | Speedup |
|-----------|----------|---------|--------|---------|
| HashJoin 1M | 18.5 ms | 12.3 ms | 🟢 -33.5% | 1.50x |

## Environment

- **CPU:** Apple M4
- **Cores:** 10
- **Memory:** 32 GB
- **OS:** macOS 15.0
```

### JSON Schema (完整)

报告遵循 `BenchmarkReport` schema，包含:

- `metadata`: 硬件/软件/Git/环境信息
- `benchmarks[]`: 各基准测试结果
  - `stats`: 完整统计 (median, mean, MAD, IQR, percentiles)
  - `outliers`: 异常值分析
  - `rawData`: 原始数据 (可选)
- `comparisons[]`: 对比结果 (可选)
- `summary`: 报告摘要

## 回退检测

### 阈值

| 级别 | 阈值 | 动作 |
|------|------|------|
| ⚠️ WARN | >5% | 警告 |
| ❌ FAIL | >10% | 阻止合并 |

### 统计显著性

使用 Welch's t-test 检验:
- p < 0.05 → 显著
- Cohen's d > 0.2 → 有效应量

## 最佳实践检查清单

### 测量前

- [ ] 系统负载低 (load < 1.0)
- [ ] 禁用不必要后台进程
- [ ] 使用 Release 构建
- [ ] 固定 CPU 频率 (如可能)

### 测量中

- [ ] 足够的预热迭代
- [ ] 足够的测量迭代
- [ ] 记录原始数据
- [ ] 不跳过异常值 (延迟测试)

### 报告

- [ ] 使用中位数 (非平均值)
- [ ] 报告 MAD 或 IQR
- [ ] 包含 95% 置信区间
- [ ] 记录环境信息
- [ ] 包含 Git commit SHA
- [ ] 导出 JSON 用于趋势分析

## 趋势分析

将报告存储到 `.solar/benchmarks/` 目录:

```
.solar/benchmarks/
├── 2026-01-30_abc1234.json
├── 2026-01-29_def5678.json
└── baseline.json
```

用于:
- 性能回归检测
- 历史趋势可视化
- 版本间对比

## TPC-H 回归检测 (核心功能)

### 执行流程

```bash
/benchmark tpch           # 运行 TPC-H 并对比 baseline
/benchmark tpch --update  # 运行并更新 baseline (仅当更好时)
```

### 1. 运行 TPC-H

```bash
cd ~/ThunderDuck/build/benchmarks
./tpch_benchmark --sf 1 --iterations 5
```

### 2. 加载 Baseline

从 `~/.claude/data/tpch_baseline.json` 加载历史最佳结果

### 3. 回归检测逻辑

```
对每个查询 Q:
  delta = (current_speedup - baseline_speedup) / baseline_speedup * 100%

  if delta < -10%:
    status = "REGRESSION"    # 🔴 严重回归
  elif delta < -5%:
    status = "WARNING"       # 🟡 轻微回归
  elif delta > 10%:
    status = "IMPROVEMENT"   # 🟢 明显提升
  else:
    status = "STABLE"        # ⚪ 稳定
```

### 4. 输出报告

```
┌─ 📊 TPC-H REGRESSION REPORT ────────────────────────────────┐
│                                                             │
│  SF=1 | 2026-02-02 | Baseline: V58                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Query  Current  Baseline  Delta    Status                  │
│  ─────  ───────  ────────  ─────    ──────                  │
│  Q1     7.09x    8.39x     -15.5%   🔴 REGRESSION           │
│  Q14    3.02x    4.98x     -39.4%   🔴 REGRESSION           │
│  Q21    21.03x   22.73x    -7.5%    🟡 WARNING              │
│  Q3     2.55x    2.50x     +2.0%    ⚪ STABLE               │
│  ...                                                        │
├─────────────────────────────────────────────────────────────┤
│  SUMMARY                                                    │
│  Geometric Mean: 2.89x (baseline: 3.24x, Δ=-10.8%)         │
│                                                             │
│  🔴 Regressions: 5 queries (Q1,Q7,Q10,Q14,Q20)             │
│  🟡 Warnings: 2 queries                                    │
│  ⚪ Stable: 13 queries                                     │
│  🟢 Improved: 2 queries                                    │
├─────────────────────────────────────────────────────────────┤
│  ⚠️ ACTION REQUIRED: Fix regressions before commit         │
└─────────────────────────────────────────────────────────────┘
```

### 5. 回归修复建议

对于每个回归的查询，分析可能原因：
- Applicability check 问题
- 版本选择问题
- 算法变更

### Baseline 管理

```bash
/benchmark baseline --show     # 显示当前 baseline
/benchmark baseline --update   # 更新 (仅当整体更好时)
/benchmark baseline --force    # 强制更新
```

Baseline 文件: `~/.claude/data/tpch_baseline.json`

## 命令示例

```bash
# 运行特定基准测试
/benchmark hash_join

# 运行算子级基准测试
/benchmark --type=operator

# 运行并对比基线
/benchmark --compare=baseline.json

# 运行完整 TPC-H 套件 (核心命令)
/benchmark tpch

# 更新 baseline
/benchmark tpch --update
```

## 参考资料

- [How NOT to Measure Latency - Gil Tene](https://www.infoq.com/presentations/latency-response-time/)
- [Google Benchmark User Guide](https://github.com/google/benchmark)
- [Criterion.rs Documentation](https://bheisler.github.io/criterion.rs/book/)
- [Reducing Variance in Benchmarks](https://google.github.io/benchmark/reducing_variance.html)
