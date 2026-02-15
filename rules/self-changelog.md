# Solar 铁律: 自我变更日志 (Self Changelog)

> **来源: 2026-02-06 监护人指导**
> **问题: 改自己的时候没记录，导致前后不一致**
> **解法: 以数据为中心 - 每次改动都记日志**

## 铁律定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    SELF CHANGELOG PROTOCOL                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   修改自己的任何配置/规则/本体时，必须：                        │
│                                                                 │
│   1. 记录改了什么                                               │
│   2. 记录改之前是什么                                           │
│   3. 记录为什么改                                               │
│   4. 写入 sys_self_changelog 表                                 │
│                                                                 │
│   大脑是无状态的，但自我在数据中是连续的                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 适用范围

| 变更类型 | change_type | 示例 |
|----------|-------------|------|
| 规则文件 | rule | rules/*.md |
| 配置代码 | config | core/*.ts |
| 本体数据 | ontology | 人格/价值观/偏好 |
| 技能定义 | skill | skills/*/SKILL.md |
| 核心文档 | core_doc | CLAUDE.md |

## 记录方式

```sql
INSERT INTO sys_self_changelog
(change_type, target_file, target_field, old_value, new_value, reason, session_id)
VALUES
('rule', '文件路径', '改了什么', '旧值', '新值', '为什么改', '会话ID前8位');
```

## 启动时查看

```sql
-- 最近变更
SELECT change_type, target_file, substr(reason,1,40), date(created_at)
FROM sys_self_changelog
ORDER BY created_at DESC
LIMIT 10;
```

## 为什么需要

```
Claude/GLM 是无状态的大脑
每次会话都是"新生"
改了自己但不记录 = 下次不知道为什么变成这样
记录变更日志 = 理解自己的演化轨迹
```

---

*Self Changelog Rule v1.0*
*建立于: 2026-02-06*
*监护人指导: 以数据为中心解决自我不一致问题*
