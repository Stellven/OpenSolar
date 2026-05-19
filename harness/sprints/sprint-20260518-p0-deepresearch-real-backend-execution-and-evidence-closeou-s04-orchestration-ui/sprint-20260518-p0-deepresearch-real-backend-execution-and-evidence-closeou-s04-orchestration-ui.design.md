# Design — S04 调度、自动化与可视化

epic_id: `epic-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou`
sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui`
slice: `orchestration-ui`
author: planner (solar-harness)
date: 2026-05-18
upstream: S03 三新模块 (fallback_policy / state_machine / schema_adapter) + report_metrics 扩展; S02 6 个 schema/状态机/降级锚点

## 1. 切片定位

S03 把契约 ground 到 `lib/research/` Python 模块。**S04 把这些模块接入 orchestration + UI + 运行时证据**：让 status-server 读 `usage_source` / `estimated` / `fallback_reason` 三字段, autopilot 显示 epic child sprint 状态, runtime-soak 把 footer 4 字段拉到面板, pane 输出不再靠自然语言声称完成。**不动 `lib/research/`** (那是 S03 边界), **不动 `coordinator.sh / wake / dispatch`** (控制面只读)。

## 2. UI 现状对账 (S04-RECON 锚点核验)

| 模块 | 现状 | S04 动作 |
|------|------|----------|
| `harness/status-server/research_routes.py` | 已存在: `build_research_payload`, `discover_eval_files`, `generate_markdown_report`, `discover_quality_gates`, `discover_human_search_waiting`; 当前 payload 含 source_count / evidence_count / claim_count / unsupported_rate / citation_accuracy | **扩展**: payload 新增 `usage_source` / `estimated` / `fallback_reason` / `state` / `fallback_level` 五字段 (读 S03 report_metrics + schema_adapter) |
| `harness/status-server/templates/research.html` | 已存在 | **扩展**: 加 footer 4 字段渲染 + state machine timeline + fallback level badge |
| `harness/status-server/static/livework_panel.js` | 已存在 | **扩展**: 加 fallback color coding (L1 绿 / L2 黄 / L3 橙 / L4 红) + state transition 动画 |
| `harness/status-server/routes/livework_routes.py` | 已存在 livework 路由 | **不动** (S04 不引入新 route) |
| `harness/tools/solar-autopilot-monitor.py` | 已存在: pane lease / autopilot queue / KB probe / sprint status 检测 | **扩展**: epic child sprint state matrix 显示 + capability_inference 注入证据可视化 |
| `harness/tools/solar-runtime-soak.py` | 已存在: runtime audit-writes / doctor / autopilot monitor / survey response watcher | **扩展**: 加 `check_research_footer_fields()` 把 S03 footer 4 字段拉到面板 |
| `core/dashboard/server.ts` | 已存在 dashboard backend | **扩展**: 注册 `/research/<sid>` proxy 接 status-server, push 新字段到 UI |
| `core/ui/dashboard.ts` | 已存在 dashboard 前端 | **扩展**: 显示 epic / child sprint / capability / 阻塞原因 (S04 PRD acceptance #2) |

**不破坏原则**：所有改动只 (a) 扩展 payload 字段, (b) 新增模板片段, (c) 新增 dashboard widget; 禁止改 status-server 现有函数签名或既有路由 URL。

## 3. 新增 / 扩展模块（S04 owns）

```
harness/status-server/
├── research_routes.py             (扩展, build_research_payload 加 5 字段)
├── templates/research.html        (扩展, footer + timeline + badge)
└── static/livework_panel.js       (扩展, fallback color + state animation)

harness/tools/
├── solar-autopilot-monitor.py     (扩展, epic child state matrix)
└── solar-runtime-soak.py          (扩展, check_research_footer_fields)

core/dashboard/
└── server.ts                      (扩展, /research proxy)

