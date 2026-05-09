# Architecture Design — External Integrations Closeout

**Sprint**: sprint-20260508-external-integrations-closeout  
**Role**: planner / architect  
**Source**: PRD R1-R9 + Contract D1-D10  
**Created**: 2026-05-08T15:30:00Z

## 0. 设计目标

把"装了一半、跑歪了"的 7 个外部集成收敛成**单一可观测面 + 单一事实源协调**，并通过 schema 锁定字段，未来不静默退化。

## 1. 组件视图

```
┌────────────────────────────────────────────────────────────────────────┐
│  status-server :8765                                                   │
│  ┌──────────┐  ┌──────────────────┐  ┌──────────────────────────────┐ │
│  │ /status  │  │ /integrations    │  │ /integrations-view (NEW)     │ │
│  │ (JSON)   │  │ (JSON, exists)   │  │ (HTML Tab, NEW)              │ │
│  └────┬─────┘  └────────┬─────────┘  └────────────┬─────────────────┘ │
└───────┼─────────────────┼─────────────────────────┼───────────────────┘
        │                 │                         │
        ▼                 ▼                         ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  external-integrations-health.py (exists, freeze schema v1)     │
   │   ├─ obsidian-wiki probe                                        │
   │   ├─ qmd probe (fix: also report installed correctly)           │
   │   ├─ mermaid probe                                              │
   │   ├─ symphony probe (NEW: mode + executes_builders)             │
   │   ├─ mirage probe   (NEW: sdk.kind + drive degraded_reason)     │
   │   ├─ owl probe      (NEW: not_connected/experimental/production)│
   │   └─ google-drive probe                                         │
   └────────────────────────────┬────────────────────────────────────┘
                                ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │  schemas/integrations.schema.json (NEW, frozen v1, dated)       │
   └─────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────────┐
   │  Wiki ingest pipeline (uploads → QMD + Vault + Solar DB)         │
   │   ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐    │
   │   │ uploader       │→ │ dispatch     │→ │ writer triplet   │    │
   │   │ (writes _raw/) │  │ agent        │  │  ├─ qmd indexer  │    │
   │   └────────────────┘  └──────┬───────┘  │  ├─ vault page   │    │
   │                              │           │  └─ solar_db ✗  │    │
   │                              ▼           └──────────────────┘    │
   │                        FAILURE POINT (S1 root-cause)             │
   └──────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────────┐
   │  audit/reconciliation                                             │
   │   wiki audit-uploads --batch <ts> --json (extends per-file state)│
   │   states: full | qmd_only | vault_only | db_only |               │
   │           partial:qmd+vault | partial:qmd+db | missing            │
   └──────────────────────────────────────────────────────────────────┘
```

## 2. Schema 冻结 (D1, D9)

