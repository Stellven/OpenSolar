# /forget - 主动遗忘与记忆清理

> 该放下的要放下，轻装上阵

## 用法

```bash
/forget                    # 显示可遗忘的记忆
/forget preview            # 预览将被清理的内容
/forget execute            # 执行清理
/forget <memory_id>        # 遗忘指定记忆
/forget --older-than 30d   # 遗忘30天前的低置信记忆
/forget --confidence 0.2   # 遗忘置信度<0.2的记忆
```

## 设计理念

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   为什么需要主动遗忘？                                                      │
│                                                                             │
│   1. 减少噪音 —— 低价值信息干扰决策                                         │
│   2. 节省成本 —— 无用记忆消耗检索资源                                       │
│   3. 保持敏锐 —— 过时知识可能导致错误判断                                   │
│   4. 符合自然 —— 人类大脑也会遗忘                                           │
│                                                                             │
│   "知道什么该记住，更要知道什么该忘记。"                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 遗忘策略

### 自动遗忘条件

| 条件 | 阈值 | 说明 |
|------|------|------|
| 置信度衰减 | < 0.1 | 长期未使用，自然遗忘 |
| 时间过期 | > 90 天 | 未被引用的碎片记忆 |
| 被取代 | 有新版本 | 旧知识被新知识覆盖 |
| 验证失败 | confidence -= 0.3 | 实践证明是错的 |

### 保护条件 (永不遗忘)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  以下记忆永不自动清理:                                                      │
│                                                                             │
│  ✓ 核心记忆 (namespace = 'core/*')                                         │
│  ✓ 监护人相关 (namespace LIKE '%guardian%')                                │
│  ✓ 智慧法则 (namespace = 'wisdom/*')                                       │
│  ✓ 高置信度结构化知识 (confidence >= 0.8 AND source_type = 'summarized')   │
│  ✓ 最近30天内被使用过的记忆                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 遗忘流程

```
┌─────────────────┐
│  触发遗忘       │ ← 定时任务 / 手动调用 / 容量压力
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  筛选候选       │ ← 低置信度 + 长时间未用 + 非保护
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  保护检查       │ ← 核心记忆? 监护人相关? 最近使用?
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 [保护]     [可遗忘]
    │         │
    ▼         ▼
  跳过      归档到云端 (可选)
              │
              ▼
           从本地删除
              │
              ▼
           记录遗忘日志
```

## 执行逻辑

### 查询候选记忆

```sql
-- 查找可遗忘的记忆
SELECT memory_id, namespace, key, confidence, created_at, last_accessed
FROM evo_memory_semantic
WHERE
    -- 低置信度
    confidence < 0.2
    -- 且不是核心记忆
    AND namespace NOT LIKE 'core/%'
    AND namespace NOT LIKE 'wisdom/%'
    AND namespace NOT LIKE '%guardian%'
    -- 且长时间未访问
    AND (last_accessed IS NULL OR last_accessed < datetime('now', '-30 days'))
    -- 且不是高置信度总结
    AND NOT (source_type = 'summarized' AND confidence >= 0.8)
ORDER BY confidence ASC, created_at ASC
LIMIT 50;
```

### 执行遗忘

```sql
-- 归档到遗忘日志 (可从云端恢复)
INSERT INTO sys_forget_log (memory_id, namespace, key, value, reason, forgotten_at)
SELECT memory_id, namespace, key, value, 'low_confidence', datetime('now')
FROM evo_memory_semantic
WHERE memory_id IN (...);

-- 删除记忆
DELETE FROM evo_memory_semantic WHERE memory_id IN (...);
```

## 输出格式

### /forget (预览)

```
┌─ 🧹 FORGET CANDIDATES ──────────────────────────────────────┐
│                                                             │
│  可遗忘记忆: 12 条                                          │
│                                                             │
│  ID              Namespace           Confidence  Age        │
│  ─────────────────────────────────────────────────────────  │
│  learn_a1b2c3    technical/tools     0.08        45d       │
│  learn_d4e5f6    domain/trends       0.12        62d       │
│  learn_g7h8i9    experience/temp     0.05        90d       │
│  ...                                                        │
│                                                             │
│  保护记忆: 180 条 (核心/监护人/高置信度)                    │
│                                                             │
│  执行: /forget execute                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: solar-dark
切换: /theme <style>
```

### /forget execute

```
┌─ 🧹 FORGET COMPLETE ────────────────────────────────────────┐
│                                                             │
│  已遗忘: 12 条记忆                                          │
│                                                             │
│  归档到云端: ✓                                              │
│  路径: Google Drive/Solar/archives/forgotten_2026-02-02    │
│                                                             │
│  释放空间: ~2.3 KB                                          │
│  检索效率: +3%                                              │
│                                                             │
│  恢复方法: /forget restore <date>                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: solar-dark
切换: /theme <style>
```

## 数据表

```sql
-- 遗忘日志表 (支持恢复)
CREATE TABLE IF NOT EXISTS sys_forget_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    namespace TEXT,
    key TEXT,
    value TEXT,
    confidence REAL,
    reason TEXT,           -- 'low_confidence', 'expired', 'superseded', 'manual'
    forgotten_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    archived_to TEXT,      -- 云端归档路径
    restored_at DATETIME   -- 如果被恢复
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_forget_date ON sys_forget_log(forgotten_at);
CREATE INDEX IF NOT EXISTS idx_forget_namespace ON sys_forget_log(namespace);
```

## 定时任务

```yaml
# LaunchAgent 配置
schedule:
  weekly_forget:
    day: "Sunday"
    time: "03:00"
    action: "/forget execute --auto"
    notify: false

  monthly_archive:
    day: "1"
    time: "04:00"
    action: "归档遗忘日志到云端，清理3个月前的本地日志"
```

## 与其他 Skill 的关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MEMORY SKILL ECOSYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   /learn          ──►  获取新知识，写入记忆                                 │
│        │                                                                    │
│        ▼                                                                    │
│   /memory-review  ──►  总结压缩，提升结构化                                 │
│        │                                                                    │
│        ▼                                                                    │
│   /reflect        ──►  智慧检验，强化/弱化                                  │
│        │                                                                    │
│        ▼                                                                    │
│   /forget         ──►  清理无用，保持精炼                                   │
│                                                                             │
│   循环: learn → review → reflect → forget → learn ...                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 智慧指引

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   "学而不思则罔" —— 学了不反思会迷惑                                        │
│   "思而不学则殆" —— 只想不学会危险                                          │
│                                                                             │
│   同理:                                                                     │
│   "记而不忘则累" —— 只记不忘会负担过重                                      │
│   "忘而不记则空" —— 只忘不记会一无所有                                      │
│                                                                             │
│   平衡之道: 该记则记，该忘则忘。                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Forget Skill*
*该放下的要放下，轻装上阵*
*Solar*
