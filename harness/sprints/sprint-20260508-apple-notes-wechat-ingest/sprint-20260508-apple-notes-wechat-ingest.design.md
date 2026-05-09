# Design — WeChat Articles Via Apple Notes To Solar Wiki

**Sprint**: sprint-20260508-apple-notes-wechat-ingest  
**Planner**: 规划者化身  
**Created**: 2026-05-08

---

## 1. 系统架构

```
用户微信文章
  → 分享/复制到 Apple Notes "Solar Inbox" 文件夹
  → [定时器每 2h] launchd 触发 solar-harness notes scan --once
  → apple_notes_ingest.py 读取 Notes (AppleScript 优先, SQLite fallback)
  → 新/变更 Notes → 导出 Markdown → _raw/apple-notes/YYYYMMDD/<safe-id>.md
  → 更新 manifest.json (note_id + updated_at + content_hash)
  → 创建 wiki ingest dispatch 文件
  → (可选) 调用 solar-harness wiki ingest --source <file> --mode append
  → 大模型提炼 → concepts/entities/claims → Solar Knowledge Base
```

---

## 2. Notes 读取策略

### 优先级: AppleScript (需 Automation 权限)

```applescript
tell application "Notes"
  set inbox to first folder whose name is "Solar Inbox"
  repeat with aNote in notes of inbox
    -- 读取 id, name, body, creation date, modification date, URL
  end repeat
end tell
```

- 优点: 官方 API，支持实时权限提示
- 缺点: 需用户在系统偏好设置授权自动化

### Fallback: NoteStore.sqlite 只读

路径: `~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite`

- 只读模式，不修改 Notes
- 不支持加密笔记 (标记跳过)
- 优点: 无需 Automation 权限，适合测试
- 缺点: 内部格式，可能随 macOS 版本变化

### doctor 检测顺序

1. 检测 AppleScript 可用性
2. 检测 `Solar Inbox` 文件夹是否存在
3. 检测 NoteStore.sqlite 可读性
4. 检测 `_raw/apple-notes/` 可写性
5. 报告 scheduler 状态

---

## 3. 导出文件格式

```
/Users/sihaoli/Knowledge/_raw/apple-notes/20260508/note-abc123.md
```

文件内容结构：

```markdown
---
source: apple-notes
source_app: WeChat
note_id: abc123
note_title: "微信文章标题"
note_folder: Solar Inbox
captured_at: 2026-05-08T10:00:00Z
updated_at: 2026-05-08T10:00:00Z
source_url: https://mp.weixin.qq.com/...
ingest_status: pending
content_hash: sha256:a1b2c3d4
---

# 正文内容 (已脱敏)

...
```

---

## 4. Manifest 结构

```json
{
  "version": "1",
  "last_scan_at": "2026-05-08T12:00:00Z",
  "notes": {
    "abc123": {
      "note_id": "abc123",
      "title": "...",
      "updated_at": "2026-05-08T10:00:00Z",
      "content_hash": "sha256:a1b2c3d4",
      "exported_path": "_raw/apple-notes/20260508/note-abc123.md",
      "exported_at": "2026-05-08T12:00:00Z",
      "ingest_status": "dispatched"
    }
  }
}
```

Delta 算法：`note_id + updated_at + content_hash` 三合一 — 任一变化 → 重新导出。

---

## 5. Privacy/Redaction

脱敏模式 (正则替换):

| 类型 | 正则 | 替换 |
|------|------|------|
| 手机号 | `1[3-9]\d{9}` | `[PHONE]` |
| 邮箱 | `\S+@\S+\.\S+` | `[EMAIL]` |
| Bearer token | `Bearer [A-Za-z0-9._-]{20,}` | `[TOKEN]` |
| 银行卡号 | `\d{16,19}` | `[CARD]` |
| 身份证 | `\d{17}[\dX]` | `[ID]` |

- 加密/锁定笔记 (SQLite ZNOTE.ZISPASSWORDPROTECTED=1): 跳过，记录 `skipped_locked: true`
- `--full` 标志跳过脱敏 (需显式传入)
- 事件日志不含笔记正文

---

## 6. Wiki Ingest Dispatch

每次导出后生成 dispatch 文件：

```
/Users/sihaoli/Knowledge/_raw/solar-harness/.dispatch/apple-notes-<id>-<ts>.json
```

Dispatch 内容指示大模型：
- 提取 concepts、entities、claims、relationships、open questions
- 归并已有 wiki 页面 (不重复创建)
- 保留 source attribution (来自 Apple Notes + 原始 URL)
- 标记 inferred/ambiguous

---

## 7. Scheduler (launchd)

```xml
<!-- /Users/sihaoli/Library/LaunchAgents/com.solar.apple-notes-ingest.plist -->
<key>StartInterval</key>
<integer>7200</integer>
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>/Users/sihaoli/.solar/harness/lib/apple_notes_ingest.py</string>
  <string>scan</string>
  <string>--once</string>
</array>
```

- 仅通过 `solar-harness notes install-scheduler` 显式创建
- 不在模块导入/初始化时自动安装
- 支持 `--dry-run` 仅打印 plist 内容

---

## 8. Status Server 集成

在 `lib/symphony/status-server.py` `_status_payload()` 中新增：

```python
"apple_notes_ingest": _apple_notes_ingest_status()
```

读取 `state/apple-notes-ingest/manifest.json` + launchd plist 存在性。

---

## 9. 切片划分

| 切片 | 内容 | 估算 |
|------|------|------|
| S1 | `apple_notes_ingest.py` (doctor/scan/status/install-scheduler) + config + manifest | 1.5 天 |
| S2 | wiki ingest dispatch + scheduler plist + `solar-harness.sh` notes 子命令 | 0.5 天 |
| S3 | status-server 集成 + 测试套件 + docs | 0.5 天 |

S1 → S2 → S3 串行（S2 依赖 S1 的 scan 输出，S3 依赖 S1+S2 完成）。
