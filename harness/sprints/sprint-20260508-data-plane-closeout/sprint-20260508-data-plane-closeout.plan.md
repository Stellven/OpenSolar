# Plan — Solar Data Plane Closeout

**Sprint**: sprint-20260508-data-plane-closeout  
**Planner**: 规划者化身  
**Created**: 2026-05-08  
**Unblocked**: `sprint-20260508-solar-kb-obsidian-autouse` → reviewing/will pass

---

## §1 — 分派方式

单一建设者，串行三切片 S1 → S2 → S3。每切片独立验收后再继续。

---

## §2 — 切片 S1: Audit 命令 + State Repair + DB Concurrency

**交付物**:

### D1: `lib/data_plane_audit.py`

独立 Python 脚本，可直接运行也可被 `solar-harness` 调用。

命令：`solar-harness data-plane audit [--json] [--verbose]`

输出结构（满足 A1/A4/A6 verify）：

```json
{
  "checks": [
    {"name": "state_integrity", "malformed_count": 0, "quarantined_count": 1, "status": "ok"},
    {"name": "sys_data_ledger", "last_checked": "2026-02-06", "age_days": 91, "status": "stale"},
    {"name": "sys_resources", "total": 99, "accessed_count": 0, "status": "dormant"},
    {"name": "cortex_sources", "row_count": 500, "freshest": "2026-05-06", "status": "ok"},
    {"name": "cortex_passages", "row_count": 0, "freshest": null, "status": "stale"},
    {"name": "solar_kb_entries", "row_count": 0, "freshest": null, "status": "stale"},
    {"name": "bridge_ledger", "row_count": 269, "freshest": "2026-05-08", "status": "ok"},
    {"name": "sprint_artifacts", "total_sprints": 0, "finalized": 0, "freshest": "2026-05-08", "status": "ok"},
    {"name": "resource_usage", "note": "see sys_resources check", "status": "dormant"},
    {"name": "accepted_artifact_path", "indexed_in_vault": 0, "blocked_by": [], "status": "warn"}
  ],
  "overall_status": "warn",
  "generated_at": "2026-05-08T..."
}
```

### D2: State Repair 命令

`solar-harness data-plane repair-state [--dry-run] [--json]`

- `--dry-run`: 列出 malformed 行，不修改
- 正式运行: 备份到 `state_quarantine` 表 → DELETE from `state`
- 结果验证: `json_valid(value)=0` count = 0

### D3: DB Concurrency 硬化

文件: `lib/solar_db.py` (新建共享模块)

```python
def open_solar_db(path=None, readonly=False):
    conn = sqlite3.connect(str(path or SOLAR_DB), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    if readonly:
        conn.execute("PRAGMA query_only=1")
    return conn
```

更新使用 sqlite3 的关键文件使用此函数（至少: `data_plane_audit.py`, `solar-knowledge-context.py`）。

### D4: 并发测试

`~/.solar/harness/test-data-plane-db-concurrency.sh`

```bash
# 5个并行进程同时读写，无锁死
for i in 1 2 3 4 5; do
  python3 -c "
import sqlite3, time, random
conn = sqlite3.connect('$HOME/.solar/solar.db', timeout=5.0)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA busy_timeout=5000')
conn.execute('SELECT count(*) FROM cortex_sources').fetchone()
conn.execute('INSERT OR IGNORE INTO state (key,value) VALUES (?,?) ON CONFLICT(key) DO NOTHING',
             [f'concurrency_test_$i', '{\"ok\": true}'])
conn.commit()
" &
done
wait
# 清理测试行
python3 -c "import sqlite3; conn=sqlite3.connect('$HOME/.solar/solar.db'); conn.execute(\"DELETE FROM state WHERE key LIKE 'concurrency_test_%'\"); conn.commit()"
echo "CONCURRENCY TEST PASS"
```

**S1 验收**:

```bash
# A1
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "checks" in d and "overall_status" in d'

# A2
sqlite3 ~/.solar/solar.db "select count(*) from state where json_valid(value)=0;"
# 期望: 0

# A3
bash ~/.solar/harness/test-data-plane-db-concurrency.sh
```

---

## §3 — 切片 S2: Telemetry 诚实标注 + Artifact Path

**交付物**:

### D5: Resource Usage Telemetry 决策实施

检查 `solar-knowledge-context.py` 是否实际从 `sys_resources` 读取:

- **如果读取**: 在读取路径加 `UPDATE sys_resources SET access_count=access_count+1, last_accessed_at=?`
- **如果不读取**: audit 报告 `"status": "dormant"` — 不虚假显示健康

Audit A4 check 输出 `resource_usage` key（两种情况都满足验收）。

