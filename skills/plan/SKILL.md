# /plan - Plan-and-Act 执行器

## 功能

使用 Plan-and-Act 框架执行复杂任务，自动生成计划、分配 Agent、跟踪进度。

## 使用方式

```
/plan <任务描述>           # 自动规划并执行
/plan preview <任务>       # 只生成计划预览，不执行
/plan resume <session_id>  # 恢复中断的计划
/plan status               # 查看当前计划状态
/plan metrics              # 查看执行统计
```

## 触发条件

以下任务类型会自动触发 Plan-and-Act：

- "实现 xxx 功能" / "开发 xxx 系统"
- "设计 xxx 架构" / "重构 xxx 模块"
- "优化 xxx 性能" / "集成 xxx 服务"
- 多步骤任务（包含 3+ 子任务）
- 任务描述超过 50 字

## 执行流程

```
1. 生成计划 → 2. 预览确认 → 3. 分步执行 → 4. 进度跟踪 → 5. 失败重规划
```

## 约束注入

Plan-and-Act 会自动从 STATE.md 读取约束条件，注入到每个 Agent 调用中：

```markdown
# Constraints
- 不破坏现有 API 接口
- 性能不能回退超过 5%
- 不引入新的外部依赖
```

## 示例

### 示例 1：实现新功能

```
用户: /plan 实现用户认证系统，支持 JWT 和 OAuth2

执行计划预览：
─────────────────────────────────────
目标: 实现用户认证系统，支持 JWT 和 OAuth2
步骤数: 4

步骤:
  1. [Researcher] 分析认证需求和技术选型
  2. [Architect] 设计认证架构和接口
  3. [Coder] 实现 JWT 认证模块
  4. [Coder] 实现 OAuth2 集成
  5. [Tester] 编写认证测试用例

约束:
  - 不引入新依赖（使用现有库）
  - 保持向后兼容

是否执行？(y/n)
```

### 示例 2：查看进度

```
用户: /plan status

当前计划: plan-1709030400000
进度: 3/5 (60%)
状态: 执行中
下一步: [Coder] 实现 OAuth2 集成
```

### 示例 3：查看统计

```
用户: /plan metrics

╔═══════════════════════════════════════════════════════════════╗
║              Plan-and-Act 执行统计 (最近 7 天)                ║
╠═══════════════════════════════════════════════════════════════╣
║  总计划数: 23                                                 ║
║  成功率: 87.3%                                                ║
║  平均耗时: 12.4s                                              ║
║  MemRL 训练数据: [████████░░] 80%                            ║
╚═══════════════════════════════════════════════════════════════╝
```

## 实现细节

调用 `~/.claude/core/plan-act/plan-act-adapter.ts`:

```typescript
import { executeWithPlanAct, quickPlan, isComplexTask } from './plan-act-adapter';

// 判断是否需要 Plan-and-Act
if (isComplexTask(userRequest)) {
  // 快速预览
  const preview = await quickPlan(userRequest, constraints);
  console.log(formatPlanPreview(preview.plan));

  // 确认后执行
  const result = await executeWithPlanAct({
    goal: userRequest,
    constraints: readConstraintsFromState(),
    onProgress: (p) => console.log(p)
  });
}
```

## 与现有 Agent 的关系

| 场景 | 使用方式 |
|------|----------|
| 简单任务 | 直接调用 @Agent |
| 复杂多步骤任务 | 自动切换到 /plan |
| 需要约束检查 | /plan 注入约束 |
| 失败需要重试 | /plan 自动重规划 |

## 注意事项

- 执行前会显示计划预览，需要用户确认
- 失败时会自动触发重规划（最多 2 次）
- 执行日志会自动收集用于 MemRL 训练
- 可以随时中断并稍后恢复
