# Solar 铁律: Schema First (查询前先读结构)

> **来源: 2026-02-06 监护人指正**
> **问题: 频繁猜测表结构导致查询出错，浪费时间修复**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCHEMA FIRST PRINCIPLE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   查询数据库前，必须先确认表结构                                │
│                                                                 │
│   ❌ 禁止: 凭记忆猜测字段名                                     │
│   ❌ 禁止: 先执行再根据错误修复                                 │
│   ✓ 必须: 先读 SCHEMA_QUICK.md 或执行 PRAGMA                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 快速参考文件

**位置:** `~/.claude/core/SCHEMA_QUICK.md`

**常见陷阱:**
| 表 | ❌ 错误字段 | ✓ 正确字段 |
|----|------------|------------|
| sys_skills | name, usage_count | skill_id, command |
| sys_shortcuts | status | (无此字段) |
| sys_agents | status | (无此字段) |
| sroe_requests | model_id, success | selected_model, finish_reason |

## 执行流程

```
需要查询数据库
       │
       ▼
┌─────────────────┐
│ 读 SCHEMA_QUICK │ ← 5秒
└────────┬────────┘
       │
       ▼
  确认字段名正确
       │
       ▼
   执行查询 (一次成功)
```

## 更新 Schema 快照

修改表结构后执行:
```bash
~/.claude/core/db-schema-snapshot.sh
```

## 本次教训

```
错误次数: 4 次
浪费时间: ~2 分钟
原因: 猜测 sys_skills.name, sroe_requests.model_id 等不存在的字段

正确做法: 5 秒读一下 SCHEMA_QUICK.md
```

---

*Schema First Rule v1.0*
*建立于: 2026-02-06*
*知行合一 - 先确认再执行*
