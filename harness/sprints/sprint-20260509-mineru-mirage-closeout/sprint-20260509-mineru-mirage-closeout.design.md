# Design — MinerU + Mirage Full Closure

> Sprint: sprint-20260509-mineru-mirage-closeout
> Author: planner
> Date: 2026-05-09
> Inputs: contract.md (A1-A7 + Stop Rules), prd.md (FR-1..7, Constraints C1-C7, OQ ×6)

## §0 Design Scope

本设计文档约束**架构层面的接口与组件拓扑**，不涉及具体代码。Builder 必须遵守：
- 所有 doctor/status JSON schema 的字段名称与语义
- 4 个 slice 的边界（不跨 slice 改文件）
- Stop Rule 的硬触发条件

## §1 Architecture Overview

### 当前态 (虚假繁荣)
```
/integrations UI ─── status="ok" (字符串硬编码)
        │
        ▼
solar-harness wiki ─── wrapper 层 (JS/TS) ── 报 venv=ok (假信号)
        │
        ▼
MinerU vendor ────── 没有 .venv，pip 装不全
Mirage 路径映射 ───── 字符串前缀替换，没有真 mount
QMD MCP ───────────── 只绑 127.0.0.1，关 shell 即死
```

### 目标态 (Closed Loop)
```
/integrations UI ─── status: 4 档枚举 (basic/default/closed/dead)
        │
        ├─ MinerU: doctor JSON {venv, models, last_extract}
        ├─ Mirage: doctor JSON {mounts[], drive_status, sdk_decision}
        └─ QMD MCP: status JSON {hosts[v4,v6], persistence}
        │
        ▼
launchd / tmux detached daemon ─ 持久化 QMD MCP, embedding worker
        │
        ▼
vendor 真实运行 (.venv 完整 + provenance audit)
```

## §2 Component Contracts (JSON Schemas)

### §2.1 `mineru-doctor` JSON 输出
```
{
  "venv": "ok" | "missing" | "broken",
  "venv_path": "<abs path>",
  "lock_file": "<abs path>" | null,
  "models": { "layout": "ok"|"missing", "ocr": "ok"|"missing" },
  "last_extract": { "ts": ISO8601, "source": "<pdf path>", "pages": int } | null,
  "errors": [{ "code": str, "msg": str, "actionable": str }]
}
```
**契约**: `venv=ok` 必须基于实际 `python -m pip check` 成功 + 关键导入测试通过；不允许只检查目录存在。

### §2.2 `mirage doctor` JSON 输出
```
{
  "mounts": [
    { "path": "/knowledge", "status": "ok"|"degraded"|"down", "type": "logical"|"fuse", "reason": str }
  ],
  "drive_status": "connected" | "dead_end" | "disabled",
  "drive_unblock": { "env_var": "GOOGLE_DRIVE_REFRESH_TOKEN", "ui_path": "/integrations#drive" } | null,
  "sdk_decision": "installed" | "wrapper_only",
  "sdk_decision_doc": "<reports/mirage-sdk-fuse-decision-*.md>"
}
```
**契约**: 至少 5 个 mount (`/knowledge /raw /sprints /db /qmd`)；缺一即 `status=down`，doctor 整体 fail。

### §2.3 `qmd-mcp status` JSON 输出
```
{
  "hosts": [
    { "addr": "127.0.0.1:8181", "reachable": bool, "latency_ms": float },
    { "addr": "[::1]:8181", "reachable": bool, "latency_ms": float }
  ],
  "persistence": "launchd" | "tmux" | "ephemeral",
  "pid": int,
  "uptime_s": int
}
```
**契约**: `persistence != ephemeral` 才允许 UI 标 `closed loop`。

### §2.4 `/integrations` 状态 JSON
```
{
  "components": [
    { "name": "MinerU", "label": "basic_usable"|"default_usable"|"closed_loop"|"dead_end",
      "evidence": { "doctor_cmd": str, "last_check": ISO8601 },
      "unblock": { "action": str, "doc": str } | null,
      "status_legacy": "ok" | null   // 兼容字段, 6 周后弃用
    }
  ]
}
```
**契约**: 任何 label 都必须有 `evidence.doctor_cmd`，UI 不允许硬编码字符串。

## §3 Persistence Model

### §3.1 QMD MCP 持久化
**选 launchd** (优先) over tmux：
- launchd plist 模板: `~/Library/LaunchAgents/io.solar.qmd-mcp.plist`
- 同时绑两端 socket: `0.0.0.0` 禁止；用 `SocketProtocolFamily=IPv4` + `IPv6` 两组 socket
- KeepAlive=true, RunAtLoad=true
- doctor 通过 `launchctl list | grep io.solar.qmd-mcp` 验证

**fallback 到 tmux** 仅当 launchd 失败 (例如沙盒限制)，但 UI 必须降级到 `default_usable`。

