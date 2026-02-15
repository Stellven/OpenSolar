# /save - 状态持久化

> 把关键状态从对话搬到外部载体，对抗 compact 失忆

## 触发词

- `/save` - 完整保存（STATE.md + memos + favorites）
- `/save quick` - 快速保存（只更新 STATE.md）
- `/save checkpoint` - 检查点保存（含 git commit）

## 执行流程

```
Step 1: 读取当前 STATE.md
Step 2: 生成结构化快照 (Mission/Constraints/Plan/Decisions/Progress/Next)
Step 3: 更新 STATE.md
Step 4: 写入备忘录 (非 quick 模式)
Step 5: 重要内容写入收藏 (非 quick 模式)
Step 6: Git commit (checkpoint 模式)
Step 7: 输出检查点宣告
```

## 备忘录写入

```sql
INSERT INTO sys_guardian_memos (memo_type, content, priority, status)
VALUES ('session_checkpoint', '当前任务: XXX | 进度: YY%', 80, 'pending');
```

## 铁律

1. compact 前必须 /save (MUST)
2. 完成子任务后 /save (SHOULD)
3. STATE.md 是唯一状态来源 (MUST)

---
*Save Skill v1.0 - 对抗 compact 失忆*
