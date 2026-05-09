# Design — Mirage Unified Virtual Filesystem For Solar

Sprint: sprint-20260508-mirage-unified-vfs
Source PRD: sprint-20260508-mirage-unified-vfs.prd.md
Source Contract: sprint-20260508-mirage-unified-vfs.contract.md
Created: 2026-05-08T08:15:00Z
Blocked-By: sprint-20260508-solar-kb-obsidian-autouse (P0)

## 1. 设计目标

把 Solar 现有零散数据入口（Solar DB、Cortex、Obsidian/QMD、sprint 产物、本地项目、可选 Drive）封装成一个**统一虚拟文件树**，对 agent 暴露 `solar-harness mirage exec / search` 的一致接口；同时**保留**现有 wiki ingest / accepted-artifact / 脱敏管线的语义（Mirage 是访问层，不是知识提炼层）。

**非目标对齐** (来自合约/PRD):
- 不替换 wiki/QMD/Solar DB/Cortex
- 不挂整个 `$HOME`
- FUSE 不作为 P1 DoD
- Drive 默认只读且可降级

## 2. 关键设计决策 (含不确定性标注)

| # | 决策 | 备选 | 选择 | 不确定性 |
|---|------|------|------|----------|
| D1 | SDK 选型 | Python `mirage-ai` / TS `@struktoai/mirage-node` | **Python 优先** | 实测两者本机均未安装；Python 与现有 status-server / wiki-capture-server 同栈，迁移成本最低 |
| D2 | 与上游 Mirage 耦合度 | 强依赖 / 轻 wrapper | **轻 wrapper + SDK 可选适配** | Mirage 还在快速迭代，包名/API 可能变；wrapper 让 doctor 在 SDK 缺失时仍能 `installed=false` 而不是抛栈 |
| D3 | Mount 实现 | FUSE / chroot / 逻辑映射 | **逻辑路径映射** (无 FUSE) | macOS FUSE 需内核扩展，违反 PRD"FUSE 不作为 P1 DoD" |
| D4 | Search 后端 | 自建索引 / 桥接现有 | **桥接** (`grep` + `solar-harness wiki qmd-search` + P0 router `solar-knowledge-context.py`) | 现有 wiki 已有 `qmd-search`/`ingest`/`vault-status`，重写违反 non-goal |
| D5 | Drive 凭证发现 | OAuth UX / env-only | **env + ~/.config/mirage/drive.json**，缺失即 degraded | OAuth UX 不在 P1 范围 |
| D6 | 写边界 | 静态 yaml / 动态策略 | **静态 yaml allowlist + 写时检查** | 简单可审计；动态策略未来可加 |
| D7 | 与 P0 sprint 关系 | 共享文件 / 完全独立 | **完全独立** | dispatch 硬约束"不要覆盖当前 P0 sprint 文件" |

## 3. 架构概览

```text
┌────────────────────── Solar Agent (planner/builder/eval) ──────────────────────┐
│                                                                                 │
│  $ solar-harness mirage doctor --json                                           │
│  $ solar-harness mirage workspace create --id solar-default                     │
│  $ solar-harness mirage exec -- 'find /knowledge -name "*.md"'                  │
│  $ solar-harness mirage search "Solar Harness Obsidian" --json                  │
│                                                                                 │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────── solar-harness.sh case `mirage)` ────────────────┐
│  routes to: ~/.solar/harness/lib/solar_mirage.py <subcmd> ...   │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
┌────────────────────── solar_mirage.py (Python wrapper) ──────────────────────┐
│                                                                              │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │ subcmd       │  │ workspace state  │  │ mount resolver               │  │
│  │ install/     │→ │ ~/.solar/state/  │  │ logical /knowledge -> phys   │  │
│  │ doctor/      │  │ mirage/          │  │ /Users/sihaoli/Knowledge     │  │
│  │ workspace/   │  │ <id>.json        │  │ readonly + write_allow flags │  │
│  │ exec/search/ │  └──────────────────┘  └──────────────────────────────┘  │
│  │ mounts/      │                                                           │
│  │ provision    │  ┌──────────────────────────────────────────────────────┐ │
│  └──────────────┘  │ exec sandbox                                         │ │
│                    │  - argv parser: rewrite logical → physical           │ │
│                    │  - block writes outside allowlist (raise → event)    │ │
│                    │  - timeout (default 30s) + bounded stdout (1MB)      │ │
│                    │  - secret redactor on stdout/stderr                  │ │
│                    └──────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ optional: SDK adapter (mirage-ai if importable)                      │ │
│  │ - if installed: real mirage workspace + remote resources             │ │
│  │ - if absent:    local-only mode, drive.status="disabled"             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────── mirage-search.py (unified search) ────────────────────┐
│                                                                            │
│  source 1: grep against mounted physical paths (find/rg)                  │
│  source 2: shell out to `solar-harness wiki qmd-search "<q>" --json`      │
│  source 3: shell out to `~/.solar/harness/lib/solar-knowledge-context.py` │
│            (P0 deliverable; if missing → skip, mark degraded)             │
│                                                                            │
│  rank/dedupe/truncate → max 10 hits, max 4000 chars                       │
│  emit: {hits:[{mount,path,source_type,snippet,provenance,score}], ...}    │
└────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────── status-server.py /status?section=mirage ─────────────┐
│  GET /status returns full payload incl. "mirage": {...}          │
│  payload reads ~/.solar/state/mirage/last-probe.json (TTL 30s)   │
└───────────────────────────────────────────────────────────────────┘
```

