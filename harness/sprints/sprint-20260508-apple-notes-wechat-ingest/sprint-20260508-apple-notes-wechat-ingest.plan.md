# Plan — WeChat Articles Via Apple Notes To Solar Wiki

**Sprint**: sprint-20260508-apple-notes-wechat-ingest  
**Planner**: 规划者化身  
**Created**: 2026-05-08  
**Unblocked**: `sprint-20260508-workstream-verification-closeout` → passed

---

## §1 — 分派方式

单一建设者串行执行三个切片 (S1 → S2 → S3)。每个切片完成后验证验收标准，再继续下一切片。

---

## §2 — 切片 S1: Notes 读取 + 导出 + Config + Manifest

**交付物**:

1. `/Users/sihaoli/.solar/harness/lib/apple_notes_ingest.py`
   - Commands: `doctor`, `scan`, `status`, `install-scheduler --dry-run`, `uninstall-scheduler --dry-run`
   - AppleScript 读取模式 (主) + NoteStore.sqlite 只读 fallback (测试可用)
   - 导出到 `_raw/apple-notes/YYYYMMDD/<safe-id>.md`
   - Frontmatter: source/source_app/note_id/note_title/note_folder/captured_at/updated_at/source_url/ingest_status/content_hash
   - 脱敏: PHONE/EMAIL/TOKEN/CARD/ID 正则替换
   - `--dry-run`: 仅列出候选 Notes，不写文件
   - `--full`: 跳过脱敏 (显式)
   - `--json`: 所有命令支持 JSON 输出

2. `/Users/sihaoli/.solar/harness/config/apple-notes-ingest.json`
   ```json
   {
     "notes_folder": "Solar Inbox",
     "tags": ["#solar-ingest", "#知识库", "#solar"],
     "interval_seconds": 7200,
     "raw_dir": "/Users/sihaoli/Knowledge/_raw/apple-notes",
     "all_notes": false
   }
   ```

3. `/Users/sihaoli/.solar/harness/state/apple-notes-ingest/manifest.json`
   - Delta 去重 (note_id + updated_at + content_hash)
   - 初始为 `{"version": "1", "notes": {}}`

**S1 验收**:

```bash
# A1
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "notes_access" in d and "target_folder" in d'

# A2
solar-harness notes scan --once --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "candidates" in d and d["dry_run"] is True'

# A8
solar-harness notes doctor --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["config"]["all_notes"] is False'
```

---

## §3 — 切片 S2: Wiki Ingest Dispatch + Scheduler + solar-harness.sh

**交付物**:

4. `solar-harness.sh` — 新增 `notes` 子命令族:
   ```
   solar-harness notes doctor [--json]
   solar-harness notes scan --once [--dry-run] [--force-dispatch] [--json]
   solar-harness notes status [--json]
   solar-harness notes install-scheduler --interval <s> [--dry-run] [--json]
   solar-harness notes uninstall-scheduler [--json]
   ```

5. Wiki ingest dispatch 生成:
   - 路径: `_raw/solar-harness/.dispatch/apple-notes-<note-id>-<ts>.json`
   - 内容: 要求大模型提取 concepts/entities/claims/relationships/open_questions
   - `scan --once` 默认创建 dispatch; `--force-dispatch` 强制重建已处理的 notes

6. `/Users/sihaoli/Library/LaunchAgents/com.solar.apple-notes-ingest.plist` (仅 install-scheduler 时生成)
   - `--dry-run`: 打印 plist 内容，不写文件，不 launchctl load
   - 支持间隔: 3600 / 7200 / 21600 / 86400
   - 日志: `~/.solar/harness/logs/apple-notes-ingest.out.log` + `.err.log`

**S2 验收**:

```bash
# A5
solar-harness notes scan --once --force-dispatch --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "dispatches" in d'

# A6
solar-harness notes install-scheduler --interval 7200 --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["interval_seconds"] == 7200'
```

