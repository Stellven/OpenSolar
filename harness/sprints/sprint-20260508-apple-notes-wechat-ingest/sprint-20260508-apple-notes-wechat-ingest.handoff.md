# Handoff — sprint-20260508-apple-notes-wechat-ingest
Builder: 建设者化身
Round: 1

## 变更文件

- `lib/apple_notes_ingest.py`: 新建，完整实现 doctor/scan/status/install-scheduler/uninstall-scheduler 命令
- `config/apple-notes-ingest.json`: 新建，保守默认配置 (all_notes=false, Solar Inbox)
- `state/apple-notes-ingest/manifest.json`: 新建，初始空 manifest
- `solar-harness.sh`: 新增 `notes` 子命令族 (lines ~1895-1913)
- `lib/symphony/status-server.py`: 新增 `_apple_notes_ingest_status()` + `_status_payload()` 注入
- `tests/test-apple-notes-ingest.sh`: 新建，27 个测试 PASS=27 FAIL=0
- `docs/apple-notes-wechat-ingest.md`: 新建，用户工作流 + 权限设置 + 故障排查

## Done 定义达成

### A1 — Doctor And Permission Visibility
✅ `solar-harness notes doctor --json` 返回 JSON
✅ 包含 `notes_access` ("ok" 或 "denied") 和 `target_folder`
✅ 权限缺失返回 `notes_access: "denied"` + actionable error message，不抛栈追踪

### A2 — Dry Run Does Not Write
✅ `--dry-run` 返回 `candidates` 列表 + `dry_run: true`
✅ 不创建任何 `_raw/apple-notes` 文件
✅ 默认仅扫 `Solar Inbox` 文件夹（config.notes_folder）

### A3 — Export To Raw Staging
✅ scan 导出 `exported` key，列出导出文件路径
✅ 文件写入 `_raw/apple-notes/YYYYMMDD/<safe-id>.md`
✅ frontmatter 包含 source/source_app/note_id/note_title/note_folder/captured_at/updated_at/source_url/ingest_status/content_hash

### A4 — Delta Manifest Prevents Duplicates
✅ 二次扫描相同 Notes 返回 `exported_count=0`
✅ manifest 记录 note_id + modified_at + content_hash 三合一去重
✅ `state/apple-notes-ingest/manifest.json` 有效

### A5 — Wiki Ingest Dispatch Created
✅ `scan --once --force-dispatch` 返回 `dispatches` 非空列表
✅ dispatch 文件包含 `instructions.extract: [concepts, entities, claims, relationships, open_questions]`
✅ 保留 source attribution (source_url, source_app)
✅ 标记 `merge_existing_wiki_pages: true`

### A6 — Scheduler Install/Uninstall
✅ `install-scheduler --interval 7200 --dry-run --json` 返回 `interval_seconds=7200`
✅ `--dry-run` 不写 plist 文件
✅ 支持间隔: 3600/7200/21600/86400，其他值返回错误

### A7 — Status Server Observability
✅ `curl -fsS http://127.0.0.1:8765/status` 包含 `apple_notes_ingest` section
✅ 包含 enabled/interval_seconds/last_run_at/notes_seen/notes_exported/notes_skipped/dispatch_created/scheduler_loaded/ok

### A8 — Privacy Guardrails
✅ `doctor --json` 中 `config.all_notes is False`
✅ 脱敏正则覆盖: PHONE/EMAIL/TOKEN(Bearer)/CARD/ID
✅ `--full` 标志跳过脱敏（显式选项）
✅ 加密/锁定笔记 mock 测试跳过处理

### A9 — Tests
✅ `bash tests/test-apple-notes-ingest.sh` PASS=27 FAIL=0
✅ 使用 APPLE_NOTES_MOCK_DIR + ECC_HOME_OVERRIDE + HARNESS_DIR 完全隔离临时目录
✅ 不需要真实 Apple Notes 权限
✅ 覆盖: dry-run/export/manifest去重/dispatch/scheduler-dry-run/status/redaction(3项)

## 验证方法

```bash
# A1
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "notes_access" in d and "target_folder" in d'

# A2
solar-harness notes scan --once --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "candidates" in d and d["dry_run"] is True'

# A6
solar-harness notes install-scheduler --interval 7200 --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["interval_seconds"] == 7200'

# A7
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "apple_notes_ingest" in d'

# A8
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["config"]["all_notes"] is False'

# A9
bash /Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh
# PASS=27 FAIL=0

# A3/A4/A5 — 需要 Solar Inbox 中有真实 Notes 或使用 APPLE_NOTES_MOCK_DIR:
export APPLE_NOTES_MOCK_DIR=/tmp/mock  # 放 *.json mock 文件
solar-harness notes scan --once --json
solar-harness notes scan --once --json  # exported_count=0
solar-harness notes scan --once --force-dispatch --json
```

## 备注

- `all_notes` 默认 `false`，不会扫全量备忘录，stop rule 已遵守
- LaunchAgent 只由 `install-scheduler` 命令创建，scan 不会自动安装
- `_REAL_HOME = Path.home()` 保证 PLIST_PATH 等系统路径不受 `ECC_HOME_OVERRIDE` 影响（测试隔离安全）
- status-server.py 的 `_apple_notes_ingest_status()` 使用 `import subprocess as _sp` 局部引入避免顶层命名空间污染
- A3/A4/A5 合约验证需要真实 Notes 或 MOCK_DIR — 测试套件 A9 已通过 mock 验证所有逻辑