### D6: Accepted Artifact Ingestion Path Tracking

Audit `accepted_artifact_path` check 逻辑:

```python
def check_accepted_artifact_path(conn, harness_dir):
    # 计算 finalized sprint 数
    finalized = list(Path(harness_dir/"sprints").glob("*.finalized"))
    # 检查 obsidian_vault_index 中 source 含 harness 的条目
    indexed = conn.execute(
        "SELECT count(*) FROM obsidian_vault_index WHERE path LIKE '%harness%' AND deleted_at IS NULL"
    ).fetchone()[0]
    # 检查是否被 apple-notes 或 wiki-ingest sprint 阻塞
    blocked_by = []
    for sid in ["sprint-20260508-apple-notes-wechat-ingest"]:
        sf = harness_dir / "sprints" / f"{sid}.status.json"
        if sf.exists():
            s = json.loads(sf.read_text()).get("status","")
            if s not in ("passed", "approved"):
                blocked_by.append(sid)
    status = "ok" if indexed > 0 else ("blocked" if blocked_by else "warn")
    return {"finalized_sprints": len(finalized), "indexed_in_vault": indexed,
            "blocked_by": blocked_by, "status": status}
```

**S2 验收**:

```bash
# A4
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "resource_usage" in d'

# A6
solar-harness data-plane audit --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "accepted_artifact_path" in d'
```

---

## §4 — 切片 S3: `solar` CLI 声明 + Runbook + Status UX

**交付物**:

### D7: `solar` CLI status 命令

修改 `~/.agents/skills/solar/scripts/run.sh` 或新增 wrapper，使 `solar status` 返回:

```
solar CLI v1.x — local flow mode
runtime:    ~/.agents/skills/solar/scripts/run.sh
state file: ~/.solar/flow-state.json  (local only)
harness:    NOT connected (by design)

For production harness status, run: solar-harness status
```

如果 `flow-state.json` 不存在，报告 `inactive`.

### D8: `solar-harness data-plane audit` solar 关系 section

Audit 新增 check:

```json
{"name": "solar_cli_integration", "mode": "local_only", "shared_db_writes": false, "status": "ok", "note": "solar writes ~/.solar/flow-state.json only; not sharing solar.db (Option B: by design)"}
```

### D9: Runbook `docs/data-plane-closeout.md`

内容章节:
1. 生产真相来源 (source of truth)
2. 缓存/派生层 vs 权威层
3. 如何用 `data-plane audit` 检查新鲜度
4. 如何 repair malformed state (`data-plane repair-state`)
5. `solar` vs `solar-harness` 边界说明
6. SQLite 锁风险说明 + WAL 模式说明
7. Rollback 步骤 (state_quarantine 还原)

**S3 验收**:

```bash
# A5
solar status
solar-harness status

# A7
test -f ~/.solar/harness/docs/data-plane-closeout.md
```

---

## §5 — solar-harness.sh 新增命令接入

`solar-harness.sh` 新增 `data-plane` case:

```bash
data-plane)
  shift
  _audit_script="$HARNESS_DIR/lib/data_plane_audit.py"
  case "${1:-}" in
    audit)   shift; python3 "$_audit_script" audit "$@" ;;
    repair-state) shift; python3 "$_audit_script" repair-state "$@" ;;
    *)       python3 "$_audit_script" "$@" ;;
  esac
  ;;
```

---

## §6 — 验收汇总 (Done 定义)

| 验收项 | 切片 | 验证命令 |
|--------|------|---------|
| A1 audit 返回 checks + overall_status | S1 | `data-plane audit --json \| python3 -c '...assert "checks" in d and "overall_status" in d'` |
| A2 malformed state count=0 after repair | S1 | `sqlite3 ... "select count(*) from state where json_valid(value)=0;"` → 0 |
| A3 并发测试无 locked | S1 | `bash test-data-plane-db-concurrency.sh` |
| A4 resource_usage key in audit | S2 | `data-plane audit --json \| python3 -c '...assert "resource_usage" in d'` |
| A5 solar status 明确说明本地流 | S3 | `solar status` 含 "local" 字样 |
| A6 accepted_artifact_path key in audit | S2 | `data-plane audit --json \| python3 -c '...assert "accepted_artifact_path" in d'` |
| A7 runbook 文件存在 | S3 | `test -f ~/.solar/harness/docs/data-plane-closeout.md` |

---

## §7 — Non-Goals 遵守确认

- ❌ 不重设计整体 schema
- ❌ 不迁移离开 SQLite
- ❌ 不破坏当前 solar-harness 生产工作流
- ❌ 不静默删历史数据以让指标好看
- ✅ 标记 dormant 而非假装健康 (capsule_executions=0 → audit 报告 dormant)
