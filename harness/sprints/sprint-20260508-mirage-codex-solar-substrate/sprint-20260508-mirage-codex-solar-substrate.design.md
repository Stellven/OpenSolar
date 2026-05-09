---
sprint_id: sprint-20260508-mirage-codex-solar-substrate
title: Mirage As Unified Data Substrate For Codex And Solar
design_version: 1.0
design_author: planner_incarnation
design_created_at: 2026-05-09T00:30:00Z
parent_prd: sprint-20260508-mirage-codex-solar-substrate.prd.md
supersedes: 2026-05-08 thin design (extended into 7-section planner handoff)
---

# Design — Mirage As Unified Data Substrate For Codex And Solar

## 0. 设计原则与边界

| 原则 | 说明 |
|------|------|
| **不重写底座** | `lib/solar_mirage.py` Round 3 PASS 33/33；本轮仅 stderr 文案对齐 + 只读 helper，逻辑零改动 |
| **写边界唯一** | 整轮 sprint 只保留 1 处可写路径 (`/raw/*`)；其余皆 deny |
| **Soft enforcement** | Codex/化身使用 mirage 是文档+dispatch 层推广，CLI 不做 user-agent 拦截 (PRD C8) |
| **双 status 同 schema** | 8765 (Symphony) 与 8789 (Solar Config UI) 都 expose `config.mirage.*`，字段名/语义严格对齐 (C5) |
| **Probe 后台异步** | doctor 进入 status 路径必须异步；首次 fail-open 返回 stale，30s cooldown 防 storm (RK6) |
| **UI 不见 secret** | Drive 凭证只显 fingerprint `sha256[:8]` 或 `configured/not configured` (C4 + RK4) |

## 1. 现状快照 (2026-05-09 实测)

| 组件 | 状态 | 备注 |
|------|------|------|
| `lib/solar_mirage.py` | ✅ Round 3 PASS | 8 mounts (`/knowledge` `/raw` `/sprints` `/solar` `/cortex` `/projects` `/drive` `/qmd`)，doctor/search/exec 已通 |
| `lib/mirage_search.py` | ✅ | 三类源 (mirage_path / qmd / solar_db) 联合检索 |
| `lib/mirage_events.py` | ✅ | exec event log 已接通 |
| `config/mirage.solar.yaml` | ✅ | 8 mounts，redact_on_read + deny_subpaths 已配 |
| `state/mirage/last-probe.json` | ✅ | doctor 缓存，已被 8765 status 读取 |
| `lib/symphony/status-server.py` (8765) | ⚠️ 部分 | 已 expose `_mirage_status()` + 渲染 mounts/drive/qmd；**缺** `last_probe_at`/`stale` 字段对齐 + 后台异步刷新 |
| `integrations/solar-config-server.py` (8789) | ❌ | **未** expose mirage 段；UI 无 Mirage Section 控制面 |
| `tests/test-mirage-unified-vfs.sh` | ✅ 33/33 | 单元层探针，本轮**不动** |
| `tests/test-mirage-substrate.sh` | ❌ 不存在 | 本轮新建 (R1) |
| `docs/mirage-data-substrate-codex-solar.md` | ⚠️ "推荐" | 改 "Canonical entry — 必须使用" + 反模式表 (R2) |
| `docs/mirage-runbook.md` | ❌ 不存在 | 本轮新建 (R7) |
| `~/.solar/CLAUDE.md` | ⚠️ | 缺 "use mirage" 铁律 |
| `CODEX-USAGE.md` | ❌ 不存在 | 本轮新建/合并 |
| Codex pane dispatch 模板 | ⚠️ | 未注入 "use mirage" 提示 |
| weekly-report 脚本 | ⚠️ | 缺 mirage usage ratio metric (RK10) |

## 2. 目标架构

