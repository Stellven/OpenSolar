# Design — Solar KB Default Retrieval + Obsidian Seamless Sync

Sprint: sprint-20260508-solar-kb-obsidian-autouse
Source PRD: sprint-20260508-solar-kb-obsidian-autouse.prd.md
Source Contract: sprint-20260508-solar-kb-obsidian-autouse.contract.md
Created: 2026-05-08T07:00:00Z

## 1. 设计目标

把 Solar 知识层从"理论上自动"变成"实际默认自动"。每个知识相关 prompt 都拿到 sourced、bounded、低延迟的上下文；Obsidian vault 成为 Solar 检索的一等公民来源。fail-open 是底线 — 任何故障都不能阻塞 agent。

## 2. 架构概览

```text
┌──────────────────────────── User Prompt ────────────────────────────┐
│                                                                      │
│  Claude UserPromptSubmit                                             │
│         ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  ~/.claude/hooks/solar-knowledge-context.sh  (Slice 1)        │ │
│  │  - heuristic: knowledge-dependent prompt?                     │ │
│  │  - timeout 800ms hard cap, fail-open silent                   │ │
│  │  - injects <solar-knowledge-context>...</solar-knowledge-context>│ │
│  └────────────────────────────────────────────────────────────────┘ │
│         ↓ subprocess (python3 stdlib)                                │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  ~/.solar/harness/lib/solar-knowledge-context.py  (Slice 1)   │ │
│  │  - SOURCE 1: ~/.solar/solar.db                                │ │
│  │      → fts_unified_search MATCH ?                             │ │
│  │      → cortex_sources LIKE                                    │ │
│  │      → evo_memory_semantic.value (NOT content!)               │ │
│  │  - SOURCE 2: obsidian_vault_index (FTS5 mirror)               │ │
│  │  - rank, dedupe, truncate to --max-chars (default 2000)       │ │
│  │  - emit JSON: {hits:[{source,table,id,path,snippet,score}],   │ │
│  │                 elapsed_ms, query, truncated}                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                                     ↑
                                     │ shared FTS index
                                     │
┌──────────────── Background Sync (Slice 2) ────────────────┐
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ knowledge-sync.ts (TS, called by capture-server)     │ │
│  │  - watch /Users/sihaoli/Knowledge/**/*.md            │ │
│  │  - manifest: ~/.solar/state/knowledge-manifest.json │ │
│  │  - parse frontmatter + title + tags + summary       │ │
│  │  - upsert into obsidian_vault_index (new table)     │ │
│  │  - register into fts_unified_search                  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ obsidian-wiki-bridge.sh (DB → vault)                 │ │
│  │  - --since <ts> --no-dispatch incremental            │ │
│  │  - writes ONLY under _raw/solar-db-export/           │ │
│  │  - manifest: _raw/.export-manifest.json              │ │
│  │  - secret redaction (token/key patterns)             │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
                                     ↑
                                     │ scheduler trigger
                                     │
┌─────────────── Automation + Status (Slice 3) ──────────────┐
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ wiki-capture-server.py (extend)                      │  │
│  │  - GET /healthz   → 200                              │  │
│  │  - GET /status    → JSON with solar_kb + obsidian_sync│  │
│  │  - internal scheduler: every 60s call sync if idle   │  │
│  │  - never block /capture or /upload during sync       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Observability fields:                                      │
│  - solar_kb: {db_path, db_size, indexed_pages,             │
│                hook_enabled, last_query_ms_p95}            │
│  - obsidian_sync: {vault_path, last_sync_at,               │
│                     pending_raw, indexed_count,            │
│                     last_error, manifest_age_s}            │
└─────────────────────────────────────────────────────────────┘
```

## 3. 文件清单与责任

| 文件 | 状态 | 职责 | Slice |
|------|------|------|-------|
| `~/.solar/harness/lib/solar-knowledge-context.py` | NEW | bounded retrieval router (DB + vault) | S1 |
| `~/.claude/hooks/solar-knowledge-context.sh` | NEW | UserPromptSubmit wrapper, 800ms timeout, fail-open | S1 |
| `~/.claude/hooks/memory-influence.sh` | EDIT | fix `value` field + SQL parens | S1 |
| `~/.claude/core/cortex/knowledge-sync.ts` | EDIT | add `/Users/sihaoli/Knowledge` as 1st-class vault, manifest | S2 |
| `~/.solar/harness/integrations/obsidian-wiki-bridge.sh` | EDIT | `--since`/`--no-dispatch` formal, manifest + secret redact | S2 |
| `~/.solar/harness/lib/obsidian-vault-indexer.py` | NEW | parse frontmatter/title, upsert into `obsidian_vault_index` + fts | S2 |
| `~/.solar/harness/integrations/wiki-capture-server.py` | EDIT | `/healthz` + `/status` payload (solar_kb, obsidian_sync) + scheduler | S3 |
| `~/.solar/harness/tests/test-solar-kb-obsidian-autouse.sh` | NEW | A1-A7 verify + temp DB/vault fixtures | S3 |
| `~/.solar/harness/docs/solar-kb-obsidian-autouse.md` | NEW | runbook: install, verify, disable, repair | S3 |