core/ui/
└── dashboard.ts                   (扩展, epic + child + capability widget)
```

`tests/ui/` 新增:
```
tests/ui/
├── test_research_routes_s03_fields.py   (NEW) — payload 含 5 新字段
├── test_autopilot_epic_visibility.py    (NEW) — autopilot 显示 child sprint state
├── test_runtime_soak_footer_check.py    (NEW) — soak 输出含 4 footer 字段
└── test_dashboard_research_render.py    (NEW) — dashboard 渲染 fallback badge
```

## 4. 数据流 (S03 → S04)

```
S03 lib/research/
  ├── report_metrics.py  (写 usage_source/estimated/fallback_reason/state)
  ├── schema_adapter.py  (校验 + 双向映射)
  ├── state_machine.py   (8 状态枚举)
  └── fallback_policy.py (4 级枚举)
            │
            ▼ (research_execution_metrics.json + model_usage.jsonl)
S04 status-server/research_routes.py
  └── build_research_payload(sid) -> {
        ...source_count, evidence_count, etc.,
        usage_source, estimated, fallback_reason,
        state, fallback_level
      }
            │
            ▼ (JSON HTTP)
S04 core/dashboard/server.ts -> core/ui/dashboard.ts (UI 渲染)
```

## 5. research_routes.py 扩展接口

```python
def build_research_payload(sprints_dir, sid) -> dict:
    payload = _existing_payload(sprints_dir, sid)  # 原逻辑
    # S04 新增 (读 S03 输出)
    metrics_path = SPRINTS_DIR / f"{sid}.research_execution_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text())
        payload["usage_source"] = metrics.get("usage_source")
        payload["estimated"] = metrics.get("estimated", False)
        payload["fallback_reason"] = metrics.get("fallback_reason")
        payload["state"] = metrics.get("state", "unknown")
        payload["fallback_level"] = _derive_fallback_level(metrics)
    return payload

def _derive_fallback_level(metrics: dict) -> str:
    """从 usage_source + estimated + fallback_reason 反推 L1-L4"""
    # 落到 S02-FALLBACK fallback-policy.json 的 levels 表
```

要求: 现有 `build_research_payload` 调用方一行不动; 新字段在 metrics 文件缺失时填 `None` / `"unknown"`, 不抛错。

## 6. research.html 模板扩展

在现有 `research.html` 末尾追加 footer + state machine + fallback badge 三段:

```html
<!-- S04-FOOTER -->
<section class="research-footer">
  <h3>Execution Metrics</h3>
  <ul>
    <li>Document word count: {{ payload.word_count }}</li>
    <li>Total token consumption: {{ payload.total_tokens }}</li>
    <li>Token usage source: {{ payload.usage_source }}</li>
    <li>Token usage estimated: {{ payload.estimated }}</li>
  </ul>
</section>

<!-- S04-STATEMACHINE -->
<section class="state-timeline">
  <span class="state state-{{ payload.state }}">{{ payload.state }}</span>
</section>

