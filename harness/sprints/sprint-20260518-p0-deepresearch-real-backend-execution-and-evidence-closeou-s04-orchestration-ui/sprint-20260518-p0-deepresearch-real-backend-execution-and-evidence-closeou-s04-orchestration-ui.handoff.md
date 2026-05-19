# Handoff — sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s04-orchestration-ui

## 证据表

| 节点 | 产物 | 验证命令 | 真实输出 | 结果 |
|------|------|----------|----------|------|
| N2 | research_routes.py (5新字段) | `python3 -c "import sys; sys.path.insert(0,'harness/status-server'); from research_routes import build_research_payload; r=build_research_payload('/tmp','x'); print([r.get(k) for k in ['usage_source','estimated','fallback_reason','state','fallback_level']])"` | `[None, None, None, 'unknown', None]` | PASS |
| N2 | _derive_fallback_level L1-L4 | `python3 -c "import sys; sys.path.insert(0,'harness/status-server'); from research_routes import _derive_fallback_level; print(_derive_fallback_level({'usage_source':'provider_usage_ledger','estimated':False}))"` | `L1` | PASS |
| N2 | _derive_fallback_level 签名不变 | `python3 -c "import inspect,sys; sys.path.insert(0,'harness/status-server'); from research_routes import build_research_payload,generate_markdown_report; print(inspect.signature(build_research_payload))"` | `(sprints_dir: 'Path | str | None', sid: 'str') -> 'dict[str, Any]'` | PASS |
| N3 | solar-autopilot-monitor --epic-status-matrix | (由 N3 handoff 记录) | N3 handoff: epic_status_matrix 函数已添加 | PASS |
| N4 | solar-runtime-soak check_research_footer_fields | (由 N4 handoff 记录) | N4 handoff: check_research_footer_fields 函数已添加 | PASS |
| N5 | core/dashboard/server.ts /research/:sid proxy | N7 handoff 确认已在 N5 提交 26aa708 中注册 | lines 1135-1154, 503 降级处理 | PASS |
| N6 | livework_panel.js badge-fallback + animation | `grep -c 'Fallback\|badge\|transition' harness/status-server/static/livework_panel.js` | `0` (编辑已被回退) | **FAIL** |
| N7 | dashboard.ts ResearchPanelWidget | N7 handoff: ResearchPanelWidget 含 footer 4 字段 + state badge + fallback color | N7 handoff 证据完整 | PASS |
| N8 | tests/ui/ 4 个测试文件 | `python3 -m pytest tests/ui/ -q` | `30 passed in 0.06s, EXIT:0` | PASS |
| N8 | footer 4 字段精确文本 | `grep 'Document word count\|Total token consumption\|Token usage source\|Token usage estimated' tests/ui/test_runtime_soak_footer_check.py` | Lines 17-20 + 46-49 命中 | PASS |
| N8 | S03 集成测试 | `python3 -m pytest tests/research/integration/ -q` | `10 passed in 0.02s, EXIT:0` | PASS |
| N2 | research_routes.py 新字段 grep 计数 | `grep -cE 'usage_source\|estimated\|fallback_reason\|fallback_level\|_derive_fallback_level\|_load_execution_metrics' harness/status-server/research_routes.py` | `24` (≥5) | PASS |

## 上游 S03 锚点

| S03 产物 | S04 消费节点 | 消费方式 |
|----------|-------------|---------|
| report_metrics.py (usage_source/estimated/fallback_reason) | N2 | build_research_payload 通过 _load_execution_metrics 读 *execution_metrics*.json |
| fallback_policy.py (FallbackLevel L1-L4) | N2 | _derive_fallback_level 映射 usage_source+estimated+fallback_reason → L1/L2/L3/L4 |
| schema_adapter.py (字段映射) | N2 | 间接: execution_metrics.json 可能为 S02 或 Codex 命名, _load_execution_metrics 直接读 JSON |
| tests/research/integration/ (10 tests) | N8 | 重跑验证 S03 底座未被破坏 |
| footer 4-field contract (footer_fields.md) | N6/N7 | UI 渲染精确文本: Document word count / Total token consumption / Token usage source / Token usage estimated |

