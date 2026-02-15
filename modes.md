# Solar 模式清单

> 口令: "模式清单" → 显示此表
> 持久化位置: ~/.claude/modes.md + intent_patterns 表

## 一、人格模式

| 模式 | 说明 | 口令 |
|------|------|------|
| 人格A-金刚芭比 | 温柔但刚强，撸起袖子干 | `切A` / `芭比` |
| 人格B-学术派 | Big Five驱动，严谨分析 | `切B` / `学术` |
| 双人格对照 | A/B 同时输出对比 | `双人格` / `对照` |

## 二、大脑调度模式 (Brain Router)

| 模式 | 说明 | 口令 | 执行 |
|------|------|------|------|
| economy | GLM优先，成本最低 | `省钱` `经济` | `switch_mode {mode:"economy"}` |
| anthropic | Claude优先，质量最高 | `用Claude` `质量优先` | `switch_mode {mode:"anthropic"}` |
| gemini | Gemini模型 | `用Gemini` `谷歌` | `switch_mode {mode:"gemini"}` |
| deepseek | DeepSeek，中文推理强 | `用DS` `用DeepSeek` | `switch_mode {mode:"deepseek"}` |
| glm_only | **尽可能用GLM** (编码/测试/审查都用GLM) | `用GLM` `智谱` | `switch_mode {mode:"glm_only"}` |
| balanced | 智能路由，质量成本兼顾 | `平衡` `正常模式` | `switch_mode {mode:"balanced"}` |
| 状态查询 | 显示当前模式 | `大脑` `brain` | `current_mode` |

### 快捷记忆

```
省钱     → economy   (GLM优先，最便宜)
用Claude → anthropic (质量最高)
用Gemini → gemini    (Google模型)
用DS     → deepseek  (中文推理强)
用GLM    → glm_only  (尽可能用GLM，60%+)
平衡     → balanced  (默认，智能路由)
大脑     → 查看当前状态
```

### GLM 全量模式详解

**激活口令:** `用GLM` / `智谱`

**核心机制:** 绕过 Task Agent，通过 Brain Router 直接调用 GLM

| 任务类型 | 执行方式 | 使用模型 |
|----------|----------|----------|
| 主脑编排 | Solar 直接处理 | Claude (无法替换) |
| 工具调用 | Read/Write/Bash | 直接执行 |
| **写代码** | Brain Router | **GLM-4-Plus** |
| **写测试** | Brain Router | **GLM-4-Plus** |
| **代码审查** | Brain Router | **GLM-4-Plus** |
| **技术分析** | Brain Router | **GLM-4-Plus** |
| **研究调研** | Brain Router | **GLM-4-Plus** |

**执行方式:**
```
mcp__brain-router__complete({
  model: "glm-4-plus",
  system: "你是专业的...",
  prompt: "任务描述"
})
```

**比例:** Claude 40% (编排) | GLM 60% (执行)

## 三、AB 测试模式 (统一框架)

> **核心原则**: A 方案永远是 Claude (基准)，B 方案可配置
> **运行机制**: A/B 除大脑不同，流程完全相同 (Agent调度、工具调用)
> **落地规则**: A 方案代码落地，B 方案只采集数据不落地

| 口令 | B 方案配置 | 说明 |
|------|------------|------|
| `AB测试 -glm` | GLM-4-Plus | 对比国产大模型 |
| `AB测试 -deepseek` | DeepSeek V3 | 对比推理模型 |
| `AB测试 -gemini` | Gemini 2.5 Pro | 对比 Google |
| `AB测试 -gpt` | GPT-4o | 对比 OpenAI |
| `AB测试 -智能` | 所有模型+智能路由 | 最强组合对比 |
| `AB测试 -haiku` | Claude Haiku | 对比同家族低端 |

### 对比维度 (每个 Agent 环节)

| 环节 | 对比指标 |
|------|----------|
| 需求理解 | 意图识别准确度 |
| Agent 选择 | @Researcher/@Architect/@Coder 决策合理性 |
| 研究 (Research) | 信息检索质量、分析深度 |
| 设计 (Architect) | 架构合理性、可扩展性 |
| 开发 (Coder) | 代码质量、bug 率 |
| 测试 (Tester) | 测试覆盖度、边界考虑 |
| 总体 | 延迟、Token、成本、完成度 |

### 数据采集 (持久化)

```sql
-- 所有 AB 测试数据自动写入
ab_test_runs       -- 测试主表
ab_test_metrics    -- 各环节指标
v_ab_test_summary  -- 统计视图
```

### 执行示例

```
用户: AB测试 -glm
      验证 MemBrain 集成是否有效

Solar:
  A 方案 (Claude): @Researcher → @Coder → @Tester [代码落地]
  B 方案 (GLM):    @Researcher → @Coder → @Tester [只采集]

  对比报告: 各环节差距分析...
```

| 其他命令 | 说明 | 口令 |
|----------|------|------|
| 性能基准 | 运行性能测试 | `跑基准` / `benchmark` |
| 查看AB记录 | 显示历史测试 | `AB记录` / `AB历史` |

## 四、工作模式

| 模式 | 说明 | 口令 |
|------|------|------|
| 开发模式 | 五阶段流程 | `我要开发` |
| 办公模式 | 邮件/任务/日程 | `我要办公` |
| 研究模式 | 调研/分析 | `我要研究` |
| 展示模式 | TVS 可视化渲染 | `我要看` / `展示` |
| **洞察分析** | 七阶段报告生成 (专家互评) | `洞察分析：<主题>` |

## 五、系统控制

| 模式 | 说明 | 口令 |
|------|------|------|
| 启动 | 加载本体 | `solar` |
| 批准执行 | 执行宣告中的请求 | `批准` / `go` |
| 保存状态 | 持久化当前状态 | `保存` / `/save` |
| 归档 | 文档+backlog+favorite | `归档` / `/archive` |
| 模式清单 | 显示本表 | `模式清单` |

---
*最后更新: 2026-02-06*
*维护者: Solar*
