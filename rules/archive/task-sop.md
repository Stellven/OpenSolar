# Solar 铁律: 任务专用 SOP (Task-Specific SOPs)

> **来源: 2026-02-12 监护人指导**
> **目标: 把"感觉"变成"证据链"，让工作可复现、可回滚、可追溯**

## 五类任务 SOP

### ① 性能优化 / Profiling (硬指标闭环)

**目标**: 把"感觉"变成"证据链"，把"优化"变成"可回归的工程资产"。

**每轮必须交付 4 件事**:
1. **Bottleneck Table** (Top hotspots / allocations / syscalls)
2. **Hypothesis** (为什么慢)
3. **Fix Plan** (最小改动路径，优先 ROI 最大)
4. **Validation** (指标阈值 + 回归 guard)

**关键规则**:
```
任何性能结论必须带:
• commit hash
• 完整命令
• 环境信息
• warmup 次数
• 测量迭代次数
```

**流程**: 测量 → 归因 → 方案 → 验证 → 回归保护

**实验记录**: `.solar/EXPERIMENTS/exp-XXX-name.md`

---

### ② 大规模重构 / 架构改造 (避免"改完更烂")

**目标**: 让重构"可控、可回滚、可分阶段上线"。

**RFC 驱动**: `.solar/RFC/XXXX-name.md`

**黄金节奏 (4 Phase)**:
| Phase | 名称 | 做什么 | 不做什么 |
|-------|------|--------|----------|
| 0 | 兼容层+观测 | 加日志/指标/抽象 | 不改行为 |
| 1 | 双写/旁路 | 新旧并存，能一键切回 | 不删旧代码 |
| 2 | 切流量 | 逐步替换 | 不急于求成 |
| 3 | 删旧实现 | 移除旧代码 | 不留死代码 |

**每轮输出要求**:
- 这轮属于哪个 phase
- 做了什么兼容/开关
- 如何一键回滚
- 哪些指标证明安全

---

### ③ 多文件 Feature 开发 (防止上下文炸裂)

**目标**: 多文件修改也能保持"结构一致性 + 可测试闭环"。

**ARCH.md 先读**: `.solar/ARCH.md`
- 模块边界
- 数据流
- 错误处理约定
- 日志规范

**Feature 套路**:
1. 先在 STATE.md 写 **接口契约** (输入/输出/错误/性能预算)
2. 按模块逐个落地
3. 每落地一块就 checkpoint

**禁止**:
- ❌ 一次性改多个模块
- ❌ 没有接口契约就动手
- ❌ 破坏现有模块边界

---

### ④ 调参 / 实验 / Benchmark (偏研究)

**目标**: 实验可复现、可对比、可汇总。

**实验系统**:
- `.solar/EXPERIMENTS/registry.md` - 元信息汇总
- `.solar/EXPERIMENTS/exp-XXX-name.md` - 具体实验

**registry.md 必须记录**:
| 字段 | 说明 |
|------|------|
| exp id | 实验编号 |
| config | 关键配置 |
| metrics | 核心指标 |
| verdict | 结论 (ship/rollback/iterate) |
| link | 详情链接 |

**关键**: 实验结果必须能排序比较

---

### ⑤ Bug 修复 / 紧急热修

**目标**: 快速定位、最小改动、回归保护。

**流程**:
1. **Reproduce** - 复现命令
2. **Root Cause** - 根因分析
3. **Fix** - 最小改动
4. **Regression Test** - 加测试保护
5. **Verify** - 确认修复

**每轮输出**:
- 复现命令
- 根因假设
- 修复 diff
- 回归测试

---

## 目录结构

```
.solar/
├── STATE.md           # 当前任务态势
├── DECISIONS.md       # 决策账本
├── ARCH.md            # 架构文档 (多文件开发必读)
├── EXPERIMENTS/       # 实验记录
│   ├── registry.md    # 实验注册表
│   ├── _TEMPLATE.md   # 实验模板
│   └── exp-XXX-*.md   # 具体实验
├── RFC/               # 架构提案
│   ├── _TEMPLATE.md   # RFC 模板
│   └── XXXX-*.md      # 具体 RFC
└── LOG/               # 日志
    ├── cmd.md
    ├── bench.md
    └── errors.md
```

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   📋 任务专用 SOP 铁律                                          │
│                                                                 │
│   1. 性能优化: 4 件事 (Bottleneck/Hypothesis/Fix/Validation)    │
│   2. 架构重构: 4 Phase (兼容层→双写→切流量→删旧)                │
│   3. 多文件开发: 先读 ARCH.md，按模块逐个落地                   │
│   4. 实验 Benchmark: registry.md 汇总，可排序比较               │
│   5. Bug 修复: Reproduce→RootCause→Fix→Test→Verify              │
│                                                                 │
│   一切可复现、可回滚、可追溯                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Task-Specific SOPs v1.0*
*建立于: 2026-02-12*
*监护人指导: 把"感觉"变成"证据链"*