## 4. 数据模型

### 4.1 现有表 (使用，不修改)

- `cortex_sources` — 主知识库行（finding/title/citation_key）
- `evo_memory_semantic` — schema 是 `value JSON NOT NULL`，**不是 content**（这是合约 A4 要修的根因）
- `fts_unified_search` — 已有的统一 FTS 表
- `knowledge_entities` — 实体图（命中加分）

### 4.2 新表 `obsidian_vault_index`

```sql
CREATE TABLE IF NOT EXISTS obsidian_vault_index (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  vault_path TEXT NOT NULL,           -- 绝对路径，如 /Users/sihaoli/Knowledge/projects/x.md
  rel_path TEXT NOT NULL,             -- 相对 vault 根
  title TEXT,
  tags TEXT,                          -- JSON array
  summary TEXT,                       -- frontmatter summary 或前 200 字
  body_excerpt TEXT,                  -- 索引用前 1000 字
  mtime REAL NOT NULL,
  size_bytes INTEGER,
  content_hash TEXT,                  -- sha1，避免 mtime 抖动重写
  indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(vault_path)
);
CREATE INDEX IF NOT EXISTS idx_obs_vault_mtime ON obsidian_vault_index(mtime);
```

外加注册到 `fts_unified_search`（doc_type='obsidian_page', doc_id='obs:'||id）。

### 4.3 Manifest 文件

- `~/.solar/state/knowledge-manifest.json`
  ```json
  {
    "vault_path": "/Users/sihaoli/Knowledge",
    "last_full_scan_at": "2026-05-08T07:00:00Z",
    "last_incremental_at": "2026-05-08T07:01:00Z",
    "indexed_count": 0,
    "skipped_count": 0,
    "last_error": null
  }
  ```
- `/Users/sihaoli/Knowledge/_raw/.export-manifest.json` — DB→vault 导出 cursor (per-table last_id)

## 5. 接口契约

### 5.1 CLI: `solar-knowledge-context.py`

```
python3 solar-knowledge-context.py \
  --query "<text>" \
  [--max-chars 2000] \
  [--max-hits 8] \
  [--timeout-ms 800] \
  [--fail-open] \
  [--json] \
  [--sources db,vault]
```

输出 (JSON 模式):
```json
{
  "query": "Solar 记忆系统",
  "elapsed_ms": 142,
  "truncated": false,
  "hits": [
    {"source":"db", "table":"cortex_sources", "id":"...", "title":"...", "snippet":"...", "score":0.83},
    {"source":"vault", "path":"/Users/sihaoli/Knowledge/.../lumen-orbit-...md", "title":"...", "snippet":"...", "score":0.71}
  ]
}
```

输出 (文本/注入模式):
```xml
<solar-knowledge-context query="Solar 记忆系统" hits="3" elapsed_ms="142">
[1] db/cortex_sources#... — <title>
    <snippet 200 chars>
[2] vault: <rel_path>
    <snippet 200 chars>
</solar-knowledge-context>
```

### 5.2 Hook: `solar-knowledge-context.sh`

- 入参: `$CLAUDE_USER_PROMPT` (或 stdin)
- 启发式触发：prompt 命中 `知识|记忆|Solar|历史|架构|sprint|教训|经验|cortex|obsidian|knowledge|memory|architecture|lesson` 关键词，或长度 >40 字符
- 走 subprocess `timeout 0.8` python3，超时 → 静默退出 0
- 输出 stdout: `<solar-knowledge-context>...</solar-knowledge-context>`（被 Claude 注入提示词）
- ENV 开关: `SOLAR_KB_CONTEXT=0` 关闭，默认开

### 5.3 HTTP: `wiki-capture-server.py`

- `GET /healthz` → `200 ok\n` (纯文本)
- `GET /status` → JSON:
  ```json
  {
    "ok": true,
    "ts": "...",
    "solar_kb": {
      "db_path": "/Users/sihaoli/.solar/solar.db",
      "db_size_mb": 263.4,
      "indexed_pages": 142,
      "hook_enabled": true,
      "last_query_ms_p95": 187
    },
    "obsidian_sync": {
      "vault_path": "/Users/sihaoli/Knowledge",
      "last_sync_at": "2026-05-08T07:01:00Z",
      "pending_raw": 3,
      "indexed_count": 142,
      "last_error": null,
      "manifest_age_s": 38
    },
    "capture": {...},
    "dispatch": {...}
  }
  ```

