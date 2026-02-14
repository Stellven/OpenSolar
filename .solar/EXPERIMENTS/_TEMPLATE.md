# exp-XXX: [实验标题]

> 创建时间: YYYY-MM-DD
> 状态: draft | running | done | abandoned

## Setup (Reproduction)

```bash
# 环境
uname -a
# commit
git rev-parse HEAD
# 命令
<exact command>
# warmup
<warmup iterations>
# iterations
<measurement iterations>
```

## Baseline

| 指标 | 值 | 备注 |
|------|-----|------|
| latency_p50 | | |
| latency_p99 | | |
| throughput | | |
| memory | | |

## Change (Diff Summary)

```
变更摘要:
-
-
```

## Hypothesis

为什么认为这个改动会有效？

## Result

| 指标 | Baseline | After | Delta |
|------|----------|-------|-------|
| latency_p50 | | | |
| latency_p99 | | | |
| throughput | | | |
| memory | | | |

## Bottleneck Table

### Top Hotspots (CPU)
| 函数 | 占比 | 调用次数 |
|------|------|----------|
| | | |

### Top Allocations (Memory)
| 来源 | 大小 | 频率 |
|------|------|------|
| | | |

### Top Syscalls (I/O)
| syscall | 次数 | 耗时 |
|---------|------|------|
| | | |

## Analysis

为什么结果是这样？

## Decision

- [ ] Ship - 合入主线
- [ ] Rollback - 回滚
- [ ] Iterate - 继续迭代 (下一个实验: exp-XXX)

## Validation

```bash
# 回归保护命令
<regression test command>

# 阈值
latency_p99 < XXX ms
throughput > XXX req/s
```
