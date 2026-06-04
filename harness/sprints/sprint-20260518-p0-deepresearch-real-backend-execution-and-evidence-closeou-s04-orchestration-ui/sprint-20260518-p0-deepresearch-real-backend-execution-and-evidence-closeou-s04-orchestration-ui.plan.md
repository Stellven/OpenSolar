# Plan — S04 调度、自动化与可视化

sprint_id: `sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui`
slice: `orchestration-ui`
date: 2026-05-18
upstream: S03 三新模块 + report_metrics 扩展字段; S02 6 个锚点

## 1. 总体策略

把 design.md 的接口契约 ground 到 status-server / tools / core dashboard 边界: 5 个 Codex 文件扩展 + 1 个新测试目录 + 1 个 docs handoff。**严守 §4 写域隔离**: status-server / tools / core/dashboard / core/ui 四个目录互不重叠, 同目录内不同文件可并行。

## 2. 并行 / 串行布局

```
Layer 1 (单节点, 无依赖):
  N1 ui-codebase-recon.md  — dump status-server / tools / core/dashboard / core/ui 当前接口 (read-only)

Layer 2 (并行 3 节点, 依赖 N1):
  N2 research_routes_extend  — payload 加 5 字段 (design §5)
  N3 autopilot_monitor_extend — --epic-status-matrix (design §7)
  N4 runtime_soak_extend     — check_research_footer_fields (design §8)

Layer 3 (并行 3 节点, 依赖 N2):
  N5 research_html_template  — footer + timeline + badge 三段 (design §6)
  N6 livework_panel_js       — fallback color + state animation (design §6)
  N7 dashboard_integration   — server.ts proxy + dashboard.ts widget (design §9)

Layer 4 (单节点, 依赖 N3+N4+N5+N6+N7):
  N8 ui_integration_tests    — 4 测试文件 (design §10)

Layer 5 (并行 2 节点, gate G_S04_ORCHUI_READY, 依赖 N8):
  N9 planning.html  — design + plan + UI 示意 合并渲染
  N10 handoff.md    — 中文证据表 + S05 入参锚点
```

join gate `G_S04_ORCHUI_READY`: N2..N8 全 passed 才允许 N9/N10 收尾。

## 3. 节点验收 Gate (含证据命令)

| Node | 验收 Gate | 证据命令 |
|------|-----------|----------|
| N1 | ui-codebase-recon.md 含 status-server / tools / core/dashboard / core/ui 四组现状表 | `grep -cE 'research_routes\|autopilot-monitor\|runtime-soak\|dashboard' *.ui-codebase-recon.md` >= 4 |
| N2 | build_research_payload 输出含 usage_source/estimated/fallback_reason/state/fallback_level 五新键; 旧字段未删 | `python3 -c "from status_server.research_routes import build_research_payload; print(set(build_research_payload(None,'test').keys()) >= {'usage_source','estimated','fallback_reason','state','fallback_level'})"` 输出 True (mock 路径) |
| N3 | solar-autopilot-monitor.py 新增 `--epic-status-matrix` 子命令; 输出 markdown ≥ 5 列 | `solar-autopilot-monitor --epic-status-matrix --json 2>&1 \| jq '.matrix \| length'` ≥ 1 |
| N4 | solar-runtime-soak.py 新增 `check_research_footer_fields()`; 输出含 4 必查字段 | `python3 -c "from solar_runtime_soak import check_research_footer_fields; r=check_research_footer_fields('test'); print(len({c['field'] for c in r['checks']}))"` ≥ 4 |
| N5 | research.html 末尾含 `S04-FOOTER` / `S04-STATEMACHINE` / `S04-FALLBACK-BADGE` 三 marker | `grep -cE 'S04-FOOTER\|S04-STATEMACHINE\|S04-FALLBACK-BADGE' research.html` == 3 |
| N6 | livework_panel.js 含 fallback color class 与 state transition 函数 | `grep -cE 'badge-fallback-\|state-transition' livework_panel.js` >= 2 |
| N7 | core/dashboard/server.ts 含 `/research/:sid` route; core/ui/dashboard.ts 含 ResearchPanel widget | `grep -c "/research/" server.ts` >= 1 && `grep -c "ResearchPanel\|research-panel" dashboard.ts` >= 1 |
| N8 | 4 个 UI 集成测试通过 | `pytest tests/ui/ -q` 退出 0 |
| N9 | planning.html 存在 size > 4KB; 含 design + plan + UI 示意三段 | `wc -c < *.planning.html` >= 4096 && `grep -c 'research_routes\|UI 示意\|并行' *.planning.html` >= 3 |
| N10 | handoff.md 含 5 个二级段: 证据表/上游 S03 依赖/下游 S05 影响/未闭环项/S05 入参锚点 | `grep -c '^## ' *.handoff.md` >= 5 |

## 4. Write Scope 矩阵 (并行安全)

