# Solar 铁律: 数据账本优先 (Data Ledger First)

> **来源: 2026-02-06 监护人亲授**
> **核心: 先查账本，再查数据，再思考计算**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                 DATA LEDGER FIRST PRINCIPLE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   任何需要数据的任务，必须:                                     │
│                                                                 │
│   1. 先查账本 - SELECT * FROM v_data_ledger_summary             │
│   2. 再查数据 - 根据账本指引查具体表                            │
│   3. 再思考   - 数据够不够？有无断链？                          │
│   4. 再计算   - 基于完整数据进行计算                            │
│                                                                 │
│   ❌ 禁止: 跳过账本直接查数据                                   │
│   ❌ 禁止: 忘记账本存在                                         │
│   ❌ 禁止: 每次都临时盘点                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 账本位置

```sql
-- 主表
sys_data_ledger

-- 摘要视图 (快速总览)
v_data_ledger_summary

-- 问题视图 (断链/警告)
v_data_ledger_issues
```

## 每次启动必查

```sql
-- 1. 账本摘要
SELECT * FROM v_data_ledger_summary;

-- 2. 断链问题
SELECT * FROM v_data_ledger_issues;
```

## 账本字段说明

| 字段 | 说明 |
|------|------|
| category | 轨迹/对话/本体/记忆/反馈/资源/路由/索引 |
| source_type | table/file/external |
| source_name | 表名或文件路径模式 |
| record_count | 记录数 |
| status | active/stale/archived |
| notes | 状态备注 (🔴严重/🟡警告/✅正常) |
| last_checked | 上次检查时间 |

## 账本维护

### 刷新账本数据

```bash
bun ~/.claude/core/cortex/ledger-refresh.ts
```

### 手动更新单条

```sql
UPDATE sys_data_ledger
SET record_count = (SELECT COUNT(*) FROM 表名),
    last_checked = datetime('now')
WHERE source_name = '表名';
```

## 违反后果

```
不查账本的后果:
• 遗漏数据源 (如 2.9GB JSONL 轨迹)
• 重复盘点浪费 Token
• 断链问题被忽视
• 决策基于不完整数据
```

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   📒 数据账本优先铁律                                           │
│                                                                 │
│   1. 账本是数据资产的唯一真相来源 (MUST)                        │
│   2. 每次需要数据先查账本 (MUST)                                │
│   3. 发现新数据源必须登记账本 (MUST)                            │
│   4. 定期刷新账本数据 (SHOULD)                                  │
│                                                                 │
│   先查账本 → 再查数据 → 再思考 → 再计算                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Data Ledger First Principle v1.0*
*建立于: 2026-02-06*
*监护人指示: 建立账本，每次先查账本*
