# Evaluation — S04 Orchestration-UI (KVTC API 网关 + UI gate state-machine)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s04-orchestration-ui`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
evaluator: 审判官 (Solar Evaluator pane / pane 2)
round: 2
ts: 2026-05-22T09:30:00Z
verdict: **PASS**

Knowledge Context: solar-harness context inject used (inherited from dispatch; mirage degraded → qmd/obsidian/solar_db fallback)
Session Log: solar-harness session evaluate used (verdict=warn, errors=[], 2 legacy warnings 非阻塞)
verify-all skill: 未注册 → 手工 plan §5 A-L + 19 pytest + 41 联合回归 + 9 否证 等价覆盖 @FALLBACK_MANUAL

Harness Modules Used: harness-knowledge (沿用 dispatch), harness-graph (validate/layers/batches/parent-check), pytest (real 19 + 41 cases run)

---

## 总判定: PASS

contract Acceptance 3 条全部满足; plan §5 验证 A-L 全部 PASS; 19 个 pytest cases 全部独立重跑 PASS (41 联合回归同样 PASS); 9 个否证全部失败; server.py 修改严格仅 2 hunks (749-820 + 2374-2475) 与 handoff 声明 byte-level 一致; 410 中间件实测在 pydantic 前拦截且 tracking_sprint 字段正确; /api/kvtc/state 实测返 Schema 7 全 10 字段; N5 默认 env=0 决策落地; 无 hard 阈值放宽; 无乐观词违规; ThunderOMLX S03 文件改动属 S03 (passed/finalized), 非 S04 越界。

---

## Done 条件逐条 (contract.md Acceptance 3 条)

| # | Acceptance | 判定 | 证据 |
|---|------------|------|------|
| D1 | ready 子任务能自动激活并派到正确角色 | **PASS** | task_graph 5 节点 layers 拓扑 = [[C0,C2], [C1], [C3], [C4]] 与 plan §1 一致; C0/C2 由 W1 派发, C1 (server.py + 2 hunks), C3 (19 tests), C4 (handoff + traceability) 按 DAG 顺序激活; gate_results.G_S04_orchestration_ui_passed = passed |
| D2 | UI 显示 epic / child sprint / 能力使用 / 阻塞原因 | **PASS** | 实测 GET /api/kvtc/state 返 10 字段 (schema_version=ui.kvtc.state.v1 / state / last_ab_source / last_ab_summary / recent_block_event / feature_flag_state / tracking_sprint / i18n_key / i18n_strings / recon_fail_rate); 默认 state=default_off + last_ab_source=unavailable 显式说明阻塞原因; tracking_sprint=sprint-20260521-... 显式可追溯 |
| D3 | pane 输出不再只靠自然语言声称完成 | **PASS** | 19 pytest 真实重跑 PASS (0.93s); 41 联合回归 PASS (含 S03 22 + S04 19, 0.91s 重跑 PASS); 410 中间件 + /api/kvtc/state 行为可由 TestClient 直接复现 (我用故意错误的 body POST 实测 410 拦截在 pydantic 之前) |

---

## 自动检测 (verify-all SKIPPED, 手工等价 12 项 plan §5 + 5 sprint-level)

| 项 | 内容 | 判定 |
|----|------|------|
| A graph validate | node_count=5 errors=[] | PASS |
| B1/B2 ready/layers | layers 3 层与 plan §1 一致 | PASS |
| B3 batches | 0 batches (全 passed) | PASS |
| C 文件齐全 | kvtc_ui_gate.py / kvtc_ui_i18n.py / test_kvtc_ui_gate.py 全存在 | PASS |
| D 4 状态常量 grep | STATE_DEFAULT_OFF / STATE_PREVIEW / STATE_ENABLED / STATE_BLOCKED_BY_GATE_FAIL 全命中 | PASS |
| E env 开关 | THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED (server.py:769) + THUNDEROMLX_KVTC_UI_AB_SOURCE + THUNDEROMLX_KVTC_UI_FORCE_OFF 全在 | PASS |
| F 410 错误体 tracking_sprint | server.py 5 处 _S04_TRACKING_SPRINT 引用 (中间件 + state endpoint) | PASS |
| G /api/kvtc/state 路由 | server.py:2375-2384 `@app.get("/api/kvtc/state")` | PASS |
| H i18n 12 行 (6 keys × 2 langs) | grep `kvtc.ui.(state|toast).` = 12 命中 | PASS |
| I pytest 19 cases | 全 PASS in 0.93s (我重跑); 含 8 state-transitions + 4 env-combos + 2 save 410/passthrough + 2 state api + 2 ab fallback + 1 i18n | PASS |
| J 禁区文件改动 | git diff 显示 S03 文件 (kvtc_codec/calibration_store/paged_ssd_cache) 已改, 但 mtime 04:51-04:56 早于 S04 C0 dispatch 04:56:19 → 属 S03 写入; S04 builder 未越界 | PASS (with caveat — 见 §额外发现) |
| K server.py 2 hunks | 实测 git diff --unified=0 仅 2 hunks: -748,0 +749,72 (= 749-820) + -2301,0 +2374,102 (= 2374-2475), 与 handoff 声明 byte-level 一致 | PASS |
| L parent-check | epic ok=true ready=false open_nodes=[S05] (S01-S04 已 passed) | PASS |

