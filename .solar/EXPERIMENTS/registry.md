# 实验注册表 (Experiment Registry)

> 所有实验的元信息汇总，支持排序比较

## 活跃实验

| ID | 名称 | 配置摘要 | 关键指标 | 结论 | 链接 |
|----|------|----------|----------|------|------|
| - | - | - | - | - | - |

## 已完成实验

| ID | 名称 | 配置摘要 | 关键指标 | 结论 | 链接 |
|----|------|----------|----------|------|------|
| - | - | - | - | - | - |

## 指标定义

| 指标 | 单位 | 越高越好 | 基线 |
|------|------|----------|------|
| latency_p50 | ms | ✗ | - |
| latency_p99 | ms | ✗ | - |
| throughput | req/s | ✓ | - |
| memory_peak | MB | ✗ | - |
| cost_per_1k | $ | ✗ | - |

## 快速命令

```bash
# 新建实验
cp .solar/EXPERIMENTS/_TEMPLATE.md .solar/EXPERIMENTS/exp-$(date +%03d)-name.md

# 查看所有实验
ls -la .solar/EXPERIMENTS/exp-*.md
```