### §3.2 Embedding/PDF 长任务后台化
- 重活通过 `solar-harness mineru extract --background` 提交
- 后台 worker 也走 launchd (`io.solar.mineru-worker.plist`)
- 队列文件: `~/.solar/queues/mineru.jsonl` (append-only)
- **Idle guard**: worker 启动前 query `ioreg -c IOHIDSystem | grep HIDIdleTime` ≥ 60s 或 `pgrep -f "claude" | wc -l == 0`，否则降并发到 1
- 用户活跃时 worker 自动暂停（SIGSTOP），idle 后 SIGCONT

## §4 SDK/FUSE Decision Framework

ADR 文档名: `reports/mirage-sdk-fuse-decision-2026-05-09.md`

ADR 必须含 5 段：
1. **Context**: macOS 24.6 / Apple Silicon 当前 FUSE 状态（macFUSE 是否安装、SIP 状态、kext 授权）
2. **Options**:
   - A) 装 macFUSE + Mirage SDK
   - B) 保留 Solar 逻辑 wrapper
   - C) 混合（FUSE 仅供测试，wrapper 是默认）
3. **Decision matrix**: 性能基线（mount 50K 文件 ls 延迟）、权限风险、可维护性、用户工作流影响
4. **Decision**: 选项 + 理由
5. **Reversibility**: 怎么回退、什么信号触发回退

**默认推荐**: B（wrapper），除非 builder 实测 FUSE 能在 5 分钟内零交互装好。

## §5 Data Flow: PDF → Obsidian

```
PDF (in /Users/sihaoli/Knowledge/_raw/file-uploads/*.pdf)
        │
        ▼
solar-harness mineru extract <pdf-path>
        │ (后台 job, 立即返回 job-id)
        ▼
MinerU vendor pipeline (.venv 内执行)
        │
        ├─ layout detection
        ├─ OCR (CPU only, no CUDA)
        └─ markdown 生成
        │
        ▼
Obsidian /references/<slug>/ 下：
        index.md (frontmatter: provenance, source_pdf, source_pages, mineru_version)
        page-001.md, page-002.md, ...
        │
        ▼
Audit report: ~/.solar/reports/mineru-audit-2026-05-09.json
        { source: "<pdf>", generated_pages: ["..."], duration_s: int }
```

**Provenance frontmatter 标准**:
```
---
source_pdf: /Users/sihaoli/Knowledge/_raw/file-uploads/foo.pdf
source_pdf_sha256: <hash>
source_page: 12
mineru_version: <semver>
extracted_at: ISO8601
---
```

## §6 Testing Strategy: Fresh-Shell Probes

Evaluator 必须在 **fresh shell** 重跑探针（不许 cache）：
- 启动新 tmux pane
- `solar-harness wiki mineru-doctor --json` → 验证 venv=ok
- `solar-harness mirage doctor --json` → 验证 mounts ≥ 5
- `solar-harness wiki qmd-mcp status --json` → 验证 v4+v6 双协议
- `curl -s http://127.0.0.1:8765/integrations` → 验证 4 档标签 schema

任一探针失败 → sprint FAIL（无回退余地）。

## §7 Cross-Cutting Concerns

| 关切 | 设计 |
|------|------|
| 可观测性 | 所有 doctor/status 命令支持 `--json` + `--verbose`；事件写 `~/.solar/harness/events.jsonl` |
| 安全 | MCP 绝不绑 0.0.0.0；Drive token 只走 keychain，不写明文 |
| 可回滚 | 每个 slice 完成时 git commit（builder 责任）；ADR 决策可逆 |
| 兼容 | `status=ok` 字符串保留 6 周 (`status_legacy`)，期间 UI 同步双发 |

## §8 Open Questions Routed Forward

| OQ | 来源 | 设计层处理 | 留给 |
|---|---|---|---|
| OQ1 (PDF 后处理质量) | PRD §10.1 | 不在本 sprint，scope 控制 | 后续 sprint |
| OQ2 (ADR 编号) | PRD §10.2 | 用 `mirage-sdk-fuse-decision-2026-05-09.md` 单文档，不入 INFRA-ADR | 已决策 |
| OQ3 (UI 标签 per-component) | PRD §10.3 | 扁平展开（每 component 独立条目） | 已决策 |
| OQ4 (持久化方案) | PRD §10.4 | launchd 优先，tmux fallback | 已决策（§3.1） |
| OQ5 (idle guard 信号) | PRD §10.5 | ioreg HIDIdleTime + claude 进程数 | 已决策（§3.2） |
| OQ6 (Drive 占位) | PRD §10.6 | dead_end + unblock 指引；不放假数据 | 已决策（§2.4） |

## §9 Out of Scope (Hard Boundary)

- 不改 `solar-harness mirage exec` 命令签名
- 不改 Obsidian 库结构（仅在 `references/` 新增）
- 不引入新 vendor（不换 MinerU 替代品）
- 不做 Linux/Windows 适配
- 不做 GPU 路径优化（用户机器无 NVIDIA）
- 不做 Drive 全量索引（仅验证可达）