新文件: `~/.solar/harness/schemas/integrations.schema.json`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Solar External Integrations Status v1",
  "frozen_since": "2026-05-08",
  "version": "1.0.0",
  "type": "object",
  "required": ["generated_at", "summary", "integrations"],
  "properties": {
    "generated_at": {"type": "string", "format": "date-time"},
    "summary": {
      "type": "object",
      "required": ["ok", "warn", "missing", "total"],
      "properties": {
        "ok": {"type": "integer"},
        "warn": {"type": "integer"},
        "missing": {"type": "integer"},
        "total": {"type": "integer"}
      }
    },
    "integrations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "source", "purpose", "installed", "configured",
                     "running", "indexed", "used_by_default", "status"],
        "properties": {
          "name": {"type": "string"},
          "source": {"type": "string", "format": "uri"},
          "purpose": {"type": "string", "minLength": 10},
          "installed": {"type": "boolean"},
          "configured": {"type": "boolean"},
          "running": {"type": "boolean"},
          "indexed": {"type": "boolean"},
          "used_by_default": {"type": "boolean"},
          "status": {"enum": ["ok", "warn", "missing", "pending"]},
          "degraded_reason": {"type": "string"},
          "evidence": {"type": "object"}
        }
      }
    }
  }
}
```

字段冻结日期 `frozen_since=2026-05-08`。未来要改字段：开新 sprint + 升 schema 版本号，不允许直接改 v1。

## 3. Status UI Tab (D2, D3)

新增 endpoint: `GET /integrations-view`

- 输出 HTML（不是 JSON），独立 page，**不嵌入 `/status` 主页避免拖慢 P95**
- 表格 7 行 × 6 列：Project / Purpose / Status badge / Used by default / Degraded reason / Owner & next action
- Badge 颜色：ok=#22c55e (绿)、warn=#eab308 (黄)、missing=#ef4444 (红)、pending=#94a3b8 (灰)
- 数据源：复用 `/integrations` JSON，client side fetch + render（避免双探测）
- Owner & next action 字段：从 `final-audit.md` 静态映射读取（避免在线生成）

性能契约：
- `/status` P95 在引入 `/integrations-view` 前后波动 ≤ 5%（用 `wrk` 或 `ab` 50 次采样）
- `/integrations-view` 自身首字节 ≤ 200ms

## 4. 上传入库根因 + 三事实源协调 (D4, D5)

### 4.1 Solar DB 0/N 根因排查路径 (S1)

不靠猜，按代码路径走：

```
1. 看 dispatch agent 是否启动:
   - 找 dispatch 入口 (events.jsonl 中 wiki_dispatch_* 事件)
   - 检查 dispatch 文件 .dispatch/wiki-ingest-*.md 有没有被消费
2. 看 ingest pipeline 写库步骤:
   - grep 写 solar_db 的代码路径 (sqlite3 INSERT)
   - 看是否有写库前 throw / 静默 catch / queue 失败
3. 看 events.jsonl 是否有 wiki_db_write_* 事件
4. 比对 QMD (14/16) vs Vault (12/16) vs DB (0/16) 差异:
   - 如果 QMD/Vault 都比 DB 多很多 → 写库步骤完全没跑
   - 如果三者递减 → pipeline 早期挂掉
   - 当前数据 (14/12/0) 表明：QMD 和 Vault 走了不同路径，DB 写步骤完全没接入