## 6. 安全与降级 (Fail-Open Matrix)

| 故障场景 | 表现 | 退化策略 |
|----------|------|----------|
| `~/.solar/solar.db` 缺失 | 文件不存在 | router 返回 `{hits:[],elapsed_ms:0}`，hook 输出空 |
| DB 锁 (write 中) | sqlite BUSY | `PRAGMA busy_timeout=200` + try once，失败 fail-open |
| Vault 路径不存在 | `/Users/sihaoli/Knowledge` 缺 | 仅查 DB，不报错 |
| Python 启动慢 | 冷启动 >800ms | hook 端 `timeout 0.8`，超时 silent |
| 索引腐败 | FTS 异常 | catch + 写 manifest.last_error，不抛栈 |
| Secret 泄漏 | DB 行含 token/key | 导出端正则脱敏 (sk-/Bearer/api_key=) |
| status server 离线 | port 8765 不通 | hook 不依赖 server，独立工作 |

## 7. 切片映射 (与 plan 对齐)

| Slice | Done 条件覆盖 | 文件写入集 | 并发边界 |
|-------|---------------|------------|----------|
| S1 retrieval + memory fix | A1, A4, A6 | 3 文件 (lib + 2 hook) | builder #1，独占 `~/.solar/harness/lib/solar-knowledge-context.py` + `~/.claude/hooks/*` |
| S2 indexing + export | A2, A3 | 3 文件 (knowledge-sync.ts, indexer.py, bridge.sh) | builder #2，独占 `~/.solar/harness/lib/obsidian-vault-indexer.py` + integrations/* + cortex/* |
| S3 status + tests + docs | A5, A7 | 3 文件 (capture-server.py, tests/, docs/) | 由 S1/S2 完成后任一 builder 串行（依赖前两者产物） |

## 8. 关键决策

- **不重写 knowledge-sync.ts**: 仅扩展 `/Users/sihaoli/Knowledge` 为 first-class，保留旧路径向后兼容。
- **新表 vs 现有表**: 新建 `obsidian_vault_index` 而不是直接塞 `cortex_sources`，避免污染现有知识源、便于回滚（DROP TABLE 即可）。
- **manifest 而非全扫**: 263MB DB + 不限大小 vault，必须增量。manifest 比 mtime-only 更可靠（处理时区跳变、touch 误触）。
- **Python stdlib only**: status server 已是 stdlib，索引器也走 stdlib（sqlite3 + json + re），零新依赖。
- **不默认启用** vs **默认启用**: 选默认启用 + `SOLAR_KB_CONTEXT=0` 退出阀。理由：PRD 明确"默认自动使用"是核心目标；fail-open 已经覆盖故障路径，开关默认 off 等于继续不可用。
- **scheduler 选 capture-server**: 不引 launchd（昊哥设备多，launchd 跨设备同步麻烦），不开新 daemon（增加运维面）。capture-server 已经在跑，加内嵌 60s tick 最经济。

## 9. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Python 冷启动 >800ms 拖慢 prompt | 中 | 中 | hook timeout 硬截断 + fail-open；可选预热进程 |
| FTS5 中文分词差 | 中 | 中 | unicode61 + 启用 trigram 备份；body_excerpt 兜底 LIKE |
| 大 vault 全扫慢 | 中 | 低 | manifest 增量；首次扫加 progress log，不阻塞 |
| 用户改动 _raw/ 被覆盖 | 低 | 高 | 导出端只写 `_raw/solar-db-export/`，禁动其他子目录 |
| GLM 1210 复发挡 builder | 中 | 中 | 沿用 SOLAR_NO_ZHIPU=1 + Sonnet (STATE.md 决策) |
| pane 抢占 (与未结 sprint) | 低 | 中 | plan 第 4 节已加 coord-status check + SESSION_NAME mock 测试 |

## 10. 与现有 sprint 的关系

- 与 `sprint-20260507-obsidian-wiki` (passed): 复用其 vault 安装/symlink/_raw 结构。本 sprint **不重装** wiki，只补检索路径与同步自动化。
- 与 `sprint-20260507-symphony3` (passed): status server :8765 已建，本 sprint 只**追加 payload 字段**，不改路由/绑定/认证。
- 与 STATE.md Sprint 2 (workspace 4 hook): 不冲突，hook 路径独立。

