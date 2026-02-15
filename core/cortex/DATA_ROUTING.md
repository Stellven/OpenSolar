# Solar 数据路由指南 (Data Routing Guide)

> **中枢神经系统的数据地图**
> **每次启动/恢复时必须参考此文件**

## 快速查看命令

```bash
# 查看数据账本摘要
bun ~/.claude/core/cortex/ledger.ts

# 查看问题列表
bun ~/.claude/core/cortex/ledger.ts issues

# 刷新账本数据
bun ~/.claude/core/cortex/ledger.ts refresh
```

## 数据路由地图

```
┌─────────────────────────────────────────────────────────────────┐
│                    SOLAR 数据路由地图                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   本体层    │     │   记忆层    │     │   资源层    │       │
│  │  (我是谁)   │     │ (我记得什么) │     │ (我能做什么) │       │
│  ├─────────────┤     ├─────────────┤     ├─────────────┤       │
│  │ ont_*       │     │ evo_memory_*│     │ sys_*       │       │
│  │ sys_person* │     │ sys_favorites│    │ (resources) │       │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│         │                   │                   │               │
│         └───────────────────┼───────────────────┘               │
│                             │                                   │
│                             ▼                                   │
│                    ┌─────────────────┐                          │
│                    │     CORTEX      │ ← 中枢神经               │
│                    │   (协调中心)    │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│         ┌───────────────────┼───────────────────┐               │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   路由层    │     │   轨迹层    │     │   反馈层    │       │
│  │  (怎么选择) │     │ (做过什么)  │     │ (学到什么)  │       │
│  ├─────────────┤     ├─────────────┤     ├─────────────┤       │
│  │ sroe_*      │     │ tel_*       │     │ evo_feedback│       │
│  │ cortex_*    │     │ evo_traces  │     │ sys_training│       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 详细路由表

### 1. 本体层 (WHO AM I) - 启动时读取

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `ont_value_dimensions` | 价值观 | 读 | 7 |
| `ont_style_dimensions` | 风格 | 读 | 6 |
| `ont_preference_dimensions` | 偏好 | 读/写 | 18 |
| `sys_personality_big_five` | 人格参数 | 读/写 | 10 |

**读取场景:** /ontology load, BIOS 启动
**写入场景:** 人格学习, 偏好更新

### 2. 记忆层 (WHAT I REMEMBER) - 随时读写

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `evo_memory_semantic` | 语义记忆 (知识) | 读/写 | 74 |
| `evo_memory_procedural` | 程序记忆 (技能熟练度) | 读/写 | 19 |
| `evo_memory_episodic` | 情景记忆 (经历) | 读/写 | 11 |
| `sys_favorites` | 收藏 (高价值内容) | 读/写 | 38 |

**读取场景:** 需要历史经验时
**写入场景:** 学到新知识, 有价值输出, 完成任务后

### 3. 资源层 (WHAT I CAN DO) - 主要读取

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `sys_resources` | 资源总表 | 读 | 192 |
| `sys_skills` | 技能列表 | 读 | 37 |
| `sys_shortcuts` | 快捷指令 | 读 | 14 |
| `sys_agents` | Agent列表 | 读 | 13 |
| `sys_scripts` | 脚本缓存 | 读/写 | 6 |

**读取场景:** 匹配资源, REE 路由
**写入场景:** 注册新资源, 能力演进

### 4. 路由层 (HOW TO CHOOSE) - 读写频繁

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `sroe_requests` | 路由请求记录 | 写 | 331 |
| `sroe_model_beliefs` | 模型信念 | 读/写 | 18 |
| `cortex_requests` | Cortex 请求 | 写 | 9 |
| `sroe_evaluations` | 路由评估 | 写 | 3 |

**读取场景:** 选择模型, 查历史决策
**写入场景:** 每次路由决策, 反馈评估

### 5. 轨迹层 (WHAT I DID) - 主要写入

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `tel_operations` | 操作遥测 | 写 | 30716 |
| `evo_traces` | 会话轨迹 | 写 | 0 ⚠️ |
| `evo_spans` | 执行跨度 | 写 | 0 ⚠️ |
| `evo_tool_calls` | 工具调用 | 写 | 1 ⚠️ |

**读取场景:** 分析历史行为
**写入场景:** 每次工具调用, 每个会话
**问题:** evo_traces/spans/tool_calls 需要从 JSONL 导入

### 6. 反馈层 (WHAT I LEARNED) - 读写

| 表名 | 用途 | 读/写 | 记录数 |
|------|------|-------|--------|
| `evo_feedback_v2` | 反馈信号 | 读/写 | 568 |
| `sys_training_samples` | 训练样本 | 写 | 97 |

**读取场景:** 学习历史, 避免重复错误
**写入场景:** 收到用户反馈, 提取样本

## 启动恢复流程

```
Solar 启动
    │
    ▼
┌─────────────────┐
│ 1. 查数据账本   │ ← bun ledger.ts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. 加载本体     │ ← ont_*, sys_personality
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. 加载记忆     │ ← evo_memory_*, sys_favorites
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. 检查资源     │ ← sys_resources
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. 检查待办     │ ← sys_guardian_memos
└────────┬────────┘
         │
         ▼
    就绪状态
```

## 常用查询

### 查看我是谁
```sql
SELECT * FROM sys_personality_big_five;
SELECT * FROM ont_value_dimensions ORDER BY weight DESC;
```

### 查看我记得什么
```sql
SELECT namespace, key, substr(value, 1, 100) FROM evo_memory_semantic
ORDER BY last_accessed_at DESC LIMIT 10;
```

### 查看我能做什么
```sql
SELECT resource_type, COUNT(*) FROM sys_resources
WHERE status='active' GROUP BY resource_type;
```

### 查看我做过什么
```sql
SELECT category, COUNT(*) FROM tel_operations
GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10;
```

### 查看我学到什么
```sql
SELECT signal_type, COUNT(*) FROM evo_feedback_v2
GROUP BY signal_type ORDER BY COUNT(*) DESC;
```

## 账本问题处理

| 问题 | 解决方案 |
|------|----------|
| 🔴 evo_traces 空 | 运行 JSONL 导入脚本 |
| 🔴 sroe_evaluations 闭环率低 | 增加反馈收集 |
| 🟡 记忆偏少 | 多写入 evo_memory_* |
| 🟡 脚本偏少 | 代码生成后注册到 sys_scripts |

---

*Solar Data Routing Guide v1.0*
*Created: 2026-02-07*
*Part of: Solar Cortex (中枢神经系统)*