```

预测根因（待 S1 验证）：DB 写步骤独立于 QMD/Vault 写步骤，且 dispatch agent 没触发它。

### 4.2 Reconciliation 状态分类 (D5)

`wiki audit-uploads --batch <ts> --json` 输出 per-file 字段升级：

| 状态值 | 定义 |
|--------|------|
| `full` | qmd_found && vault_found && solar_db_found |
| `qmd_only` | qmd_found && !vault && !db |
| `vault_only` | !qmd && vault && !db |
| `db_only` | !qmd && !vault && db |
| `partial:qmd+vault` | qmd && vault && !db |
| `partial:qmd+db` | qmd && !vault && db |
| `partial:vault+db` | !qmd && vault && db |
| `missing` | 三处都没有 |

每个 missing/partial 文件还要带 `blocker` 字段：
- `dispatch_pending` / `dispatch_failed` / `parse_error` / `oversized` / `unsupported_format` / `db_write_failed` / `unknown`

### 4.3 Backfill 兜底

`wiki backfill-uploads --batch <ts>` 必须能让一个 partial 批次跑到 full，或者输出 per-file blocker。

**Stop rule（强制兑现）**：一次 backfill 后仍 `solar_db: 0/N` → 立即升级，不允许循环重试。这条写进 plan.md 和 builder dispatch。

## 5. Mirage / Symphony / OWL 边界 (D6, D7, D8)

### 5.1 Mirage (D6)

`mirage doctor --json` 字段升级：

```json
{
  "enabled": true,
  "sdk": {
    "kind": "none | solar-logical | strukto-official | fuse",
    "path": "...",
    "version": "..."
  },
  "drive": {
    "state": "disabled | degraded | connected",
    "degraded_reason": "missing oauth token | scope insufficient | token expired YYYY-MM-DD | sdk not installed"
  },
  "mounts": [...]  // unchanged
}
```

当前实测：sdk.kind=none，drive 在原 schema 里没有独立块。本 sprint 把 drive 升到 first-class 字段。

UI 展示规则：mount.ready=true 但 drive.state!=connected 时，UI 必须明示"逻辑挂载（非真实 Drive 写入）"。

### 5.2 Symphony (D7)

`symphony status` 字段升级：

```json
{
  "mode": "dry-run | sidecar | primary-executor",
  "executes_builders": false,
  "claimed": 0, "running": 0, "retry": 0, "completed": 1,
  "issues": {...}
}
```

当前 mode=`dry-run`、executes_builders=`false`。任何 UI 文案"Symphony 在跑 builder"必须删除或 gate by `executes_builders`。

### 5.3 OWL (D8)

`integrations status` 中 owl 项 status 字段值收敛到三态：

- `not_connected`: 仓库存在但未纳入主调度（当前态）
- `experimental`: 已接入，仅 sandbox sprint 可调
- `production`: 常规 sprint 可默认调

不允许 `pending`。本 sprint 把 OWL 的 status 锁在 `not_connected` 并明示"如需提级须新 sprint"。

## 6. 测试架构 (D9)

新增 `~/.solar/harness/tests/external-integrations/`:

```
tests/external-integrations/
├── test_schema_health.sh        # 跑 integrations status --json | jq -e 验 schema
├── test_endpoint_integrations.sh # curl /integrations 验 200 + JSON
├── test_endpoint_view.sh         # curl /integrations-view 验 200 + HTML 含 7 项目
├── test_audit_uploads.sh         # 跑 wiki audit-uploads --json 验 schema
└── test_p95_no_regression.sh     # /status 引入新 view 前后 P95 ≤ +5%
```

测试栈选 **bash + jq + curl**（与现有 Solar 测试一致），不引 pytest。

## 7. 最终报告 (D10)

新增（不覆盖原 audit）: `~/.solar/harness/reports/solar-open-source-integrations-audit-20260508-final.md`

结构：
- §1 七态最终表（七个集成 × 七字段）
- §2 上传入库批次最终数据快照（前后对照）
- §3 多事实源 reconciliation 实测样本（10 个文件抽样）
- §4 Mirage / Symphony / OWL 边界对外措辞修订记录
- §5 遗留 conflicts 列表（每条带 owner + next action sprint id）
- §6 链接回原 audit 报告作为审前快照

## 8. 接口冻结 / 不动清单

绝对不动：
- 任何 sprint 的 contract.md（immutable）
- `~/.solar/harness/trajectories/`
- `/Users/sihaoli/Knowledge/concepts`、`/Users/sihaoli/Knowledge/canonical` 等正式知识库目录
- 凭据存储路径（包括 `.config/google-oauth.json` 之类）
- mermaid 渲染逻辑（mermaid 是 ok 状态，不动）

## 9. 风险设计点

| ID | 风险 | 缓解设计 |
|----|------|----------|
| R-D1 | Schema 锁死后字段难演进 | 显式版本号 + frozen_since 注释；改字段必须升 v2 |
| R-D2 | `/integrations-view` 拖慢 `/status` | 独立 page；client-side fetch；P95 测试硬卡 5% |
| R-D3 | DB 写步骤根因排查需要读代码，时间不可控 | S1 给 60min 时间盒；超时则切到"接受 0/N + 写降级文档"路径 |
| R-D4 | Backfill 修不动 | Stop rule：一次跑完 0/N 立即升级监护人 |
| R-D5 | Mirage qmd probe 当前误报 missing | 修 probe 前先证明 qmd 真的安装（已有证据）后再改字段语义 |

## 10. 不在本 design 范围

- 真实 Drive OAuth 配置（PRD Non-Goal）
- OWL 提级到 experimental/production（独立 sprint）
- Symphony 改主执行器（架构层决策）
- Wiki ingest 全链路重写（只修闭环）
- 引入 pytest 等新测试栈

