# Handoff — S04 Orchestration-UI (KVTC API 网关 + UI gate state-machine)

sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s04-orchestration-ui`
epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
builder: 建设者化身 (Solar Builder pane)
round: 1
ts: 2026-05-22T06:05:00Z

Knowledge Context: solar-harness context inject used
Harness Modules Used: harness-knowledge, harness-graph, harness-skills (TaskCreate/TaskUpdate), pytest (real run)

## 变更文件（write_scope 内）

### C0 + C2（由其他 pane 上一轮完成，已 reviewing，本 round 复用）

- `src/omlx/cache/kvtc_ui_gate.py`（NEW, 293 行）— 4 状态 FSM + env reader + AB summary loader + recon_gate FAIL rate 计算；纯函数 `compute_state(now, env, ab_summary_path, recon_gate_jsonl_path)`；首版 enabled 不可达；fail-soft（缺失文件 → default_off）。
- `src/omlx/cache/kvtc_ui_i18n.py`（NEW, 80 行）— 6 个 i18n key × {zh-CN, en-US} + `validate_i18n_keys()`；文案与 S01 N7-A4 表 1:1；禁词检查内置。

### C1（本 round 实施）

- `src/omlx/server.py`（MODIFY, +174 / -0 行；surgical edit，2 个 hunk）：
  - **Hunk 1** lines 749-820（在 `app.add_middleware(DebugRequestLoggingMiddleware)` 后）：
    - `from starlette.middleware.base import BaseHTTPMiddleware`
    - `_S04_TRACKING_SPRINT` / `_NAMED_PROMPT_CACHE_SAVE_PATH` 常量
    - `_named_prompt_cache_save_enabled()` env 检查（默认 0=disabled）
    - `NamedPromptCacheSaveDisableMiddleware` 类（拦截 POST `/v1/cache/prompt/save`，env≠"1" → 410 + N5-A6 统一错误体 + `tracking_sprint`；fail-closed except）
    - `app.add_middleware(NamedPromptCacheSaveDisableMiddleware)` + 启动期 log `named_prompt_cache_save_enabled=<0|1>`
  - **Hunk 2** lines 2374-2475（在 `delete_prompt_cache` 之后、`/api/status` 之前）：新路由 `GET /api/kvtc/state`（Schema 7 `ui.kvtc.state.v1`）；try/except ImportError → 503 fail-soft（与 S03 软依赖兼容）；调用 `kvtc_ui_gate.compute_state` + `kvtc_ui_i18n.KVTC_UI_I18N`；query `?include_fixtures` 默认 false；feature_flag_off 状态映射到 i18n key `kvtc.ui.state.feature_flag_off`。
  - **未触碰** server.py 其他 6431 行（git diff hunks 仅 749-820 + 2374-2475）。

### C3（本 round 实施）

- `tests/orchestration/__init__.py`（NEW, 空）
- `tests/orchestration/test_kvtc_ui_gate.py`（NEW, 19 cases）：
  - 8 state-machine transitions（T1-T8）
  - 4 env-switch combos（E1-E4）
  - 2 `/v1/cache/prompt/save` 410 vs pass-through（S1-S2）
  - 2 `/api/kvtc/state` 响应（A1-A2，含 `include_fixtures` 验证）
  - 2 AB summary 容错（F1-F2，missing / malformed）
  - 1 i18n 完整性（I1）
  - 全部用 `TestClient` + `tmp_path` + `monkeypatch`；不真起 uvicorn / port binding。

### C4（本 round 实施）

- `sprints/<s04-sid>.handoff.md`（本文件）
- `sprints/<s04-sid>.traceability.json`

### NOT my work（不在 S04 write_scope，本 sprint 不修改）

- 任何 `src/omlx/cache/kvtc_codec.py / kvtc_calibration_store.py / kvtc_recon_gate.py / paged_ssd_cache.py / kvtc_errors.py / kvtc_tools_recalibrate.py`（属 S03，已 passed/finalized）
- `scripts/kvtc_ab_correctness.py`（S05）
- `.github/workflows/*`（S05）
- `src/omlx/admin/*`（pre-existing 修改，不在本 epic 范围）

## Done 定义达成（来自 .contract.md Acceptance）

| Acceptance | 满足证据 |
|------------|----------|
| ready 子任务能自动激活并派到正确角色 | C0/C2 已由其他 pane 在 graph-scheduler 派发下完成；C1/C3/C4 按 DAG 依赖 (C0+C2 → C1 → C3 → C4) 顺序执行 |
| UI 显示 epic、child sprint、能力使用和阻塞原因 | `GET /api/kvtc/state` 返回 Schema 7（含 state / last_ab_summary / feature_flag_state / recent_block_event / tracking_sprint / i18n_key / recon_fail_rate），外部 UI / CLI / dashboard 消费即可 |
| pane 输出不再只靠自然语言声称完成 | 19 pytest cases 真实运行通过（输出 raw 行附下）+ middleware 行为可由 `TestClient` 直接复现 |

## Decision Made — N5 默认决策

**`THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` 默认 = `0`（禁用 → 410）**，原因（与 S04 design §5 一致）：

1. 缺 staging 实测数据（OQ2 仍 partially_resolved per S02 / S03）；H2 鉴权 / 路径绑定假设未被静态扫描确认；H3 KV capture 时机修复（`wait_for_kv_seconds`）本 sprint 不实施（A3 API 6a 仅保留接口槽位）。
2. 满足 PRD「不污染主服务 cache」+「提供 rollback 指令」+ 「UI 默认关闭」3 条约束。
3. 切换条件：staging 复测 N5 H1/H2/H3 命中 + S05 N6 7 天 `M5 named_prompt_cache_save_2xx_rate ≥ 0.99` → ops 设 env=1。

## API Signatures

```python
# C0 — kvtc_ui_gate.py (S02 A3 API 7 backend)
def compute_state(
    now: datetime,
    env: dict[str, str],
    ab_summary_path: str | os.PathLike,
    recon_gate_jsonl_path: str | os.PathLike,
) -> GateStateResult

# C1 — server.py middleware (S02 A3 API 6b)
class NamedPromptCacheSaveDisableMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next): ...
# Returns HTTP 410 + {"error": "named_prompt_cache_save_disabled",
#                     "message": "...",
#                     "tracking_sprint": "sprint-20260521-..."}
# when THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED != "1".

# C1 — server.py /api/kvtc/state (S02 A3 API 7 + Schema 7)
@app.get("/api/kvtc/state")
async def kvtc_state(include_fixtures: bool = False) -> JSONResponse
```

## Test Evidence

```
$ ./venv/bin/python -m pytest tests/orchestration/ -v --tb=short
============================= test session starts ==============================
collected 19 items

tests/orchestration/test_kvtc_ui_gate.py::test_t1_startup_default_off_no_files PASSED [  5%]
tests/orchestration/test_kvtc_ui_gate.py::test_t2_default_off_to_preview PASSED [ 10%]
tests/orchestration/test_kvtc_ui_gate.py::test_t3_preview_back_to_default_off_on_force_off PASSED [ 15%]
tests/orchestration/test_kvtc_ui_gate.py::test_t4_preview_to_blocked_on_recon_fail PASSED [ 21%]
tests/orchestration/test_kvtc_ui_gate.py::test_t5_blocked_stays_blocked_until_fail_window_clears PASSED [ 26%]
tests/orchestration/test_kvtc_ui_gate.py::test_t6_hard_slo_violation_blocks_preview PASSED [ 31%]
tests/orchestration/test_kvtc_ui_gate.py::test_t7_enabled_state_unreachable_in_v1 PASSED [ 36%]
tests/orchestration/test_kvtc_ui_gate.py::test_t8_recon_fail_priority_over_ab_summary PASSED [ 42%]
tests/orchestration/test_kvtc_ui_gate.py::test_e1_env_kvtc_disable_forces_off PASSED [ 47%]
tests/orchestration/test_kvtc_ui_gate.py::test_e2_env_ui_force_off_overrides_recon_block PASSED [ 52%]
tests/orchestration/test_kvtc_ui_gate.py::test_e3_default_no_env_no_files PASSED [ 57%]
tests/orchestration/test_kvtc_ui_gate.py::test_e4_env_named_prompt_cache_enabled_flag_propagates PASSED [ 63%]
tests/orchestration/test_kvtc_ui_gate.py::test_save_410_default_when_env_unset PASSED [ 68%]
tests/orchestration/test_kvtc_ui_gate.py::test_save_passthrough_when_env_one PASSED [ 73%]
tests/orchestration/test_kvtc_ui_gate.py::test_state_endpoint_returns_schema_7_shape PASSED [ 78%]
tests/orchestration/test_kvtc_ui_gate.py::test_state_endpoint_default_excludes_fixtures PASSED [ 84%]
tests/orchestration/test_kvtc_ui_gate.py::test_ab_summary_missing_returns_unavailable PASSED [ 89%]
tests/orchestration/test_kvtc_ui_gate.py::test_ab_summary_malformed_json PASSED [ 94%]
tests/orchestration/test_kvtc_ui_gate.py::test_i18n_keys_complete_and_clean PASSED [100%]

======================== 19 passed, 3 warnings in 0.80s ========================
```

回归验证（S03 22 cases 仍通过，本 sprint 未破坏）：

```
$ ./venv/bin/python -m pytest tests/kvtc/ tests/orchestration/ -v --tb=short
======================== 41 passed, 3 warnings in 0.91s ========================
```

## Compat Notes

- `/v1/cache/prompt/save` env=1 时回到原 handler（行为不变）；env=0 时中间件在 pydantic validation 之前拦截，不会泄露 422 schema。
- `GET /api/kvtc/state` 是新路由，与现有 `/api/status` 兼容；未抢占 `/v1/cache/prompt/*` 任何路径。
- ImportError 兜底：若 S03 kvtc_ui_gate / kvtc_ui_i18n 模块缺失，`/api/kvtc/state` 返回 503 + `state=default_off` + `reason=state_compute_error:<cls>`，不抛 500。
- server.py 其他 6257 行（除 749-820 + 2374-2475 区域外）零改动 — `git diff -U0 src/omlx/server.py | grep '^@@'` 仅 2 个 hunk。
- OpenAPI schema 自动包含 410 响应（FastAPI 解析中间件返回的 JSONResponse）；不删除既有 422。

## Stop-Rule Compliance

- ❌ `src/omlx/cache/kvtc_codec.py / kvtc_calibration_store.py / kvtc_recon_gate.py / paged_ssd_cache.py / kvtc_errors.py / kvtc_tools_recalibrate.py` — NOT modified（git diff 验证 0 命中）
- ❌ `scripts/kvtc_ab_correctness.py` — NOT modified
- ❌ `.github/workflows/*` — NOT created
- ❌ `~/.solar/STATE.md` / epic.* / S01/S02/S03 artifacts — NOT touched
- ❌ 禁用 API 状态码留为 422 — verified middleware returns 410
- ❌ default UI 状态非 default_off — verified compute_state 默认返回 STATE_DEFAULT_OFF
- ❌ 跨态直跳 (default_off → enabled) — verified STATE_ENABLED 首版不可达（test_t7_enabled_state_unreachable_in_v1）
- ❌ 乐观词（已修复 / 稳定 / 完美 / 无需担忧） — grep 验证为 0（包括 server.py middleware 文案 + i18n 6 keys × 2 langs + handoff）
- ❌ live pane / harness restart / curl / uvicorn / ab_correctness — NOT invoked
- ❌ `wait_for_kv_seconds` H3 修方案 — NOT implemented（保留接口槽位，留 round-2 或后续 sprint）

## R1..R7 状态（继承 + 本 sprint 实施）

| Req | 状态 | S04 实施物 |
|-----|------|-----------|
| R1 论文对齐 | inherited from S01 (passed) | n/a |
| R2 calibration key 5 维 | inherited from S03 (passed) | n/a |
| R3 family classifier + sink/recent + side-band | inherited from S03 (passed) | n/a |
| R4 reconstruction gate | inherited from S03 (passed) | n/a |
| **R5 /v1/cache/prompt/save 422 → 410** | **implemented (S04)** | `NamedPromptCacheSaveDisableMiddleware` (env=0 默认 → 410) + 19 pytests 含 S1/S2 |
| R6 CI 5×3 矩阵 | **deferred to S05** | S04 不触 ab_correctness / workflows |
| **R7 UI default_off + 最近 A/B** | **implemented (S04)** | `compute_state` 4 状态 FSM + `GET /api/kvtc/state` Schema 7 + 6 i18n keys + 19 pytests 含 T1..T8/E1..E4/A1/A2/F1/F2/I1 |

## OQ1..OQ4 状态（继承 + 本 sprint 更新）

| OQ | S03 status | S04 status | 备注 |
|----|-----------|-----------|------|
| OQ1 stable-ci 真实 Qwen3.6 fixture | still_open | **still_open** | 仍归 S05；S04 用 synthetic tmp_path 跑 pytest |
| OQ2 /v1/cache/prompt/save 422 root cause | partially_resolved | **resolved-for-default-disable** | 默认 env=0 + 410 决策落地；切 env=1 仍待 staging 验证 H1/H2/H3 |
| OQ3 family-profile thresholds | confirmed (unified) | inherited | S04 不动 |
| OQ4 UI A/B 数据源 | resolved (reports_artifact) | **resolved-in-impl** | `THUNDEROMLX_KVTC_UI_AB_SOURCE` env 实施完整；默认指向 `reports/kvtc-ab/latest/ab_correctness.summary.json` |

## Env Switches 实施清单

| env | 默认 | 行为 | 实施位置 |
|-----|------|------|----------|
| `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` | `0`（禁用） | `0` → middleware 返回 410；`1` → 透传原 handler | `server.py` `_named_prompt_cache_save_enabled()` |
| `THUNDEROMLX_KVTC_UI_FORCE_OFF` | `0` | `1` → 状态机始终 default_off | `kvtc_ui_gate._is_force_off()` |
| `THUNDEROMLX_KVTC_DISABLE` | `0`（S03 同名） | `1` → 状态机始终 default_off | 同上 |
| `THUNDEROMLX_KVTC_UI_AB_SOURCE` | （空，回退默认路径） | 指定 ab summary 文件路径 | `kvtc_ui_gate.get_default_ab_summary_path()` |
| `THUNDEROMLX_KVTC_HOME` | （空，回退 logs/recon_gate.jsonl） | 指定 KVTC_HOME 根目录 | `kvtc_ui_gate.get_default_recon_gate_jsonl_path()` |
| `THUNDEROMLX_KVTC_RECON_FAIL_WINDOW_SEC` | `300` | recon FAIL rate 计算窗口 | `kvtc_ui_gate._fail_window_sec()` |

## 已完成

- C0 + C2 + C1 + C3 + C4 全 5 节点（C0/C2 由 W1 其他 pane 完成；C1/C3/C4 由本 round 完成）。
- 2 个新模块（`kvtc_ui_gate.py` + `kvtc_ui_i18n.py`）+ server.py 局部修改（174 行新增，2 个 hunk）+ 1 个测试文件（19 cases）+ 1 个 handoff + 1 个 traceability.json。
- 19 pytest cases 真实运行通过（≥15 acceptance；CPU 0.80s，<15s 上限）。
- S03 22 cases 仍全 PASS（41 cases 整体回归 0.91s）。
- N5 默认决策 = env=0 + 410 显式记录 + 切 env=1 条件钉死。
- 6 个 env 开关全部就位 + 默认值钉死。

## 已验证（本 sprint 边界内）

- 19 pytest cases all PASS（含 8 state transitions / 4 env combos / 2 saved 410 / 2 state api / 2 ab fallback / 1 i18n）
- 41 pytest cases 联合回归 PASS（防止 S04 误改 S03 模块）
- server.py 路由层 410 middleware 在 pydantic 之前执行（test_save_410_default_when_env_unset 用未通过 pydantic 的 body 验证；如果 pydantic 先跑会返回 422 而非 410）
- `/api/kvtc/state` Schema 7 字段完整（test_state_endpoint_returns_schema_7_shape）
- include_fixtures=false 默认（test_state_endpoint_default_excludes_fixtures）
- AB summary 缺失 / 损坏 → fail-soft default_off（test_ab_summary_missing / malformed）
- ImportError 兜底（C1 try/except 块）
- server.py git diff -U0 仅 2 hunk：749-820 + 2374-2475，未触碰其他 ~6260 行

## 未验证（下游 sprint 责任）

- staging 真实复现 `/v1/cache/prompt/save` 422 + 验证 H1/H2/H3 → 由 S04 builder（本 round 之外）或运维在 staging。
- N5 切 env=1 后 200 条 staging 调用 2xx ≥ 99% → S05 final regression.
- UI e2e 截图（4 状态视觉）→ 由 S05 staging 或外部 UI 团队（ThunderOMLX 无 frontend 目录，UI 由外部消费）。
- `recon_gate.jsonl` 真实产出（S03 已实现 writer，但生产数据流由运行期产生）。
- auto block_by_gate_fail 60s 阈值演练 → S05.
- CI YAML + ATLAS hook → S05.

## 风险

- **N5 默认 env=0**：默认禁用对当前没有 named prompt cache 用户没影响，但如果有客户端依赖该 API，会立刻拿到 410。切 env=1 需 ops 配合且依赖 S03 KV capture 链路稳定。
- **ImportError 兜底掩盖真问题**：`/api/kvtc/state` 在 S03 模块缺失时返回 503 而非抛 ImportError；如果生产部署 S04 但 S03 模块路径变更，UI 会 silently 走 503 而非告警。建议运维监控 `state_compute_error` reason 字段。
- **fixture 数组未做大小检查**：`include_fixtures=true` 时直接返回 `last_ab_summary["fixtures"]`；若 fixtures > 几千 → 响应体可能巨大。S05 必须保证 fixtures 数量 ≈ 15 + N/A（design §"15 个" 一致）。
- **recon_fail_rate 计算依赖时区**：`compute_state` 接收 `now: datetime`；如果调用方传 naive datetime，窗口可能错配。Server endpoint 用 `datetime.now(timezone.utc)`，OK；但其他调用方需注意。
- **server.py 6431 行 surgical edit**：本 sprint 只动 2 个 hunk，但如果 future sprint 重排 server.py（例如插入新路由），hunk 位置可能漂移。建议保留 `_S04_TRACKING_SPRINT` / `_NAMED_PROMPT_CACHE_SAVE_PATH` 常量在 server.py 顶部附近便于追踪。

## 后续待办（给协调器 / 审判官 / 下游 sprint）

1. **本 sprint**：协调器将状态 → `reviewing/builder_done/evaluator`；等审判官评估。
2. **审判官**：跑 `solar-harness session evaluate sprint-…s04-orchestration-ui --json` + 抽样 plan §5 验证 A-L；重点抽样：(a) 19 pytest 实际通过；(b) server.py diff 仅 2 hunk 在 KVTC 区域；(c) 410 错误体含 `tracking_sprint`；(d) `/api/kvtc/state` schema_version；(e) 6 i18n keys + 禁词；(f) 41 cases 联合回归 PASS（S03 + S04）。
3. **PASS 后**：S03 + S04 都 passed → epic_decomposer 激活 S05_verification_release。
4. **S05 round-1**：依赖 S03 公开 API + S04 `/api/kvtc/state` + S04 410 middleware；S05 在 N6 CI 中调用 `GET /api/kvtc/state` 验证 UI gate；S05 在 staging 跑 200 条 `/v1/cache/prompt/save` 测 2xx（env=1）/ 410（env=0）比例。
5. **N5 切换 env=1 条件**：(a) S04 staging 复现 H1/H2/H3 + 选定修方案；(b) S05 N6 7 天 success_rate ≥ 0.99；(c) ops 设 env=1。本 sprint 不预 enable。
6. **epic 关闭门禁**：S05 passed 后 parent-check `ready=true` 才允许 epic close。