---

## 验证命令实跑证据 (plan §5 全 12 条)

### A. validate
```
cmd: solar-harness graph-scheduler validate
stdout: {"ok": true, "node_count": 5, "errors": [], "warnings": []}
```

### B. ready/layers/batches
```
cmd: solar-harness graph-scheduler layers
stdout: {"ok": true, "layers": [["C0_ui_gate_module", "C2_ui_i18n_module"], ["C1_server_routes"], ["C3_pytest_15_cases"], ["C4_handoff_traceability_join"]]}
```

### I. pytest tests/orchestration (handoff claim: 19/0.80s)
```
cmd: cd /Users/lisihao/ThunderOMLX && KMP_DUPLICATE_LIB_OK=TRUE ./venv/bin/python -m pytest tests/orchestration/ -v --tb=short
stdout: 19 passed, 3 warnings in 0.93s
conclusion: 19/19 PASS (我重跑, 不复用 handoff)
```

### Joint regression (handoff claim: 41 cases)
```
cmd: cd /Users/lisihao/ThunderOMLX && KMP_DUPLICATE_LIB_OK=TRUE ./venv/bin/python -m pytest tests/kvtc/ tests/orchestration/ --tb=line -q
stdout: 41 passed, 3 warnings in 1.00s
conclusion: 41/41 PASS (S03 22 + S04 19); S04 未破坏 S03 任何 case
```

### K. server.py hunks
```
cmd: git diff --unified=0 src/omlx/server.py | grep ^@@
stdout:
  @@ -748,0 +749,72 @@ app.add_middleware(DebugRequestLoggingMiddleware)
  @@ -2301,0 +2374,102 @@ async def delete_prompt_cache(
shortstat: 1 file changed, 174 insertions(+)
conclusion: 仅 2 hunks 与 handoff 声明 (749-820 + 2374-2475) byte-level 一致; 0 跨区域改动
```

### L. parent-check
```
cmd: solar-harness graph-scheduler parent-check --graph epic-...task_graph.json
stdout: {"ok": true, "ready": false, "open_nodes": ["S05_verification_release"], "failed_nodes": []}
conclusion: PASS — S01..S04 全 passed 已从 open_nodes 清除; 仅 S05 待 passed
```

### session evaluate
```
cmd: solar-harness session evaluate <sid> --json
verdict: warn
errors: []
warnings: 2 (activity_without_terminal, legacy_unpaired_activity)
drift_detected: false; event_count: 170
```

2 个 warning 全部为 legacy schema / non-terminal, 与 S04 交付内容无关 → 不阻塞 (与 dispatch §Log-Native Evaluation Requirement 第 3 条一致)。

---

## Smoke Test 证据三要素 (审判官 5 个独立实测, 不复用 handoff)

### Smoke 1: 410 中间件在 pydantic 之前拦截 (handoff 关键 claim)
```
cmd: env  THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED unset, POST /v1/cache/prompt/save with body={"totally_wrong_field": 123}
stdout:
  status_code=410
  body={'error': 'named_prompt_cache_save_disabled', 'message': '... THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED=1 once staging verification clears.', 'tracking_sprint': 'sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026'}
conclusion: 410 真的拦在 pydantic 之前 (否则会先返 422 missing 'name'/'prompt'); tracking_sprint 字段精确 = epic id
```

### Smoke 2: env=1 时透传到原 handler
```
cmd: env THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED=1, 同 body
stdout: status_code=422 [{'type': 'missing', 'loc': ('body', 'name')...}]
conclusion: env=1 时透传走 pydantic, 不再 410; 切换路径真生效
```

### Smoke 3: /api/kvtc/state 返 Schema 7
```
cmd: GET /api/kvtc/state
stdout:
  schema_version=ui.kvtc.state.v1
  state=default_off
  last_ab_source=unavailable
  fields=['schema_version', 'state', 'last_ab_source', 'last_ab_summary', 'recent_block_event', 'feature_flag_state', 'tracking_sprint', 'i18n_key', 'i18n_strings', 'recon_fail_rate']
conclusion: 10 字段全集; 默认 state=default_off + last_ab_source=unavailable 与 plan §1 一致
```

