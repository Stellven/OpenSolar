# /self-eval - Solar 自我评估

## 触发
- `/self-eval` - 立即运行评估
- `/self-eval daily` - 运行日评估
- `/self-eval weekly` - 运行周评估
- `/self-eval report` - 查看最近报告

## 执行

### 运行评估

```bash
cd ~/.claude/core/ses && bun evaluate.ts on_demand console
```

### 查看最近报告

```bash
ls -lt ~/.solar/reports/ses_*.md | head -5
```

### 查看评估历史

```sql
SELECT run_id, run_type, overall_score, completed_at
FROM ses_evaluation_runs
WHERE status = 'completed'
ORDER BY completed_at DESC
LIMIT 10;
```

### 查看技能熟练度

```sql
SELECT * FROM v_skill_proficiency_overview;
```

### 查看改进建议

```sql
SELECT priority, dimension, title, description
FROM v_active_recommendations
ORDER BY priority;
```

## 输出格式

TVS 风格的评估报告，包括：
- 综合得分 (0-100)
- 七维度得分 (SKILL/TASK/LEARN/ERROR/RULE/RESOURCE/MEMORY)
- 技能熟练度 (Dreyfus 模型)
- 关键发现 (亮点 + 关注点)
- 改进建议 (P1/P2/P3)
- **闭环验证** (v1.1):
  - 数据健康检查 - 各数据源状态
  - 置信度评估 - 每个维度的评分可靠性
  - 建议追踪 - 之前建议的执行效果
  - 元评估 - 评估系统自身的有效性

## 评估维度说明

| 维度 | 权重 | 数据来源 |
|------|------|----------|
| SKILL (技能) | 20% | evo_tool_calls, ses_skill_proficiency |
| TASK (任务) | 25% | ses_task_records, evo_sessions |
| LEARN (学习) | 15% | evo_learning_signals, evo_memory_semantic |
| ERROR (错误) | 15% | evo_tool_calls (status=error) |
| RULE (规则) | 10% | ses_rule_compliance |
| RESOURCE (资源) | 10% | evo_llm_calls, sys_token_usage |
| MEMORY (记忆) | 5% | evo_memory_*, evo_memory_influences |

## Dreyfus 技能熟练度模型

| 等级 | 名称 | 标准 |
|------|------|------|
| 1 | Novice | usage < 10 OR success_rate < 60% |
| 2 | Advanced Beginner | usage >= 10 AND success_rate >= 60% |
| 3 | Competent | usage >= 50 AND success_rate >= 80% |
| 4 | Proficient | usage >= 100 AND success_rate >= 90% |
| 5 | Expert | usage >= 200 AND success_rate >= 95% |

## 定时评估

| 类型 | 频率 | 时间 |
|------|------|------|
| Daily | 每天 | 04:00 |
| Weekly | 每周日 | 03:00 |
| Monthly | 每月1日 | 02:00 |

报告保存位置: `~/.solar/reports/`

## 闭环设计原则

基于监护人教的智慧法则：

| 法则 | 实现 |
|------|------|
| 知行合一 | 建议追踪 - 生成建议后追踪执行效果 |
| 实事求是 | 数据健康检查 - 数据不足时承认，不强行评分 |
| 实践检验 | 置信度评估 - 用数据点和方差验证评估可靠性 |
| 否定之否定 | 元评估 - 评估"评估系统"本身的有效性 |

```
评估 → 建议 → 执行 → 验证 → 反馈 → 评估
       ↑                         │
       └─────── 闭环 ─────────────┘
```
