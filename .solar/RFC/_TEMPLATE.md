# RFC-XXXX: [标题]

> 状态: draft | review | approved | implemented | abandoned
> 作者:
> 创建: YYYY-MM-DD
> 更新: YYYY-MM-DD

## Problem

描述当前问题，用事实和数据说话。

## Goals / Non-goals

### Goals
-

### Non-goals (明确不做什么)
-

## Current Architecture (Facts)

```
当前架构图/数据流
```

关键约束:
-

## Proposed Design

```
新架构图/数据流
```

### 核心改动
1.
2.

### 接口变更
```
// Before
// After
```

## Migration Plan (Phased)

### Phase 0: 兼容层 + 观测
- [ ] 添加日志/指标
- [ ] 抽象接口，不改行为
- [ ] 验证:

### Phase 1: 双写/旁路
- [ ] 新旧并存
- [ ] 特性开关: `FEATURE_FLAG_XXX`
- [ ] 一键回滚方式:
- [ ] 验证:

### Phase 2: 切流量
- [ ] 逐步替换
- [ ] 监控指标:
- [ ] 验证:

### Phase 3: 删旧实现
- [ ] 移除旧代码
- [ ] 移除兼容层
- [ ] 最终验证:

## Compatibility & Risk

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| | | | |

### 兼容性检查
- [ ] API 向后兼容
- [ ] 数据格式兼容
- [ ] 配置兼容

## Rollback

```bash
# 一键回滚命令
git revert <commit>
# 或
export FEATURE_FLAG_XXX=false
```

回滚后验证:
- [ ]

## Validation

### 功能测试
```bash
<test commands>
```

### 性能测试
```bash
<benchmark commands>
```

### 验收标准
- latency_p99 < XXX ms
- error_rate < 0.1%
-