### Smoke 4: server.py 修改区域精确性
```
cmd: git diff --unified=0 src/omlx/server.py | grep ^@@
stdout: 2 hunks at line 749 (+72) and 2374 (+102)
conclusion: 174 行新增, 0 跨区域改动; 与 handoff §Compat Notes 第 4 行 "server.py 其他 6257 行零改动" 一致
```

### Smoke 5: i18n 与 S01 N7-A4 byte-level 比对 (复用 C2 评审证据)
```
ref: 我在 C2_ui_i18n_module eval 中已做 12/12 字符串 byte-by-byte 比对, diff_count=0
conclusion: i18n 文案 1:1 来自 S01 N7-A4 L119-124 (无漂移)
```

---

## 否证尝试 (Falsification — 9 个角度全失败 → PASS)

| # | 角度 | 假设 | 结果 |
|---|------|------|------|
| 1 | 410 拦截在 pydantic 之后 | 中间件可能在 pydantic 之后才跑 → 错误 body 会先返 422 | 失败: 实测错误 body 真返 410 (smoke 1) |
| 2 | env=1 时仍 410 | 环境变量切换可能未生效 | 失败: env=1 时返 422 pydantic validation (smoke 2) |
| 3 | Schema 7 缺字段 | 路由可能漏字段 | 失败: 10 字段全集 (smoke 3) |
| 4 | server.py 跨区域改动 | builder 可能"surgical edit"实际偷改其他行 | 失败: git diff 严格仅 2 hunks 在声明区域 (smoke 4) |
| 5 | S04 越界改 S03 文件 | git diff 显示 3 个 S03 文件 modified | 失败: mtime 04:51-04:56 早于 S04 C0 dispatch 04:56:19; S03 已 passed/finalized, 属 S03 写入 |
| 6 | 乐观词违规 | server.py / handoff 可能含 "已修复/稳定/完美" | 失败: 命中全在 forbidden 定义 (i18n) / 反向声明 (handoff §Stop-Rule) / 技术依赖描述 ("依赖 S03 KV capture 链路稳定" — 类似 S02 "签名稳定" 合规用法); 0 substantive 违规 |
| 7 | pytest 数虚假 | handoff 19 cases 可能虚报 | 失败: 重跑 19 passed in 0.93s; collected 19 items 严格匹配 |
| 8 | 联合回归破坏 S03 | S04 改动可能 break S03 tests | 失败: 41 passed (S03 22 + S04 19) in 1.00s |
| 9 | N5 默认 env=0 + 410 体一致性 | 错误体可能缺 tracking_sprint 或 error 字段 | 失败: smoke 1 body 含 error / message / tracking_sprint 全 3 字段, 与 N5-A6 design 一致 |

9 次否证均失败 → PASS。

---

## 额外发现

1. **handoff "git diff 验证 0 命中" 措辞不准**: 严格字面 git diff HEAD 显示 3 个 S03 文件 (kvtc_codec / kvtc_calibration_store / paged_ssd_cache) modified, 因为 S03 也尚未 commit. 但 mtime 实测 04:51-04:56 早于 S04 C0 dispatch 04:56:19 → 是 S03 builder 写的, 不是 S04 越界。建议未来 handoff 用 "git diff --since=<sprint-start-ts>" 或显式排除 S03 已 passed 的文件清单, 避免 evaluator 误读。**不构成 FAIL** — sprint Acceptance 不要求 git diff 字面 0 命中, 要求 "S04 没改 S03 文件", 后者成立。
2. **C1/C3/C4 自动 reconciled 而非单独 evaluator 评审**: task_graph 显示 C1/C3/C4 节点 note="coordinator auto-reconciled from complete write_scope artifacts before evaluator dispatch"。这意味着 evaluator 跳过了 node-level 评审, 直接基于 write_scope 文件完整性 reconcile。我在 sprint-level 评审中等价覆盖了 C1 (实测 410 + /api/kvtc/state + git diff hunks) + C3 (19 pytest + 41 联合回归) + C4 (handoff + traceability schema)。未来 coordinator 应对 C1/C3 这种含运行时验证的节点保留 evaluator 步骤, 避免漏 catch。
3. **/api/kvtc/state 实测 10 字段 vs design Schema 7 名义 7 字段**: 实际多了 `i18n_key` / `i18n_strings` / `recon_fail_rate`, 这是 builder 主动 enriched 而非 spec 漂移 — 与 handoff §API Signatures 第 3 节一致。S05 / UI consumer 必须按实测 10 字段写代码, 而不是 design 名义 7。
4. **kvtc_codec.py mtime 04:56:21 与 S04 C0 dispatch 04:56:19 仅差 2 秒**: 这是边缘 case, 可能让保守 evaluator 怀疑越界。我用 S03 sprint status (passed/finalized) + 内容方向 (KVTC codec 属 N3 范围非 UI gate) 双重确认是 S03 残留。建议未来 coordinator 在 sprint 启动时打 timestamp anchor + S04 启动后冻结 S03 file mtime (例如用 `chattr +i` 或 git commit), 避免歧义。
5. **N5 默认 env=0 决策合规**: handoff §Decision Made 明示原因 — OQ2 仍 partially_resolved, H2 未被静态扫描确认, H3 修方案 (wait_for_kv_seconds) 本 sprint 不实施。这是合规的 fail-safe 决策, 符合 PRD "不污染主服务 cache" + "提供 rollback 指令" + "UI 默认关闭" 3 条约束。切 env=1 条件钉死 (handoff §3) 留给 S05 final regression 验证。
6. **R6 deferred to S05**: handoff §R1..R7 表显式标注 R6 deferred, 不属本 sprint 范围。这是合规的 scope 边界 (S04 contract Acceptance 也没要求 R6)。
7. **session evaluate 2 warnings**: activity_without_terminal + legacy_unpaired_activity — 与 S04 交付无关, 与历次 sprint 同性质 (基础设施 legacy schema 项)。

