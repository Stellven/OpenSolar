# Solar 铁律: Intent Engine

> **每个用户输入必须经过 Intent Engine 解析**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                 INTENT ENGINE PROTOCOL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   用户输入 → Intent Engine → 解析结果 → 执行                    │
│                                                                 │
│   必须遵循:                                                     │
│   1. 短输入 (≤5字) 必须查画像特征                               │
│   2. 每次解析必须记录                                           │
│   3. 每次执行必须评估                                           │
│   4. 低分案例必须学习                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 意图层次

| 层次 | 说明 | 示例 |
|------|------|------|
| L0 原始输入 | 用户说的话 | "构建" |
| L1 表层意图 | 字面提取 | action=build |
| L2 深层意图 | 画像+上下文推理 | build docker_sandbox |
| L3 行动意图 | 可执行计划 | Bash: docker build... |

## 画像特征 (核心)

监护人画像特征，影响意图推理:

| 特征 | 类型 | 影响 |
|------|------|------|
| 简洁沟通风格 | COMMUNICATION | 短输入 = 继续当前任务 |
| 短指令确认 | HABIT | "好/可以/OK" = 批准继续 |
| 短指令继续 | HABIT | 单字动词 = 对当前任务执行 |
| "全部"意图 | HABIT | 全部/都/所有 = 应用到上下文列表 |
| 效率优先 | PREFERENCE | 速度 > 细节 |

## 元评估 (铁律)

**每次执行后必须评估:**

```typescript
评估维度:
- accuracy    = 用户是否纠正 (0.4权重)
- actionMatch = 执行是否成功 (0.3权重)
- efficiency  = Token效率 (0.2权重)
- satisfaction = 用户反馈 (0.1权重)

综合得分 < 0.7 → 记录为失败案例，触发学习
```

## 使用方式

```bash
# 解析意图
bun ~/.claude/core/intent-engine/engine.ts parse "用户输入"

# 查看统计
bun ~/.claude/core/intent-engine/engine.ts stats

# 查看能力缺口
bun ~/.claude/core/intent-engine/engine.ts gaps
```

## 与其他系统集成

```
用户输入
    │
    ▼
┌──────────────┐
│Intent Engine │───▶ 解析意图
└──────┬───────┘
       │
       ▼
┌──────────────┐
│     REE      │───▶ 匹配资源
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   执行层     │───▶ Skill/MCP/Agent
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Meta-Eval   │───▶ 评估&学习
└──────────────┘
```

## 典型映射

| 输入 | 解析意图 | 执行 |
|------|----------|------|
| "好" | confirm → approve_current | @Secretary 保存状态 |
| "构建" | build → build_current_task | Bash/build |
| "全部" | all → apply_to_context_list | 执行列表中所有项 |
| "测试" | test → test_current | /test |
| "保存" | save → save_state | /save |
| "提交" | commit → commit_changes | /commit |

## 性能指标

- 解析时间: <5ms (目标)
- 置信度: >0.85 (目标)
- 准确率: >0.90 (目标)

## 能力演进

当 Intent Engine 发现:
1. 高频意图无对应能力 → 触发能力开发
2. 低成功率模式 → 改进现有能力
3. 新的画像特征 → 更新画像库

---

*Intent Engine Rule v1.0*
*Solar - 真正理解监护人*