## 4. Mount 矩阵 (来自合约 A2 + PRD R2)

| Logical | Physical | Default Mode | Write 例外 | Redaction |
|---------|----------|--------------|------------|-----------|
| `/knowledge` | `/Users/sihaoli/Knowledge` | read-only | — | none (vault 已是 redacted 输出) |
| `/raw` | `/Users/sihaoli/Knowledge/_raw` | **read+write** (staging only) | 仅此 mount | 写入前 secret 扫描 |
| `/sprints` | `/Users/sihaoli/.solar/harness/sprints` | read-only | — | redact `*.events.jsonl` 中 token/key |
| `/solar` | `/Users/sihaoli/.solar` (排除 `secrets/`、`.env*`) | read-only | — | secret patterns + 文件名黑名单 |
| `/cortex` | `/Users/sihaoli/.claude/core/cortex` | read-only | — | none |
| `/projects` | yaml allowlist (空默认) | read-only | 显式 `--allow-write-projects` | none |
| `/drive` | Mirage Drive resource | read-only / `disabled` | 显式 `--allow-write-drive` | OAuth tokens never logged |
| `/qmd` | virtual (调 `qmd search/read`) | read-only | — | qmd 自身管 |

**绝不挂载**: `$HOME` 整体、`~/.ssh`、`~/.aws`、`~/Library`、`~/.config/{mirage,gcloud}/credentials*`。

## 5. 文件清单与责任

| 文件 | 状态 | 职责 | Slice |
|------|------|------|-------|
| `~/.solar/harness/config/mirage.solar.yaml` | NEW | workspace manifest，mount allowlist | S1 |
| `~/.solar/harness/lib/solar_mirage.py` | NEW | wrapper: install/doctor/workspace/exec/mounts/provision (≤500 行) | S1 |
| `~/.solar/harness/solar-harness.sh` | EDIT | 加 `mirage)` case 分支 (≤80 行 diff) | S1 |
| `~/.solar/harness/lib/mirage_search.py` | NEW | 统一搜索：grep + qmd-search + solar-knowledge-context (≤300 行) | S2 |
| `~/.solar/harness/lib/symphony/status-server.py` | EDIT | 加 `mirage` section + `last-probe.json` 读取 (≤80 行 diff) | S3 |
| `~/.solar/harness/lib/mirage_events.py` | NEW | 事件写入器: `mirage_*` 6 种事件 (≤120 行) | S3 |
| `~/.solar/harness/tests/test-mirage-unified-vfs.sh` | NEW | A1-A8 端到端 + temp workspace (≤350 行) | S3 |
| `~/.solar/harness/docs/mirage-unified-vfs.md` | NEW | install/credentials/security/examples/rollback (≤250 行) | S3 |