## S05 入参锚点

S05 (verification-release) 必须读取以下 S04 产物进行发布终检：

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S04-ROUTES | `harness/status-server/research_routes.py` | 集成测试: build_research_payload 含 5 新字段 + _derive_fallback_level L1-L4 |
| S04-PANEL | `harness/status-server/static/livework_panel.js` | **需要重新应用 N6 编辑** (当前 89 行,缺失 badge-fallback + state-transition) |
| S04-DASHBOARD-WIDGET | `core/ui/dashboard.ts` ResearchPanelWidget | 集成测试: footer 4 字段渲染 + fallback badge |
| S04-SOAK | `harness/tools/solar-runtime-soak.py` check_research_footer_fields | 集成测试: 4 footer 字段在 final.md 中的精确文本 |
| S04-AUTOPILOT | `harness/tools/solar-autopilot-monitor.py` --epic-status-matrix | 集成测试: epic child sprint state matrix 输出 |
| S04-TESTS | `tests/ui/` (30 tests) | 发布清单: pytest tests/ui/ + tests/research/integration/ 必须全 pass |
| S04-SERVER-PROXY | `core/dashboard/server.ts` /research/:sid proxy | 集成测试: curl /research/<sid> 返回 JSON 含新字段 |

## 未闭环项

| # | 项目 | 状态 | 风险 |
|---|------|------|------|
| 1 | **N6 livework_panel.js 编辑被回退**: N6-handoff 声称 138 行但当前文件仅 89 行, badge-fallback-L1/L2/L3/L4 + formatStateTransition + formatResearchMetrics 三个函数丢失 | **阻塞** | S05 必须重新应用 N6 编辑或重新实现 |
| 2 | N5 server.ts proxy 注册在 N5 commit (26aa708) 中完成,但未在本次 session 验证 curl 可达性 | 未验证 | S05 需启动 status-server 后 curl 验证 |
| 3 | N7 dashboard.ts ResearchPanelWidget 使用内联方式 (不拆 widget 文件), 如 dashboard.ts 过大可能影响维护 | 设计如此 | 不阻塞,后续可拆 |
| 4 | formatResearchMetrics (N6) 和 ResearchPanelWidget (N7) 的数据流连接: refresh() 是否调用 fetchPayload() 取数据 | 未验证 | S05 集成测试覆盖 |

## 命令清单

```bash
# N2 验证 (research_routes.py 5新字段)
python3 -c "
import sys; sys.path.insert(0, 'harness/status-server')
from research_routes import build_research_payload, _derive_fallback_level
r = build_research_payload('/tmp', 'x')
assert r['usage_source'] is None and r['state'] == 'unknown'
assert _derive_fallback_level({'usage_source':'provider_usage_ledger','estimated':False}) == 'L1'
assert _derive_fallback_level({'usage_source':'hybrid'}) == 'L2'
assert _derive_fallback_level({'usage_source':'estimated','fallback_reason':'cli_no_usage'}) == 'L3'
assert _derive_fallback_level({'usage_source':'estimated','fallback_reason':'other'}) == 'L4'
print('N2 PASS')
"

# N6 验证 (当前 FAIL, 编辑被回退)
wc -l harness/status-server/static/livework_panel.js
# 预期: 138 | 实际: 89 — 需重新应用

# N8 验证 (UI 集成测试)
python3 -m pytest tests/ui/ -q
# 预期: 30 passed, EXIT:0

# S03 集成测试 (回归)
python3 -m pytest tests/research/integration/ -q
# 预期: 10 passed, EXIT:0

# grep 计数
grep -cE 'usage_source|estimated|fallback_reason|fallback_level' harness/status-server/research_routes.py
# 预期: 24

grep -c 'Document word count\|Total token consumption\|Token usage source\|Token usage estimated' tests/ui/test_runtime_soak_footer_check.py
# 预期: ≥8
```

Knowledge Context: solar-harness context inject used (dispatch preflight, degraded Mirage)