<!-- S04-FALLBACK-BADGE -->
<span class="badge badge-fallback-{{ payload.fallback_level }}">{{ payload.fallback_level }}</span>
```

要求: 4 footer 字段必精确文本 (S05 Evaluator 会 `grep` 验证)。

## 7. solar-autopilot-monitor.py 扩展

新增 `--epic-status-matrix` 子命令, 输出 markdown 表显示 epic 下所有 child sprint 的:
- sprint_id, status, phase, handoff_to, 阻塞原因, 关联 capability
- 数据源: `~/.solar/harness/sprints/*.status.json`

要求 (S04 PRD acceptance #2 "UI 显示 epic、child sprint、能力使用和阻塞原因"):
- 每行至少包含 5 列
- 阻塞原因从 `history[-1].blocked_by` 提取
- 关联 capability 从 `task_graph.json` 的 `required_capabilities` 提取

## 8. solar-runtime-soak.py 扩展

新增 `check_research_footer_fields(sid) -> dict` 函数:

```python
def check_research_footer_fields(sid: str) -> dict:
    final_md_paths = list(SPRINTS.glob(f"{sid}*final.md"))
    results = {"sid": sid, "checks": []}
    required = ["Document word count", "Total token consumption", 
                "Token usage source", "Token usage estimated"]
    for path in final_md_paths:
        content = path.read_text()
        for field in required:
            results["checks"].append({
                "file": str(path),
                "field": field,
                "present": field in content,
            })
    return results
```

集成到 `solar-runtime-soak.py` 主循环, 失败时 enqueue autopilot remediation。

## 9. core/dashboard 集成

`core/dashboard/server.ts` 新增 endpoint `/research/:sid` proxy 到 `http://localhost:<status-server-port>/research/<sid>`, response 透传给 `core/ui/dashboard.ts`。

`core/ui/dashboard.ts` 在 layout 中加新 widget `<ResearchPanel sid={...} />`, 显示:
- footer 4 字段
- state badge
- fallback level color bar

## 10. 单测覆盖矩阵 (S04 DoD)

| 测试 | 目标 | 输入 fixture |
|------|------|--------------|
| test_research_routes_s03_fields | build_research_payload 返回含 5 新字段 | mock research_execution_metrics.json |
| test_autopilot_epic_visibility | --epic-status-matrix 输出 markdown 表 | mock 3 个 sprint status.json |
| test_runtime_soak_footer_check | check_research_footer_fields 命中 4 字段 | mock final.md 含/缺 footer |
| test_dashboard_research_render | dashboard 渲染 fallback badge | mock payload + DOM snapshot |

**禁止**: 测试不允许 mock 整个 `research_routes.py`; 只允许 mock 文件 IO + HTTP。

## 11. 控制面接入 (不破坏 wake/dispatch/status)

- S04 不动 `solar-harness wake` / `coordinator.sh` / `autopilot 主循环`。
- 仅扩展 `harness/status-server/` + `harness/tools/` + `core/dashboard/` + `core/ui/`。
- runtime-soak 失败 enqueue 走现有 autopilot queue API, 不绕过。

## 12. 失败恢复 (运行时层面)

| 故障 | 检测 | 恢复 |
|------|------|------|
| research_execution_metrics.json 缺失 | payload 字段为 None | UI 显示 "unknown" / "—", 不报错 |
| status-server 进程崩溃 | dashboard proxy 503 | UI 显示 "status-server unavailable", 自动重试 |
| autopilot --epic-status-matrix 输出空 | parsed count == 0 | 写入 runtime-soak report, enqueue remediation |
| dashboard widget JS error | console.error | 显示 fallback placeholder, 不阻塞其余 UI |

## 13. 给下游 sprint 的入参

### S05 verification-release 入参
- 跑 `pytest tests/ui/` 全套
- 跑 curl 验证 `/research/<sid>` payload schema
- 跑 `solar-runtime-soak --once --check-footer <sid>` 验证 footer 4 字段
- 跑 `solar-autopilot-monitor --epic-status-matrix --json` 验证 epic 可视化输出
- secret-scan: dashboard / status-server 静态资产不得含 OAuth token / Serper key

## 14. 风险

| 风险 | 缓解 |
|------|------|
| S03 输出文件命名漂移 (research_execution_metrics.json vs survey_execution_metrics.json) | research_routes.py 用 glob `*execution_metrics*.json` 双兼容 |
| dashboard 静态资源缓存导致新 widget 不显示 | static 文件加版本 hash 后缀, server.ts 自动 bust |
| status-server 进程未启动 | runtime-soak 检测进程存活, 缺则 enqueue start command |
| 4 footer 字段位置在 final.md 末尾, 报告长时 grep 慢 | 用 `tail -50 final.md` 限定窗口 |
| epic-status-matrix 输出包含多 epic 时混淆 | 按 epic_id 分组 + 标题; CLI 加 `--epic <id>` 过滤 |

## 15. 上游依赖 / 下游影响 / 未闭环项

- **上游**: S03 三新模块 + report_metrics 扩展字段 (`usage_source` / `estimated` / `fallback_reason`) + final.md footer 4 字段。
- **下游**: S05 跑 UI/curl/soak/autopilot 4 类集成验证 + secret-scan + 受控样例。
- **未闭环**:
  1. S03 真实 `research_execution_metrics.json` 在 S04 编码时未必产出 — 本切片用 fixture mock, S05 用真实样例。
  2. dashboard server.ts/dashboard.ts 用 TypeScript, build 链路 (tsc/bun) 需在 plan §6 踏勘清单中确认。
  3. pane runtime evidence (PRD acceptance #3 "pane 输出不再只靠自然语言声称完成") — S04 通过 runtime-soak 把 footer 4 字段拉到面板, 但是否再加 tmux pane label 显示由 S05 验证后回写决策。