**严禁触碰** (P0 sprint 写入集):
- `~/.solar/harness/lib/solar-knowledge-context.py` (P0 S1 builder #1 拥有，仅调用其 CLI)
- `~/.solar/harness/lib/obsidian-vault-indexer.py` (P0 S2)
- `~/.solar/harness/integrations/wiki-capture-server.py` (P0 S3)
- `~/.solar/harness/integrations/obsidian-wiki-bridge.sh` (P0 S2)
- `~/.claude/hooks/*` (P0 S1)

## 6. Workspace YAML Schema

```yaml
# /Users/sihaoli/.solar/harness/config/mirage.solar.yaml
version: 1
workspace_id: solar-default
created_at: 2026-05-08T...

mounts:
  - path: /knowledge
    source: { type: disk, root: "/Users/sihaoli/Knowledge" }
    mode: ro

  - path: /raw
    source: { type: disk, root: "/Users/sihaoli/Knowledge/_raw" }
    mode: rw
    redact_on_write: true

  - path: /sprints
    source: { type: disk, root: "/Users/sihaoli/.solar/harness/sprints" }
    mode: ro
    redact_on_read: ["*.events.jsonl"]

  - path: /solar
    source: { type: disk, root: "/Users/sihaoli/.solar" }
    mode: ro
    deny_subpaths: ["secrets/", ".env*", "**/*.token", "**/credentials*"]

  - path: /cortex
    source: { type: disk, root: "/Users/sihaoli/.claude/core/cortex" }
    mode: ro

  - path: /projects
    source: { type: disk, allowlist_roots: [] }   # 默认空，用户显式加
    mode: ro

  - path: /drive
    source: { type: gdrive, credential_env: GOOGLE_APPLICATION_CREDENTIALS }
    mode: ro
    optional: true   # 缺凭证则 disabled，不报错

  - path: /qmd
    source: { type: virtual_command, adapter: "solar-harness wiki qmd-search" }
    mode: ro

policy:
  default_timeout_s: 30
  max_stdout_bytes: 1048576
  redact_patterns:
    - "sk-[A-Za-z0-9]{20,}"
    - "Bearer [A-Za-z0-9._-]+"
    - "api_key=[^\\s\"']+"
    - "client_secret=[^\\s\"']+"
    - "refresh_token=[^\\s\"']+"
  drive:
    write_requires_flag: --allow-write-drive
  projects:
    write_requires_flag: --allow-write-projects
```

**env 展开**: 支持 `${VAR}`，但 `--json` 输出永远显示原始模板字符串而不是值。

## 7. CLI 命令面 (合约 R3 + A1-A2-A3-A4)

```bash
solar-harness mirage install [--method pip|npm|vendor] [--dry-run]
solar-harness mirage doctor [--json]
solar-harness mirage workspace create --id <id> [--config <path>] [--json]
solar-harness mirage workspace status [--id <id>] [--json]
solar-harness mirage workspace destroy --id <id> [--force]
solar-harness mirage mounts [--id <id>] [--json]
solar-harness mirage exec [--id <id>] [--timeout <s>] -- <cmd...>
solar-harness mirage search <query> [--id <id>] [--json] [--max-hits 10] [--max-chars 4000] [--sources mirage,qmd,db]
solar-harness mirage provision --dry-run -- <cmd...>
```

**输出契约**: 所有 `--json` 模式必须发出可被 `python3 -c 'json.load(sys.stdin)'` 解析的单一 JSON 对象。

**doctor JSON schema**:
```json
{
  "enabled": true,
  "version": "0.x.y" | null,
  "sdk": { "kind": "python|ts|none", "path": "...", "version": "..." },
  "config": "/Users/sihaoli/.solar/harness/config/mirage.solar.yaml",
  "fuse": { "available": false, "reason": "macos-no-kext" },
  "mounts": [ { "path":"/knowledge", "ready":true, "mode":"ro", ... }, ... ],
  "drive": { "status": "ok|warn|degraded|disabled", "reason": "..." },
  "qmd": { "status":"ok|missing", "binary": "/opt/homebrew/bin/qmd" },
  "solar_db": { "status":"ok|missing", "path":"...", "size_mb": 263.4 },
  "last_probe_at": "ISO8601"
}
```

## 8. Search 排序与去重 (合约 A4)

```text
                  ┌── grep mirage paths (find+rg) ───→ N hits
mirage_search ────┼── qmd-search bridge ─────────────→ M hits
                  └── solar-knowledge-context (P0) ──→ K hits

合并 → 去重 (path+id) → 排序 (score desc) → 截断 (≤10 hits, ≤4000 chars)
```

每个 hit 必有: `mount`(逻辑路径), `path`(物理或逻辑), `source_type` ∈ `{mirage_path, qmd, solar_db}`, `snippet`(≤200 字), `provenance`(命令名+引用键), `score`(0-1)。

**fail-soft**: 任一源失败（qmd 未装 / P0 router 未交付 / DB 锁）→ 该源跳过，hit 集减但不报错；`degraded_sources` 字段标注。

## 9. 安全模型 (合约 A5/A6 + PRD R8)

| 边界 | 实施 |
|------|------|
| 默认只读 | yaml 中 `mode: ro` 是默认；解析层把无 `mode` 字段当 ro |
| Mount allowlist | 任何 `exec` 调用前重写 argv 中的路径，阻止逃逸（拒绝 `..`、symlink-to-outside、绝对路径在 allowlist 外） |
| Drive 写需 flag | `--allow-write-drive` 必须出现在 argv，否则 syscall 拦截抛 `WriteDeniedError` + event |
| Secret redaction | 三层: (1) yaml redact_patterns; (2) 写入 `/raw` 前扫描 (refuse on hit); (3) 所有 `--json`/event 输出脱敏 |
| Symlink escape | `realpath` 比对 mount root，越界 → 拒绝 |
| Path traversal | 解析后 `os.path.normpath` 必须以 mount root 开头 |
| Timeout | yaml `default_timeout_s` 30s 硬上限，超时 SIGKILL + event |
| Stdout cap | 1MB 截断 + `truncated:true` 标记 |
| Event 不漏密 | 事件 schema 永不包含 stdout 内容，仅包含命令名+mount+exit_code |

## 10. 状态/事件 Schema (合约 A7 + PRD R7)

**status-server `/status` 增加**:
```json
"mirage": {
  "enabled": true,
  "version": "0.x.y",
  "workspace_id": "solar-default",
  "mounts": [{"path":"/knowledge","ready":true,"mode":"ro"}, ...],
  "drive": {"status":"degraded","reason":"no credentials"},
  "qmd": {"status":"ok"},
  "last_command": "exec find /knowledge",
  "last_error": null,
  "last_probe_at": "2026-05-08T08:00:00Z"
}
```

**事件类型** (写入对应 sprint 的 `*.events.jsonl` 或 `~/.solar/harness/sprints/warn.events.jsonl`):
- `mirage_installed` `{method, version}`
- `mirage_workspace_created` `{workspace_id, mount_count}`
- `mirage_command_executed` `{cmd_kind, mount, duration_ms, exit_code}` (无 stdout)
- `mirage_mount_degraded` `{mount, reason}`
- `mirage_secret_redacted` `{mount, pattern_class, count}` (无 raw secret)
- `mirage_write_denied` `{mount, attempted_path, requested_mode}` (无内容)

## 11. 切片映射 (与 plan 对齐)

| Slice | 合约覆盖 | 文件集 | 并发边界 |
|-------|---------|--------|----------|
| **S1** install/doctor/workspace/CLI shell | A1, A2, A3, A6 部分 | `mirage.solar.yaml`, `solar_mirage.py`, `solar-harness.sh` (+mirage case) | builder #1 |
| **S2** unified search bridge | A4 | `mirage_search.py` (调 S1 工件 + P0 deliverable + 既有 wiki qmd-search) | builder #2，等 S1 PASS 后开 |
| **S3** status/events/security/tests/docs | A5, A6 完整, A7, A8 | `status-server.py` diff, `mirage_events.py`, `tests/`, `docs/` | builder #1 或 #2 续接，等 S1+S2 PASS |

## 12. 与现有 sprint 的关系

| 关系对象 | 关系 | 处理 |
|---------|------|------|
| **P0 sprint-20260508-solar-kb-obsidian-autouse** | `blocked_by` | 复用其 `solar-knowledge-context.py` 作为 search 的一个源；如未交付则 `degraded_sources:["solar_db"]` 而不阻断；builder dispatch 等 P0 PASS |
| sprint-20260507-symphony3 (passed) | 共享 status-server :8765 | 仅追加 `mirage` section，不改 routing/绑定/认证 |
| sprint-20260507-obsidian-wiki (passed) | 复用 wiki ingest 语义 | mirage 写入仅走 `/raw`，正式 wiki 页面仍由 `solar-harness wiki ingest` 处理 |
| MLSys KG sprint (passed) | 无关 | — |

## 13. 风险登记

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Mirage 上游 SDK API 变化 | 高 | 中 | 轻 wrapper，SDK 仅作 optional adapter，doctor 显示 SDK 版本 |
| `pip install mirage-ai` 拉到错误同名包 | 中 | 高 | install 默认 `--dry-run`，必须人工确认 PyPI URL+package name |
| Drive OAuth 配置卡住测试 | 高 | 低 | A5 默认无凭证场景为主路径；有凭证仅 smoke 测 |
| FUSE 用户误以为是默认 | 中 | 低 | docs 明确标注 optional；doctor 输出 `fuse.available=false, reason=...` |
| symlink/path 逃逸漏洞 | 中 | 高 | A8 测试套件覆盖 `..`、symlink-to-/etc、绝对路径攻击 |
| P0 deliverable 未及时 PASS | 中 | 中 | search 的 solar_db 源标记 optional，degraded 不阻断 A4（A4 要求 ≥2 类源，mirage_path + qmd 已可凑齐） |
| pane 抢占 (与 P0 builder) | 中 | 中 | plan §10 dispatch 严格等 P0 PASS |

