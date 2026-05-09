# Design — Solar Data Plane Closeout

**Sprint**: sprint-20260508-data-plane-closeout  
**Planner**: 规划者化身  
**Created**: 2026-05-08

---

## 1. 现状快照 (2026-05-08 实测)

| 组件 | 状态 | 备注 |
|------|------|------|
| `state` 表 | ⚠️ 1 行 malformed (key=test_pragma, value=test) | `json_valid(value)=0` |
| `sys_data_ledger.last_checked` | ⚠️ stale 2026-02-06 | 3 个月未更新 |
| `sys_resources.updated_at` | ⚠️ stale 2026-02-23 | `access_count=0` for all |
| `knowledge_records` | ⚠️ stale 2026-02-27 | |
| `cortex_passages` | ⚠️ stale 2026-02-16 | |
| `cortex_sources` | ✅ 活跃 2026-05-06 | 正在使用 |
| `obsidian_vault_index` | ✅ 156 行 | 2026-05-08 最新 |
| `sys_capsule_executions` | ❌ 0 行 | 架构存在，运营为零 |
| bridge-ledger.jsonl | ✅ 活跃 2026-05-08 | 269 行，harness 实际在用 |
| solar CLI | ⚠️ 本地流 only | 写 `.solar/flow-state.json`，不共享 DB |

---

## 2. 问题分类

### P1 — 安全类 (必须修)

**DB concurrency**: `sqlite3` 已出现 `database is locked`，当前无统一 busy_timeout 设置。  
**Malformed state**: 1 行 `key=test_pragma value=test` — 虽是测试遗留，但 state 热路径直接 `json_valid=0`，不符合 schema 承诺。

### P2 — 可见性类 (实现 audit 命令)

以下表/层存在但状态不透明：
- 5 个核心表 stale ≥ 3 个月
- `v_solar_resources` 99 行但 access telemetry 全零
- `sys_capsule_executions` 零执行 — 分支死亡未声明

### P3 — 关系模糊类 (文档+状态命令)

`solar` CLI 写本地 `flow-state.json`，`solar-harness` 写共享 `solar.db` + harness。用户无法一眼区分两套系统的边界和活跃度。

---

## 3. 核心设计决策

### 3.1 `solar-harness data-plane audit` 命令

新增独立脚本 `lib/data_plane_audit.py`，输出 JSON + 可选 pretty table：

```
checks:
  - name: state_integrity
    stale_count: 0
    malformed_count: 1
    status: warn
  - name: sys_data_ledger
    last_checked: 2026-02-06
    age_days: 91
    status: stale
  - name: resource_usage
    total: 99
    accessed: 0
    status: dormant
  ...
overall_status: warn
```

`checks` 数组 + `overall_status` 满足 A1/A4/A6 verify 命令要求。

### 3.2 State Integrity Repair

```python
# 找出 malformed rows
rows = conn.execute("SELECT id, key, value FROM state WHERE json_valid(value)=0").fetchall()
# 备份到 state_quarantine 表 (自动创建)
conn.execute("CREATE TABLE IF NOT EXISTS state_quarantine (id,key,value,quarantined_at)")
conn.execute("INSERT INTO state_quarantine SELECT id,key,value,? FROM state WHERE json_valid(value)=0", [now])
# 删除 hot path
conn.execute("DELETE FROM state WHERE json_valid(value)=0")
```

命令: `solar-harness data-plane repair-state [--dry-run] [--json]`

### 3.3 SQLite Concurrency 硬化

标准化所有 Python 写入方：

```python
# 统一入口函数
def open_solar_db(path=None, readonly=False):
    conn = sqlite3.connect(str(path or SOLAR_DB), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```

WAL 模式允许多 reader 并发，单 writer 不阻塞 reader。对当前 SQLite-only 工作负载安全。

并发测试脚本: `~/.solar/harness/test-data-plane-db-concurrency.sh`  
- 启动 5 个并行 Python 进程同时读写
- 验证无 `database is locked` 退出码非零

### 3.4 Resource Usage Telemetry

选择 Option B: 如果 `v_solar_resources` 实际没有被检索调用更新，在 audit 中明确标记为 `"status": "dormant"` 而非伪装健康。

如果 `solar-knowledge-context.py` 确认它实际从 `sys_resources` 读取，则在读取路径上加 `UPDATE sys_resources SET access_count=access_count+1, last_accessed_at=? WHERE id=?`。

### 3.5 `solar` CLI 关系决策

选择 **Option B** (声明分离): 实现成本低，避免破坏现有 harness 生产工作流。

```bash
solar status
# 输出:
# solar CLI: active (local flow only)
# runtime: ~/.agents/skills/solar/scripts/run.sh
# state: ~/.solar/flow-state.json (local only, NOT shared with solar.db)
# solar-harness: use 'solar-harness status' for production harness
```

`solar-harness status` 保持不变，已经指向共享状态。

### 3.6 Accepted Artifact Ingestion Path

Audit 命令检查并报告:
- sprint `.finalized` 文件存在数
- `obsidian_vault_index` 中对应 artifact 的 indexed 条目数
- 如果 apple-notes-ingest 等下游 sprint 未完成，明确报告 `"blocked_by": ["sprint-20260508-apple-notes-wechat-ingest"]`

---

## 4. 切片划分

| 切片 | 内容 | 依赖 |
|------|------|------|
| S1 | data-plane audit 命令 + state repair + DB concurrency | 无 |
| S2 | resource telemetry 诚实标注 + artifact path 追踪 | S1 audit 框架 |
| S3 | `solar` CLI Option B + runbook + status UX | S1+S2 |