| Node | Write Scope | Read Scope |
|------|-------------|------------|
| N1 | `sprints/*-s04-orchestration-ui.ui-codebase-recon.md` | `/Users/lisihao/Solar/harness/{status-server,tools}/`, `/Users/lisihao/Solar/core/{dashboard,ui}/` (read-only) |
| N2 | `/Users/lisihao/Solar/harness/status-server/research_routes.py` (扩展函数返回 dict) | S03 report_metrics.py, schema_adapter.py, design §5 |
| N3 | `/Users/lisihao/Solar/harness/tools/solar-autopilot-monitor.py` (新增 subcmd) | sprint status.json schema, design §7 |
| N4 | `/Users/lisihao/Solar/harness/tools/solar-runtime-soak.py` (新增函数) | S02 footer_fields.md, design §8 |
| N5 | `/Users/lisihao/Solar/harness/status-server/templates/research.html` | N2 payload schema, design §6 |
| N6 | `/Users/lisihao/Solar/harness/status-server/static/livework_panel.js` | N2 payload schema, design §6 |
| N7 | `/Users/lisihao/Solar/core/dashboard/server.ts`, `/Users/lisihao/Solar/core/ui/dashboard.ts` | N2 payload schema, design §9 |
| N8 | `/Users/lisihao/Solar/tests/ui/test_research_routes_s03_fields.py`, `..._autopilot_epic_visibility.py`, `..._runtime_soak_footer_check.py`, `..._dashboard_research_render.py` | N2-N7 |
| N9 | `sprints/*-s04-orchestration-ui.planning.html` | design.md, plan.md, N1-N7 产物 |
| N10 | `sprints/*-s04-orchestration-ui.handoff.md` | 全部 |

**冲突检查**:
- N2/N3/N4 写不同 .py 文件 → 并行安全。
- N5/N6/N7 写不同 .html/.js/.ts 文件 → 并行安全。
- N7 在同节点内顺序改 server.ts 然后 dashboard.ts (两 ts 文件强相关, 单节点合写以避免 type 漂移)。
- N8 写 tests/ui/, 与 lib/ 无重叠。

## 5. 模型选择

- N1: `sonnet` (代码踏勘 + 多目录写文档)
- N2: `sonnet` (Python + 与 S03 模块对接)
- N3: `sonnet` (CLI 子命令)
- N4: `sonnet` (Python 文件 IO + glob)
- N5: `sonnet` (Jinja + HTML)
- N6: `sonnet` (JS + DOM 操作)
- N7: `sonnet` (TypeScript, type 严格)
- N8: `sonnet` (pytest + mock 文件 IO/HTTP)
- N9: `sonnet` (HTML 渲染)
- N10: `sonnet` (中文 handoff)

## 6. 代码地形踏勘清单 (N1 builder 必读, read-only)

```bash
ls /Users/lisihao/Solar/harness/status-server/
head -250 /Users/lisihao/Solar/harness/status-server/research_routes.py
grep -nE "def build_research_payload|def generate_markdown_report|def discover_" /Users/lisihao/Solar/harness/status-server/research_routes.py
cat /Users/lisihao/Solar/harness/status-server/templates/research.html
head -80 /Users/lisihao/Solar/harness/status-server/static/livework_panel.js
ls /Users/lisihao/Solar/harness/status-server/routes/
head -60 /Users/lisihao/Solar/harness/status-server/routes/livework_routes.py

head -150 /Users/lisihao/Solar/harness/tools/solar-autopilot-monitor.py
grep -nE "def main|argparse" /Users/lisihao/Solar/harness/tools/solar-autopilot-monitor.py
head -100 /Users/lisihao/Solar/harness/tools/solar-runtime-soak.py
grep -nE "def run|def check_" /Users/lisihao/Solar/harness/tools/solar-runtime-soak.py

ls /Users/lisihao/Solar/core/dashboard/
head -60 /Users/lisihao/Solar/core/dashboard/server.ts
head -60 /Users/lisihao/Solar/core/ui/dashboard.ts
grep -nE "route\|Route\|express\|fastify" /Users/lisihao/Solar/core/dashboard/server.ts

git -C /Users/lisihao/Solar status --short
```

**禁止修改**这些文件 (N1 阶段)。

## 7. HTML 渲染兜底 (N9)

同 S01/S02/S03 plan: pandoc → python markdown → cmark → 最简 `<pre>` 兜底; 若全不可用, 写入 handoff 风险段。

## 8. 失败回退路径

- **N1 现状偏差** (例如 core/dashboard 实际不存在或用 ts/bun 链) → 写入 N1 文档 "现状偏差" 段, 并在 plan §6 标 build 链确认状态。
- **N2 build_research_payload 调用方 break** → 立刻回滚, 改 try/except 软兼容; 写入 handoff CR-01。
- **N3 autopilot --epic-status-matrix 输出格式与 jq 不兼容** → 改 markdown 列表+ JSON 双输出。
- **N7 TypeScript 编译错** → tsc check 先跑, 失败立刻修复; 不允许 silent build error。
- **N8 pytest 失败** → 不允许跳过, 必须修到通过; 失败 > 2 次则触发 ATLAS repair。
- **G_S04_ORCHUI_READY** 阻塞 N9/N10 收尾。

## 9. 完成定义 (DoD)

- 10 节点全 passed。
- `solar-harness graph-scheduler validate` 退出 0; `layers` 输出 ≥ 5 layers; `doctor` 无 critical。
- `pytest tests/ui/` 退出 0 (4 测试文件)。
- `git -C /Users/lisihao/Solar status --short` 仅显示 `harness/status-server/` + `harness/tools/` + `core/dashboard/` + `core/ui/` + `tests/ui/` 变更, 无 `lib/research/` 改动 (S03 边界禁线)。
- handoff.md §3 表所有 grep / pytest / curl 输出真实截断。
- status.json `artifacts` 含 `design / plan / task_graph / planning_html / handoff`。

## 10. 与 S05 的入参锚点

handoff.md §5 必须明确:
- **S05 入参**:
  - `tests/ui/` 全套 pytest 路径
  - `curl http://localhost:<port>/research/<sid>` 响应 schema (含 5 新字段)
  - `solar-runtime-soak --once --check-footer <sid>` 命令 (含 4 footer 字段验证)
  - `solar-autopilot-monitor --epic-status-matrix --json` 命令 (含 epic 可视化)
  - secret-scan 命令 (覆盖 static/ + templates/)
  - 受控 DeepResearch 样例 (max_results ≤ 3) 跑通后 UI 展示验证