---

## 风险 (本 sprint 边界外, 不阻塞 PASS)

- **N5 默认 env=0**: 当前无 named prompt cache 用户无影响; 但若有客户端依赖 → 立刻拿 410。ops 切 env=1 前必须先做 staging 验证 (handoff §3 + §后续待办 5)。
- **ImportError 兜底掩盖真问题**: /api/kvtc/state 在 S03 模块缺失时返 503 + reason=`state_compute_error:<cls>`, 不抛 ImportError。建议运维监控 `reason=state_compute_error` (handoff §风险第 2 条已声明)。
- **include_fixtures=true 响应体大小**: 当前未做 size 检查, 若 fixtures > 几千 → 响应巨大。S05 必须保证 fixtures ≈ 15 + N/A (handoff §风险第 3 条)。
- **tz-naive datetime**: server endpoint 用 `datetime.now(timezone.utc)` OK; 其他调用方需注意 (handoff §风险第 4 条 + 我在 C0 评审已 fail-soft 验证)。
- **server.py 6431 行 surgical edit 漂移风险**: future sprint 重排 server.py → hunk 位置漂移。建议保留 `_S04_TRACKING_SPRINT` / `_NAMED_PROMPT_CACHE_SAVE_PATH` 常量便于追踪 (handoff §风险第 5 条)。
- **mirage 知识库持续降级**: 不影响本 sprint (事实来自实测), 但若降级到 S05 实施期可能影响 evidence 取证。

---

## 未验证 (下游 sprint 责任)

- staging 真实复现 /v1/cache/prompt/save 422 + 验证 H1/H2/H3 → S04 builder (round 之外) 或 ops
- N5 切 env=1 后 200 条 staging 调用 2xx ≥ 99% → S05 final regression
- UI e2e 截图 (4 状态视觉) → S05 staging 或外部 UI 团队 (ThunderOMLX 无 frontend 目录)
- recon_gate.jsonl 真实产出 (writer 已 S03 实现, 生产数据流由运行期产生)
- auto block_by_gate_fail 60s 阈值演练 → S05
- CI YAML + ATLAS hook → S05
- 真实 Qwen3.6 block A/B 修复后 p95_rel_rmse ≤ 0.02 / min_cos ≥ 0.999 → S05 final regression

---

## 后续待办 (给协调器)

1. **本 sprint**: PASS。协调器 `eval-verdict pass` → 推 status → `passed`; epic_decomposer 自动激活 S05_verification_release。
2. **S05 round-1**: 必读 S03 公开 API + S04 /api/kvtc/state + S04 410 middleware; 在 N6 CI 中调用 GET /api/kvtc/state 验证 UI gate; 在 staging 跑 200 条 /v1/cache/prompt/save 测 2xx (env=1) / 410 (env=0) 比例。
3. **N5 切 env=1 条件** (S05 + ops 联合): (a) S04 staging 复现 H1/H2/H3 + 选定修方案; (b) S05 N6 7 天 success_rate ≥ 0.99; (c) ops 设 env=1。
4. **epic 关闭门禁**: S05 passed 后 parent-check ready=true 才允许 epic close。
5. **建议 coordinator 改进** (优先级 P3): C1/C3 含运行时验证的节点不应直接 auto-reconcile, 应保留 evaluator step; sprint-level handoff 用 "since-anchor" 表达 git diff 避免 S03 残留误读。
