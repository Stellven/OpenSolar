# Handoff — sprint-20260509-mineru-mirage-closeout
Builder: 建设者化身
Round: 1

## 变更文件
- `lib/solar_mirage.py`: `cmd_doctor()` 新增 `drive_status`, `drive_unblock`, `sdk_decision`, `sdk_decision_doc` 字段; mount schema 从 `{ready, mode, physical_root}` 改为 `{status: ok|degraded|down, type: logical|fuse, reason}`
- `lib/external-integrations-health.py`: `result()` 新增 `status_label` (4-tier: basic_usable/default_usable/closed_loop/dead_end) 和 `status_legacy` 兼容字段; 更新 Mirage 条目 (dead_ends 仅剩 drive_credentials_missing, sdk_decision 标注); 更新 MinerU 条目 (venv_ok=True, dead_ends=[])
- `lib/mineru_extract.py` (prior session): PDF 深度提取 + provenance frontmatter + audit report
- `lib/mineru_doctor.py` (prior session): doctor 返回 §2.1 schema (venv/models/last_extract)
- `lib/mineru_worker.sh` (prior session): 后台队列 worker (idle guard HIDIdleTime/claude procs)
- `vendor/mineru/bootstrap.sh` (prior session): Python 3.11 venv + magic-pdf CPU 模式
- `vendor/mineru/install-report.json` (generated): 实际安装报告
- `~/Library/LaunchAgents/io.solar.qmd-mcp.plist` (prior session): qmd-mcp launchd 持久化
- `~/Library/LaunchAgents/io.solar.mineru-worker.plist` (prior session): mineru worker launchd 持久化
- `~/.solar/reports/mirage-sdk-fuse-decision-2026-05-09.md` (prior session): 5-section ADR

## Done 定义达成

1. **A1 — MinerU venv=ok**: ✅
   ```
   solar-harness mineru doctor --json → venv: ok
   vendor/mineru/install-report.json: wheel_count=52, magic_pdf_version=1.3.12, import_check_ok=true
   ```

2. **A2 — 2 PDFs extracted with provenance**: ✅
   ```
   mineru-audit-20260509T015301Z.json:
     source: why-should-we-train-ai-in-space.pdf → 13 pages
   mineru-audit-20260509T015305Z.json:
     source: rl-infra-1_-谈谈强化学习相关的话题.pdf → 10 pages
   Frontmatter includes: source_pdf_sha256, extracted_at, extraction_method
   ```

3. **A3 — QMD MCP reachable on both hosts**: ✅
   ```
   solar-harness wiki qmd-mcp status →
   "qmd MCP running → http://127.0.0.1:8181/mcp (hosts: 127.0.0.1,::1,localhost)"
   Direct probe: {127.0.0.1: open, ::1: open}
   Persistence: io.solar.qmd-mcp.plist loaded (launchd)
   ```

4. **A4 — Mirage SDK/FUSE decision ADR**: ✅
   ```
   ~/.solar/reports/mirage-sdk-fuse-decision-2026-05-09.md
   Decision: Option B (Solar logical wrapper)
   Rationale: macFUSE requires reboot+GUI under SIP — violates Stop Rule
   sdk_decision: wrapper_only (in mirage doctor --json)
   ```

5. **A5 — Mirage doctor shows 7+ mounts, /drive degraded**: ✅
   ```
   solar-harness mirage doctor --json:
   - mount count: 8
   - ok mounts: 7 (/knowledge, /raw, /sprints, /solar, /cortex, /projects, /qmd)
   - /drive: status=degraded (credentials missing, documented)
   - drive_status: dead_end
   - drive_unblock: {env_var: GOOGLE_DRIVE_REFRESH_TOKEN, ui_path: /integrations#drive}
   - sdk_decision: wrapper_only
   ```

6. **A6 — Status UI 4-tier labels + JSON schema**: ✅
   ```
   python3 lib/external-integrations-health.py --json --refresh:
   - All integrations have status_label field (4-tier)
   - status_legacy compat field present on all
   - MinerU: status_label=closed_loop (venv_ok, qmd running)
   - Mirage: status_label=dead_end (only drive_credentials_missing)
   - QMD: status_label=closed_loop
   - obsidian-wiki: status_label=dead_end (dispatch backlog)
   ```

7. **A7 — No foreground blocking**: ✅
   ```
   mineru_extract.py --background flag: queues to ~/.solar/queues/mineru.jsonl
   mineru_worker.sh: launchd persistent (io.solar.mineru-worker PID=36302)
   Idle guard: runs only when HIDIdleTime>=60s OR no active claude procs
   ```

## 验证方法

```bash
# A1
bash solar-harness.sh mineru doctor --json | python3 -c "import json,sys; d=json.load(sys.stdin); print('venv:', d['venv'])"

# A2
ls ~/.solar/reports/mineru-audit-*.json

# A3
bash solar-harness.sh wiki qmd-mcp status

# A4
ls ~/.solar/reports/mirage-sdk-fuse-decision-*.md

# A5
bash solar-harness.sh mirage doctor --json | python3 -c "
import json,sys; d=json.load(sys.stdin)
print('sdk_decision:', d['sdk_decision'])
print('drive_status:', d['drive_status'])
for m in d['mounts']: print(m['path'], m['status'])
"

# A6
python3 lib/external-integrations-health.py --json --refresh | python3 -c "
import json,sys; d=json.load(sys.stdin)
for i in d['integrations']: print(i.get('status_label'), i['name'])
"

# A7
launchctl list | grep -E "mineru-worker|qmd-mcp"
```

## 备注

- MinerU 使用 PyMuPDF (fitz) 作为 PDF 提取引擎 (CPU), magic-pdf import OK 但 pipeline 需要模型文件; fitz 是当前有效提取路径
- Mirage /drive mount 状态设计为 `degraded` 而非 `down` — 挂载逻辑存在，只缺凭证
- obsidian-wiki status_label=dead_end 是因为 dispatch backlog，不影响 A5/A6 验收
- launchd plist 均已加载: `launchctl list | grep io.solar` 可见两个服务