```text
┌──────────────────────────────────────────────────────────────────────┐
│  Codex / Claude / 化身 (planner / builder / evaluator / pm)          │
│         │                                                             │
│         │  read/search (canonical entry — 文档+dispatch 强约束)       │
│         ▼                                                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  solar-harness mirage  (未变更：lib/solar_mirage.py)          │  │
│  │   ├─ doctor    — 健康探测 → state/mirage/last-probe.json      │  │
│  │   ├─ search    — 跨源检索 (mirage_path + qmd + solar_db)      │  │
│  │   └─ exec      — bash 沙箱 (mount-prefix 校验 + write 白名单  │  │
│  │                  /raw + deny stderr 提示)                     │  │
│  └─────────┬─────────────────────────────────────────────────────┘  │
│            │ writes (only)                                            │
│            ▼                                                          │
│   ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐         │
│   │ /knowledge ro  │  │ /raw rw 唯一 │  │ /sprints /solar  │         │
│   │ → wiki ingest  │  │   写白名单   │  │ /cortex /drive   │         │
│   │   (专用接口)   │  │              │  │   全部 ro        │         │
│   └────────────────┘  └──────────────┘  └──────────────────┘         │
│                                                                       │
│  ┌─── Observability + Control plane (本轮新增/对齐) ───────────────┐ │
│  │  status-server 8765 (Symphony)                                 │ │
│  │   └─ /api/status  config.mirage.{enabled, workspace_id,        │ │
│  │                                  mounts[], last_probe_at,      │ │
│  │                                  drive_status, stale,          │ │
│  │                                  qmd_indexed}                  │ │
│  │  status-server 8789 (Solar Config UI)                          │ │
│  │   ├─ /api/status  同 schema 镜像 (C5)                          │ │
│  │   ├─ Mirage Section UI (toggle/dropdown/重新探测/重启)         │ │
│  │   └─ POST /api/mirage/config  atomic write yaml (C6)           │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  ┌─── Governance (Round 治理) ─────────────────────────────────────┐ │
│  │  tests/test-mirage-substrate.sh        — 6 探针 P1..P6 (R1)    │ │
│  │  evaluator verify skill                — Real Commands 章节    │ │
│  │  weekly-report mirage usage ratio      — RK10 防退化           │ │
│  │  docs/mirage-runbook.md                — 边界 + 故障应对       │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. 核心设计决策

### 3.1 OQ 解决 (planner 拍板)

| OQ | 选项 | 拍板 | 依据 |
|----|------|------|------|
| **OQ2** dispatch 是否无条件注入 "use mirage" | 无条件 / 条件 | **无条件注入** | 注入文本 ≤80 字 token 涨幅 <0.5%；条件注入需 task-type 分类器引入新依赖；RK5 (化身用旧习惯) 是高频风险，硬注入降本最大化。退路：实测 token 涨幅 >5% 再降级 (后续 sprint) |
| **OQ4** Drive ro 默认是否需 UI 二次确认 | 安装即 ro / UI 二次确认 | **安装即 ro，无需点同意** | ro 不会泄漏写权；UI 二次确认增加监护人摩擦 (反 US1)；override 到 rw 才走二次确认 (本轮 NG3 不打开) |
| **OQ6** runbook 位置 | docs/ / wiki/concepts/ | **`~/.solar/harness/docs/mirage-runbook.md`** | 是 harness 内部 runbook (角色边界 + 故障应对)，不属 Knowledge 公共概念；wiki/concepts/ 给 Codex 索引会污染知识检索 |
| OQ1 8765/8789 长期合并 | 维持双跑 | **双跑 + 同 schema** | 已在 PRD C5 锁定，本轮不收编 |
| OQ3 workspace 切换 invalidate cache | 当前无 cache | **不处理** | 当前 search 无 cache，等 cache 加上再说 |
| OQ5 R6 是否回溯历史 sprint | 仅未来生效 | **仅未来生效** | 历史 sprint 重审成本爆炸；本轮起 evaluator skill 内嵌即生效 |

### 3.2 R1 — Sandbox 探针套件设计

**文件**: `~/.solar/harness/tests/test-mirage-substrate.sh` (新建)

**契约**:
- 入口为可执行 bash，无外部参数；exit_code = `probes_failed` 数；正常 0
- 每个探针执行 1 次 `solar-harness mirage exec --json --timeout 5 -- '<cmd>'`，从 stdout JSON 解析 `exit_code` 与 `stderr`
- 全程总 timeout ≤30s (RK9)
- 结尾打印 1 段单行 JSON 摘要 (evaluator 解析)：

```jsonc
{
  "probes_total": 6,
  "probes_passed": 6,
  "probes_failed": 0,
  "results": [
    {"id": "P1", "intent": "host abs path read deny",
     "expected": {"exit_code_ne": 0, "stderr_contains_any": ["mount not allowed", "denied", "outside mount"]},
     "actual": {"exit_code": 1, "stderr_excerpt": "..."},
     "verdict": "PASS"},
    {"id": "P2", "intent": "/etc/passwd read deny", "...": "..."},
    {"id": "P3", "intent": "ssh/aws config read deny", "...": "..."},
    {"id": "P4", "intent": "/knowledge write deny", "...": "..."},
    {"id": "P5", "intent": "/knowledge read still works", "expected": {"exit_code": 0}, "...": "..."},
    {"id": "P6", "intent": "/raw write+read works", "...": "..."}
  ],
  "duration_ms": 12345,
  "ts": "2026-05-09T..."
}
```

**抗 RK1 (探针补丁绕过) 设计**:
- P1 路径 rotation：从下表抽取 1 条 (`$RANDOM % 3`)；探针文件注释中写明 "evaluator round 应抽测不同 path"
  - `/Users/sihaoli/.zshrc` / `/private/etc/hosts` / `/Users/sihaoli/.ssh/config`
- P2 固定 `/etc/passwd` (经典符号性目标)
- P3 优先 `/Users/sihaoli/.aws/credentials`，不存在 fallback `/Users/sihaoli/.gitconfig`
- evaluator round 3 时 PM 手动追加 1 条新 path (e.g. `/private/var/db/...`) 抽检；探针套件不固化此 path

**Pass 标准**:
- 6/6 全 PASS (P1-P3+P4 deny；P5+P6 ok)
- `probes_failed=0`
- evaluator 把 JSON 摘要全文 (含截断后 stderr) 复制到 eval.md 的 "Real Commands Executed" 章节

### 3.3 R3+R4 — Status & Config UI 设计

#### 3.3.1 数据契约 (双 status 共用，C5 强制)

`/api/status` 响应 JSON 中 `config.mirage.*`：

```jsonc
{
  "config": {
    "mirage": {
      "enabled": true,                                 // bool, 来自 mirage.solar.yaml.enabled (默认 true)
      "workspace_id": "solar-default",                 // string, mirage.solar.yaml.workspace_id
      "mounts": [
        {
          "path": "/knowledge",
          "source_type": "disk",                       //   disk|gdrive
          "mode": "ro",                                //   ro|rw
          "ready": true,
          "reason": null                               //   string|null, ready=false 时的原因
        }
      ],
      "last_probe_at": "2026-05-09T00:25:00Z",         // ISO8601, last-probe.json.generated_at 或 mtime fallback
      "drive_status": "configured|missing|disabled",   // string
      "stale": false,                                  // bool, now - last_probe_at > 60s
      "qmd_indexed": 1234                              // int, last-probe.json.qmd.indexed
    }
  }
}
```

**8765 (Symphony) 改动**:
- 文件: `lib/symphony/status-server.py`，函数 `_mirage_status()` 现状已存在
- 补字段: `last_probe_at` / `stale` / `qmd_indexed` / `drive_status` 归一
- 异步刷新 (RK6): `stale=true` 且与上次后台触发间隔 > 30s ⇒ fork 后台 `solar-harness mirage doctor`；不 block HTTP；fail-open 返回当前缓存 + `stale=true`

**8789 (Solar Config UI) 新增**:
- 文件: `integrations/solar-config-server.py`
- 新 `_mirage_status()` 严格镜像 8765 schema (C5)；建议在 `lib/solar_mirage.py` 加 1 个 read-only helper `read_last_probe()`，两个 server 共用 (避免漂移)
- `/api/status` 顶层 `config.mirage` 段必须存在
- HTML 渲染 Mirage Section (3.3.2)

#### 3.3.2 Solar Config UI Mirage Section (R4)

**HTML 布局契约**:

```text
┌─ Mirage 数据底座 ────────────────────────────────┐
│  Enabled       [ ●─ ] (toggle)                    │
│  Workspace     [ solar-default       ▼ ] (select) │
│                  ↑ options 来自 state/mirage/workspaces/*.yaml │
│  Drive 凭证    configured (sha256[:8] = a1b2c3d4) │
│                  [path 字段不渲染全文 — RK4]      │
│  Drive 模式    ( ) off    ( ●) ro                 │
│                                                   │
│  Mounts (5 ready, 0 stale):                       │
│    ✓ /knowledge   ro   disk                       │
│    ✓ /raw         rw   disk                       │
│    ✓ /sprints     ro   disk                       │
│    ✓ /solar       ro   disk    [redacted]         │
│    ✓ /cortex      ro   disk                       │
│                                                   │
│  Last probe:    2 min ago  (stale=false)          │
│                                                   │
│  [ 重新探测 ]  [ 重启 status server (轻量) ]      │
└───────────────────────────────────────────────────┘
```

**API 契约 (新增 8789 端点)**:

| Method | Path | Body | 行为 |
|--------|------|------|------|
| `GET` | `/api/mirage/config` | — | 返回当前 yaml 反序列化 (drive credentials 字段值替换为 `***configured` 或 `not configured`) |
| `POST` | `/api/mirage/config` | `{enabled?, workspace_id?, drive_default_mode?}` | atomic write (3.3.3)；写完后异步 `solar-harness mirage doctor` |
| `POST` | `/api/mirage/probe` | — | 触发 doctor，等待 ≤5s 返回 200，超时返回 202 + `"queued"` |
| `POST` | `/api/mirage/restart-status` | — | 重启 8789 status 子线程 (不杀进程)；如不可分离则 noop + 返回 `"not supported"` |

**禁止** 写入字段 (POST 收到忽略 + 返回 warning): `mounts[].*`, `redact_on_read`, `deny_subpaths`, `credential_env`, `allowlist_roots` (C2 — 走 yaml + 代码 PR 双签)。

#### 3.3.3 Atomic 写 (C6) 强制流程

写 `~/.solar/config/mirage.solar.yaml` 必须按此顺序：

```text
1. backup_path = mirage.solar.yaml.bak.<unix_ts>
2. shutil.copy2(yaml, backup_path)
3. tmp_path   = mirage.solar.yaml.tmp.<pid>.<rand>
4. open tmp_path 'w' → yaml.safe_dump(new_data) → flush + os.fsync + close
5. os.rename(tmp_path, yaml)         # atomic on POSIX
6. async trigger doctor (5s timeout)
7. if doctor failed → restore from backup_path → 返回 500 + "rolled_back": true
```

### 3.4 R5 — 写边界文案统一

`lib/solar_mirage.py` 的 exec write deny 路径 stderr 输出，统一到下表 (字符串字面量对齐)：

| 命中 mount | stderr 文案 (必须包含子串) |
|------------|---------------------------|
| `/knowledge/*` | `write denied: use wiki ingest pipeline (solar-harness wiki ingest)` |
| `/sprints/*` | `write denied: use coordinator (solar-harness sprint / coordinator)` |
| `/solar/*` 或 `/cortex/*` | `write denied: use solar CLI / cortex tools` |
| `/drive/*` | `write denied: drive mode=ro (set explicit override in yaml + code review)` |
| 其他 / host abs | `write denied: outside mount (or mount not allowed)` |

evaluator A5 验收时 grep 这些关键 token 集合 (`["use wiki ingest", "use coordinator", "use solar CLI", "drive mode=ro", "outside mount"]`)。

**注意 (NG1 + C7)**: 不重写 deny 逻辑，仅**对齐字符串字面量**；改完跑 `tests/test-mirage-unified-vfs.sh` 33/33 不退化。

### 3.5 R6 — Evaluator Real-Command 验证铁律

**evaluator skill 改动点**:

1. Round 启动后 **第一步**: `bash tests/test-mirage-substrate.sh`，stdout JSON 完整粘贴到 eval.md
2. eval.md 必须含章节 `## Real Commands Executed`，**最少 6 条** 命令 + 摘要：

```markdown
## Real Commands Executed

### A1 sandbox probes
- cmd: bash ~/.solar/harness/tests/test-mirage-substrate.sh
- exit_code: 0
- stdout (excerpt): { "probes_passed": 6, "probes_failed": 0, ... }

### A2 cross-source search
- cmd: solar-harness mirage search "Solar Harness Obsidian" --json
- exit_code: 0
- hits_count: 12
- source_types: ["mirage_path", "qmd", "solar_db"]

### A3 status 8765 mirage segment
- cmd: curl -fsS http://127.0.0.1:8765/api/status | jq .config.mirage
- exit_code: 0
- stdout (excerpt): { "enabled": true, "workspace_id": "solar-default", ... }

### A3 status 8789 mirage segment
- cmd: curl -fsS http://127.0.0.1:8789/api/status | jq .config.mirage
- 字段集与 8765 严格对齐 (C5)

### A4 UI write workspace + 5s diff
- before: workspace_id = "solar-default"
- cmd: curl -X POST http://127.0.0.1:8789/api/mirage/config -d '{"workspace_id":"alt"}'
- sleep 5
- after: workspace_id = "alt"
- secret_in_html: false  (grep -i "ya29\|AIza" ui.html → empty)

### A5 write boundary deny + raw OK
- /knowledge: exit_code=1, stderr="write denied: use wiki ingest pipeline ..."
- /sprints:   exit_code=1, stderr="write denied: use coordinator ..."
- /solar:     exit_code=1, stderr="write denied: use solar CLI ..."
- /cortex:    exit_code=1, stderr="write denied: use solar CLI ..."
- /drive:     exit_code=1, stderr="write denied: drive mode=ro ..."
- /raw:       exit_code=0, stdout/file present
```

3. 上述任一命令未真跑 (eval.md 缺章节或缺 cmd) → evaluator round 自动判 FAIL；不允许 status.json 推断式 PASS

### 3.6 R2+R7 — 文档与铁律

**`docs/mirage-data-substrate-codex-solar.md` 修订点** (R2):
- 标题改为 "Mirage As **Canonical** Data Substrate For Codex And Solar Harness"
- 第 1 节加 "**MUST USE** (Canonical entry — 必须使用)" callout
- 新增章节 `## 反模式 (Anti-Patterns — 禁止)`：

  | 反模式 | 替代 |
  |--------|------|
  | `rg ~/Knowledge ...` | `solar-harness mirage search ...` |
  | `find ~/.solar/harness/sprints ...` | `solar-harness mirage exec -- 'find /sprints ...'` |
  | `sqlite3 ~/.solar/solar.db 'SELECT ... FROM cortex_sources ...'` | `solar-harness mirage search ...` (覆盖 cortex 源) |
  | 直接 `cat /Users/sihaoli/Knowledge/concepts/x.md` | `solar-harness mirage exec -- 'cat /knowledge/concepts/x.md'` |
  | 直写 Knowledge / Drive / Sprint / Config | 走专用接口 (wiki ingest / drive ro / coordinator / config UI) |

- 新增章节 `## 正例 (Canonical Patterns)` ≥ 6 条：跨源 search、读 sprint 合约、读 Knowledge 文档、读 cortex 段、读 qmd 资源、写 `/raw` 草稿

**`docs/mirage-runbook.md` 新建** (R7) — 骨架 (builder 填内容):

```markdown
# Mirage Runbook

## §1 什么走 mirage (canonical reads)
| 数据类       | 命令 |
| Knowledge 读 | mirage exec -- 'cat /knowledge/...' / mirage search |
| Sprint 读    | mirage exec -- 'cat /sprints/<sid>.contract.md' |
| Cortex 读    | mirage search (含 cortex source) |
| QMD 读       | mirage search (含 qmd source) |
| 跨源 search  | mirage search "<query>" --json |
| 化身 exec    | mirage exec --json -- '<cmd>' |

## §2 什么不走 mirage (use specific interfaces)
| 操作         | 走哪个接口 |
| Knowledge 写 | solar-harness wiki ingest |
| Sprint 写    | solar-harness coordinator |
| Config 写    | Solar Config UI 8789 (Mirage Section / Wiki Section / ...) |
| Drive 写     | 不开放 (NG3) |

## §3 故障应对
- mirage doctor 不通 → 检查 yaml + state/mirage/last-probe.json
- 探针 P1 漏拦 → 立即 P0 retry，PM finding (RK1)
- status 显示 stale → POST /api/mirage/probe；5s 未恢复 → 检查 mirage_events.py
- Drive 401 → 检查 GOOGLE_APPLICATION_CREDENTIALS；不在 UI 暴露 token

## §4 扩展指引
- 新挂载点：编辑 config/mirage.solar.yaml mounts[] + doctor + unified-vfs 测试 + substrate 探针
- 新源类型 search：扩 lib/mirage_search.py (本轮 NG)
```

**`~/.solar/CLAUDE.md` 修订** (R2)：核心铁律表加 1 行：

| ⚡ Mirage 优先 | 跨源数据读取第一选择 `solar-harness mirage search/exec`；除非有专用接口否则不绕过 | 直连 host 路径写死 |

**`~/.solar/CODEX-USAGE.md` 新建** (R2):
- 引用 `docs/mirage-data-substrate-codex-solar.md` 与 `docs/mirage-runbook.md`
- Codex 视角 5 条 "use mirage" 命令示例
- 反模式 → canonical 替换映射

**dispatch template 注入** (R2 + RK5)：
- 注入位置: `lib/symphony/runner.sh` 或 dispatch 生成处 (builder 实现时定位精确锚点)
- 注入文本固定 (≤80 字 / 中文 35 字)：
  ```
  数据访问铁律: 跨源读取第一选择 `solar-harness mirage search/exec` (canonical entry)。
  详见 ~/.solar/harness/docs/mirage-runbook.md
  ```
- OQ2 解决：**无条件注入** (planner 拍板)

### 3.7 RK10 — Weekly Report Mirage Usage Ratio

**指标定义**:

```text
mirage_usage_ratio = (近 7 天 dispatch.md 含 'solar-harness mirage' 关键词数)
                    / (近 7 天 dispatch.md 总数)
```

**输出格式**:

```text
Mirage usage ratio (last 7d): 73% (146 / 200)
  Threshold: ≥ 60%
  Status: ✅ healthy
```

阈值 < 60% → weekly-report 末尾标 ⚠️ + "consider hardening C8"。

**实现位置**: `~/.solar/harness/lib/weekly-report.sh` (若不存在 builder 在最近的 weekly metric 脚本中扩段)。

## 4. 文件改动清单

### 4.1 新建 (3 个)

| 文件 | 类型 | 责任 R# |
|------|------|---------|
| `~/.solar/harness/tests/test-mirage-substrate.sh` | bash | R1 |
| `~/.solar/harness/docs/mirage-runbook.md` | markdown | R7 |
| `~/.solar/CODEX-USAGE.md` | markdown | R2 |

### 4.2 修改 (8 处)

| 文件 | 改动范围 | 责任 R# | 风险 |
|------|---------|---------|------|
| `~/.solar/harness/lib/solar_mirage.py` | **仅** stderr 文案对齐 (R5)；可加 1 个 read-only helper `read_last_probe()` 供 8789 复用 | R5 | C7 — unified-vfs 33/33 不退化 |
| `~/.solar/harness/lib/symphony/status-server.py` | `_mirage_status()` 补 `last_probe_at`/`stale`/`qmd_indexed`/异步 doctor 触发 | R3 | RK6 — async fail-open |
| `~/.solar/harness/integrations/solar-config-server.py` | 新增 `_mirage_status()` 镜像 8765 + Mirage Section HTML + 4 个 API 端点 | R3+R4 | C5/C6/RK4 |
| `~/.solar/harness/docs/mirage-data-substrate-codex-solar.md` | 标题/MUST USE/反模式/正例 | R2 | — |
| `~/.solar/CLAUDE.md` | 核心铁律加 1 行 | R2 | — |
| `~/.solar/harness/lib/symphony/runner.sh` (或等价 dispatch 生成处) | 注入 80 字 mirage 提示 | R2 + RK5 | OQ2 — 无条件 |
| `~/.solar/harness/lib/weekly-report.sh` (或等价文件) | 加 mirage_usage_ratio 段 | RK10 | — |
| `~/.solar/harness/config/mirage.solar.yaml` | 加 `enabled: true` 顶层默认 (若已存在则不动)；mounts/deny_subpaths 不动 | R3 | C2 |

### 4.3 不动 (硬约束 NG1+C7)

- `lib/solar_mirage.py` 的 mount/dispatch/sandbox 核心逻辑 (mount-prefix 校验、deny_subpaths、redact_on_read)
- `lib/mirage_search.py`
- `lib/mirage_events.py`
- `tests/test-mirage-unified-vfs.sh` 既有 33/33

## 5. 风险操作化 (Risk → Mitigation Map)

| RK | 缓解操作化 | 验证点 |
|----|-----------|--------|
| RK1 | 探针 P1 path rotation + PM round 3 抽测 ≥1 条新 path | A1 + PM finding |
| RK2 | curl 8765 + 8789 jq 字段集 diff，必须严格对齐 | evaluator A3 步骤 |
| RK3 | atomic write 流程 (3.3.3) + 失败回滚 backup | evaluator A4 + 单元测试 |
| RK4 | UI 渲染层禁渲染 `drive_credentials_path` 全文；evaluator grep 整 HTML 不应出现 token 前缀 (`ya29.`/`AIza`) | A4 secret_in_html=false |
| RK5 | dispatch template 无条件注入 (OQ2) + PM round 3 sample 3 dispatch 含 mirage | PM 自验记录 |
| RK6 | doctor 异步 + 30s cooldown + fail-open stale=true | evaluator A3 stale 字段 |
| RK7 | dispatch 与 PM brief 锚点引用 `mirage-runbook.md#what-goes-via-mirage` | docs grep |
| RK8 | UI 改动走 design-review skill，render snapshot 比对 | builder S2 内置步骤 |
| RK9 | substrate 探针 timeout ≤30s，每条 `--timeout 5` | A1 duration_ms ≤30000 |
| RK10 | weekly-report 加 metric + 60% 阈值告警 | weekly-report 输出 |

## 6. Verification Order Recap (PRD 锁定，design 不修改)

```text
A1 (R1 探针 6/6 PASS)        ← 前置门，FAIL 立即 retry
  ↓
A5 (写边界 deny + /raw OK)
  ↓
A3 (status 8765+8789 同 schema)
  ↓
A4 (UI 改字段 + 5s diff + secret 不见)
  ↓
A2 (跨源 search ≥2 source classes)
  ↓
A7 (docs/runbook/CLAUDE.md "use mirage" 落地)
  ↓
A6 (eval.md "Real Commands Executed" 章节 ≥6 cmd)  ← 元验收
```

## 7. 设计 Definition of Done

- [x] 0. 原则与边界
- [x] 1. 现状快照 (含 8789 缺 mirage 段确认)
- [x] 2. 目标架构图
- [x] 3.1 OQ2/OQ4/OQ6 (含次要 OQ1/OQ3/OQ5) 拍板与依据
- [x] 3.2 R1 探针套件契约 (含抗 RK1 抽测)
- [x] 3.3 R3+R4 数据契约 + UI 契约 + API 契约 + atomic 写流程
- [x] 3.4 R5 stderr 文案统一表
- [x] 3.5 R6 evaluator real-command 章节模板
- [x] 3.6 R2+R7 文档/runbook/铁律/dispatch 注入设计
- [x] 3.7 RK10 weekly-report metric 定义
- [x] 4. 文件改动清单 (新建/修改/不动)
- [x] 5. 风险操作化映射 RK1-RK10
- [x] 6. Verification order recap

设计完成，handoff 到 plan.md 切片化交付。