---

## §4 — 切片 S3: Status Server + Tests + Docs

**交付物**:

7. `lib/symphony/status-server.py` — 新增 `apple_notes_ingest` section:
   ```python
   def _apple_notes_ingest_status() -> dict:
       # 读 manifest.json + config.json + launchd plist 存在性
       # 返回: enabled/interval_seconds/last_run_at/last_success_at/last_error/
       #        notes_seen/notes_exported/notes_skipped/dispatch_created/scheduler_loaded
   ```

8. `/Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh`
   - 使用 fixture mock notes (不需要真实 Notes 权限)
   - `ECC_HOME_OVERRIDE` / `APPLE_NOTES_MOCK_DIR` 测试隔离
   - 覆盖: dry-run / export / manifest 去重 / dispatch 生成 / scheduler dry-run / status payload / redaction
   - `trap 'rm -rf "$TMP"' EXIT` 清理

9. `/Users/sihaoli/.solar/harness/docs/apple-notes-wechat-ingest.md`
   - 用户工作流图
   - 权限设置步骤 (macOS 系统偏好 → 隐私与安全 → 自动操作)
   - 调度选项
   - 故障排查

**S3 验收**:

```bash
# A7
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "apple_notes_ingest" in d'

# A9
bash /Users/sihaoli/.solar/harness/tests/test-apple-notes-ingest.sh
```

---

## §5 — No-Live-Pane 保护

- 建设者不得修改 `~/.claude/` 真实配置
- 不得在 scan 时自动安装 scheduler (只 `install-scheduler` 命令可安装)
- 测试必须用临时目录隔离，不写 `~/Library/LaunchAgents/` 真实路径
- `apple_notes_ingest.py` 读取 Notes 失败时 fail-open: 返回 `{"notes_access": "denied"}` 而非抛栈追踪

---

## §6 — Stop Rules

| 条件 | 动作 |
|------|------|
| 代码扫描全量 Notes (all_notes 强制 true) | STOP |
| 读取加密/锁定笔记 | STOP |
| 直接写最终 wiki 页面 | STOP |
| 需要 WeChat 自动化 | STOP |
| LaunchAgent 在 install-scheduler 之外自动安装 | STOP |
| 测试需要真实 Notes 权限 | STOP |

---

## §7 — 验收汇总表 (建设者 Done 定义)

| 验收项 | 切片 | 验证命令 |
|--------|------|---------|
| A1 doctor JSON, notes_access + target_folder | S1 | `solar-harness notes doctor --json \| python3 -c '...assert "notes_access" in d and "target_folder" in d'` |
| A2 dry-run 不写文件，返回 candidates + dry_run=True | S1 | `solar-harness notes scan --once --dry-run --json \| python3 -c '...assert "candidates" in d and d["dry_run"] is True'` |
| A3 scan 导出 .md 到 _raw/apple-notes/ | S2 | `solar-harness notes scan --once --json \| python3 -c '...assert "exported" in d'` |
| A4 二次扫描 exported_count=0, manifest 有记录 | S2 | 两次 scan --once，第二次 exported_count==0 |
| A5 force-dispatch 返回 dispatches 列表 | S2 | `scan --once --force-dispatch --json \| python3 -c '...assert "dispatches" in d'` |
| A6 install-scheduler --dry-run 返回 interval_seconds=7200 | S2 | `install-scheduler --interval 7200 --dry-run --json \| python3 -c '...assert d["interval_seconds"] == 7200'` |
| A7 /status 含 apple_notes_ingest | S3 | `curl /status \| python3 -c '...assert "apple_notes_ingest" in d'` |
| A8 config.all_notes is False | S1 | `doctor --json \| python3 -c '...assert d["config"]["all_notes"] is False'` |
| A9 测试套件通过 (无需真实权限) | S3 | `bash tests/test-apple-notes-ingest.sh` |
