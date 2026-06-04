# Design — S04 Orchestration-UI 切片：API 网关 + UI gate state-machine

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s04-orchestration-ui`
slice: `orchestration-ui`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T08:55:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream_passed: `S02_architecture (passed 2026-05-22T08:39:39Z) — S04 not depending on S03 per epic DAG`
parallel_with: `S03_core_runtime (active/planning_complete, may run concurrently)`

## 0. 本切片的边界（强制 read-first）

- **ThunderOMLX 仓库无 frontend/UI/static/templates 目录**（A1 archeology + grep 实测）。S04 不写任何 HTML/JS/CSS；**S04 落地为 server-side 状态机 + JSON API + env 开关**。"UI" 由外部消费者（dashboard / CLI / 第三方 UI）通过 `GET /api/kvtc/state` 拿状态。
- **本 sprint 允许 Write/Edit** 的路径：
  - `/Users/lisihao/ThunderOMLX/src/omlx/server.py`（仅修 `/v1/cache/prompt/save` 区域 lines 2051-2215 + 新增 `/api/kvtc/state` 路由）
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_ui_gate.py`（新建：状态机 + env 开关）
  - `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_ui_i18n.py`（新建：i18n key 常量 + zh-CN/en-US 默认文案）
  - `/Users/lisihao/ThunderOMLX/tests/orchestration/test_*.py`（新建）
- **严格禁止** 触碰：
  - 任何 `src/omlx/cache/kvtc_codec.py / kvtc_calibration_store.py / kvtc_recon_gate.py / paged_ssd_cache.py / kvtc_errors.py`（属 S03）
  - `scripts/kvtc_ab_correctness.py`（S05）
  - `.github/workflows/`（S05）
  - 任何 `server.py` 非 `/v1/cache/prompt/save` 与 `/api/kvtc/state` 区域代码
- 禁止 `tmux send-keys`、`solar-harness restart`、动 STATE.md、epic.*、S01/S02 artifacts。
- 禁止用乐观词；禁止把禁用 API 状态码留为 422（必须 410）；禁止 default UI 状态非 default_off。

## 1. S03 协同（软依赖，不阻塞）

S04 import 路径 `from omlx.cache.kvtc_errors import (...)` 依赖 S03 B0 完成。在 S03 未完成期间：

- S04 builder 可用 `try/except ImportError` 兜底（仅 server.py 入口）；
- 或 S04 builder 显式在 task_graph 节点 read_scope 中等待 S03 B0 产出（推荐：手动校验 `test -f src/omlx/cache/kvtc_errors.py`）。

epic DAG 设计上 S04 不强依赖 S03，但**实施期**有上述软依赖。S04 planner 在 plan §5 加 import-check 验证。

## 2. 上游摘要（S02 → S04）

S02 已交付 S04 实施所需的契约（in traceability.json downstream_handoff for S04_orchestration_ui，已读取）：

| S02 输入 | S04 节点 | S04 实施物 |
|----------|----------|-----------|
| A3 API 6a/6b（/v1/cache/prompt/save 双签名） | C1 | server.py 路由层加 env middleware（双分支） |
| A3 API 7（GET /api/kvtc/state） | C0 + C1 | 新建状态机 module + server 路由 |
| A4 Schema 7（ui.kvtc.state.v1） | C1 | API 响应序列化 |
| A5 M3（/v1/cache/prompt/save 422 → 410 迁移） | C1 | env=0 默认 → 中间件前置拦截 410 |
| A5 M4（UI default_off 强制升级） | C0 + C1 | 状态机首装 default_off；任何"升级"路径强制走 preview |
| N5 决策树 | C1 决策 | 默认走 **禁用（env=0 + 410）**，待 staging 验证后切换 env=1 |
| N7 4-state state machine + i18n | C0 + C2 | state-machine 实现 + 6 个 i18n key |

## 3. 系统视图（哪个文件什么变化）

```
omlx/cache/                                   （S04 写范围）
├── kvtc_ui_gate.py        [C0 NEW]            4-state FSM + env reader + AB summary loader
└── kvtc_ui_i18n.py        [C2 NEW]            6 i18n keys × {zh-CN, en-US}

omlx/server.py             [C1 MODIFY 局部]    /v1/cache/prompt/save env middleware (410 default)
                                               + new endpoint GET /api/kvtc/state

tests/orchestration/                           （S04 写范围）
└── test_kvtc_ui_gate.py   [C3 NEW]            ≥15 cases：state transitions + env switches + 410
                                               + state api response + AB summary read
```

下游不动（属其他 sprint）：
- `src/omlx/cache/kvtc_codec.py / kvtc_calibration_store.py / kvtc_recon_gate.py / paged_ssd_cache.py / kvtc_errors.py / kvtc_tools_recalibrate.py`（S03）
- `scripts/kvtc_ab_correctness.py`（S05）
- `.github/workflows/`（S05）

## 4. State Machine（C0 实施）

per S01 N7-A1 钉死 4 状态闭包，server-side 状态由以下输入计算：

```
                              ┌─────────────────────────┐
   default_off  ◀─────────────│ feature_flag_off (env)  │── 任何状态
       │                      └─────────────────────────┘
       │ prereq_ready (latest_ab_summary 存在 + hard SLO 全 pass)
       ▼
   preview
       │ user_enable (POST /api/kvtc/preview/accept)
       ▼
   enabled
       │ recon_fail (recon_gate.jsonl 末窗 FAIL rate > 1% / 5min)
       ▼
   blocked_by_gate_fail
       │ recover (人工 acknowledge + 最近 A/B 重新达标)
       ▼
   default_off
```

输入信号（C0 读取）：

1. `$THUNDEROMLX_KVTC_UI_FORCE_OFF=1` env → 永远 default_off（覆盖一切）
2. `$THUNDEROMLX_KVTC_DISABLE=1`（S03 同名 env）→ default_off
3. `latest_ab_summary` JSON 文件路径由 `$THUNDEROMLX_KVTC_UI_AB_SOURCE` 决定（默认 = `reports/kvtc-ab/latest/ab_correctness.summary.json`）
4. `recon_gate.jsonl` 末窗 FAIL rate（`$THUNDEROMLX_KVTC_HOME/logs/recon_gate.jsonl` 末 N 行计算）

状态机为**纯函数式**：给定 inputs → 唯一 state。无 in-memory persistent state；每次 `GET /api/kvtc/state` 重新计算。

## 5. /v1/cache/prompt/save 决策（C1 实施）

per N5-A5 决策树 + S02 A3 API 6 双签名：

- **默认 env `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED=0`** → middleware 前置拦截，返回 410 + N5-A6 统一错误体
- **env=1**（staging 验证后切换）→ 走原 handler（保留 server.py:2051-2215 现状）；可选加 `wait_for_kv_seconds: int = 0` kwarg（per A3 API 6a）但**本 sprint 不实施 wait_for_kv 逻辑**（H3 修方案的代码扩展属 round-2 或留给后续 sprint）

C1 节点写入 server.py 必须：

1. 在 `/v1/cache/prompt/save` 路由 decorator 前**注入 middleware**或前置 if 判断（env=0 → 410 + N5-A6 错误体 + tracking_sprint）
2. 不修改原 handler body（lines 2051-2215）
3. 加新 endpoint `GET /api/kvtc/state` 返回 Schema 7 JSON

S04 builder 默认选择 **禁用分支**（环境变量 default=0），原因：

- 缺 staging 实测数据（OQ2 仍 partially_resolved per S02）
- 等 S03 完成 + S05 fixture 准备 + staging 复测后再考虑切 env=1
- 默认禁用满足 PRD 「不污染主服务 cache」+ 「提供 rollback 指令」

## 6. i18n Keys（C2 实施）

per N7-A4 6 个 i18n key × {zh-CN, en-US}，C2 输出常量 dict：

```python
KVTC_UI_I18N = {
    "kvtc.ui.state.default_off": {
        "zh-CN": "KVTC 默认关闭。开启前请查看最近一次 A/B 结果。",
        "en-US": "KVTC is disabled by default. Review the latest A/B gate result before enabling.",
    },
    "kvtc.ui.state.preview": {...},
    "kvtc.ui.state.enabled": {...},
    "kvtc.ui.state.blocked_by_gate_fail": {...},
    "kvtc.ui.toast.recover": {...},
    "kvtc.ui.state.feature_flag_off": {...},
}
```

server `GET /api/kvtc/state` 响应只返回 i18n_key，文案由消费者（外部 UI）自行渲染。

## 7. 关键设计决策（钉死）

1. **N5 默认禁用** — env=0 时返回 410（per N5-A6 统一错误体 + tracking_sprint 字段）
2. **state machine 纯函数式** — 无 in-memory state；每次请求重新计算
3. **状态机优先级**：`THUNDEROMLX_KVTC_UI_FORCE_OFF > THUNDEROMLX_KVTC_DISABLE > recon_fail > prereq_ready > user_enable > default_off`（高 → 低覆盖）
4. **AB summary 读取容错** — 文件不存在 / 解析失败 → 状态机走 `default_off` + `last_ab_source: "unavailable"`，**禁止抛 500**
5. **recon_gate.jsonl FAIL rate 窗口** — 默认末 5 分钟 / 末 1000 行（取小），可被 env `THUNDEROMLX_KVTC_RECON_FAIL_WINDOW_SEC=300` override
6. **不实施 wait_for_kv_seconds 修复路径** — 本 sprint 仅留接口槽位（A3 API 6a 已含），实际 H3 修复留待 staging 验证后启动 round-2 或后续 sprint
7. **GET /api/kvtc/state 不带 query 默认 `include_fixtures=false`** — 防 UI 拿巨型 fixtures 数组
8. **server.py 限改区域** — 仅 `/v1/cache/prompt/save`（2051-2215）+ 新增 `/api/kvtc/state` 路由块；其他 6431 行不动

## 8. 测试矩阵（C3 必跑 ≥15 cases）

| case 类型 | cases | 说明 |
|----------|-------|------|
| state machine 4 状态 × 转移 | 8 | N7-A1 转移表全覆盖 |
| env 开关组合 | 4 | DISABLE / FORCE_OFF / NAMED_PROMPT_CACHE / 全开 |
| /v1/cache/prompt/save 410 默认 | 2 | env=0 默认 vs env=1 通过 |
| /api/kvtc/state 响应 schema | 2 | 含/不含 fixtures；ab summary 缺失 |
| ab summary 读取容错 | 2 | 文件不存在 / JSON 损坏 → default_off |
| i18n keys 完整 | 1 | 6 个 key × 2 lang 全在 |

合计 ≥ 19 case（acceptance ≥15 下限）。

测试必须：

- 用 `tmp_path` fixture 写 fake ab_summary.json / recon_gate.jsonl
- 用 `monkeypatch` 设置 env
- 不真起 FastAPI server（用 `TestClient`）
- 不依赖 S03 实际 codec（mock `kvtc_errors` 或捕获 ImportError）
- CPU ≤ 15s

## 9. 状态机持久性

- 无持久化：状态由 env + jsonl + summary file **实时计算**
- 唯一"长期 state" = env 变量（`THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` / `*_KVTC_UI_FORCE_OFF`），由运维管理
- `user_enable` 信号：可选 POST `/api/kvtc/preview/accept`（**本 sprint 不实施**；属后续）。当前版本中 state machine 只支持 `default_off → preview → blocked_by_gate_fail` 自动转移，**没有 enabled 状态**（保守起点）

→ **简化决定**：S04 首版只实现 3 个可达状态：`default_off`、`preview`、`blocked_by_gate_fail`。`enabled` 状态保留在 Schema 中但首版始终不可达（需 future sprint 加 POST endpoint）。这降低实施风险并符合 N7 default_off 强制约束。

## 10. 失败恢复

| 失败模式 | 处理 |
|----------|------|
| `THUNDEROMLX_KVTC_UI_AB_SOURCE` env 未设 | 用默认路径 `reports/kvtc-ab/latest/ab_correctness.summary.json`；缺文件 → default_off + `last_ab_source: "unavailable"` |
| ab_summary.json JSON 损坏 | log warn + default_off + `last_ab_source: "malformed"` |
| recon_gate.jsonl 读失败 | 视为 FAIL rate=0（保守，不轻易 block）+ log warn |
| `THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` 未设 | 默认 0（禁用） |
| middleware 内部异常 | 仍返回 410 + 错误体（fail-closed） |
| /api/kvtc/state 计算异常 | 返回 503 + `{"state": "default_off", "reason": "state_compute_error", ...}`（避免 500 leak） |

## 11. 观测（接 S02 A6）

- `recon_gate.jsonl` 读路径每次决策计入指标 `ui_gate_state_request_count` + `ui_gate_state_<state>_count`
- `/v1/cache/prompt/save` 405/410/200 状态计数
- env 切换：`THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED` 启动期读取后必须 log 一行：`named_prompt_cache_save_enabled=<0|1>`
- 不新增 dashboard（属运维范围）；S04 仅产生原始 metric counter

## 12. 兼容性

| 项 | 兼容动作 |
|----|----------|
| `/v1/cache/prompt/save` 旧客户端调用 | env=0 时返回 410；env=1 时回到原 handler 不破坏 |
| 现有 server.py 主路由 | 限改 lines 2051-2215 + 新增 `/api/kvtc/state` 路由块；其他不动 |
| OpenAPI schema | 410 错误体作为 `responses` 添加；不删除 422 schema |
| 中间件顺序 | env 检查必须**最早**（before pydantic validation），避免泄露 422 错误细节 |

## 13. 冲突 / 依赖 / 降级

**冲突**：

- 与 S03 软依赖：`omlx.cache.kvtc_errors` 模块由 S03 B0 创建；S04 C0/C1 import 时若 S03 未完成 → ImportError；solution: `try: from omlx.cache.kvtc_errors import ... except ImportError: # use local stubs`
- 与 S05 路径合同：`reports/kvtc-ab/latest/ab_correctness.summary.json` 实际由 S05 CI 产生；S04 假设该路径存在；若不存在 → fail-soft default_off
- `/api/kvtc/state` 新路由可能与现有路由冲突；S04 builder 必须先 `grep -n "/api/kvtc" server.py` 确认无碰撞

**依赖**：

- C1 依赖 C0（状态机）+ C2（i18n）
- C3 依赖 C0/C1/C2
- C4 依赖 C3

**降级**：

- 若 ab_summary 文件不可读 → default_off（保守）；不允许 server 5xx
- 若 recon_gate.jsonl 不可读 → FAIL rate=0（保守）
- 若 S03 kvtc_errors 不可用 → S04 内部 stub 类（不阻塞 S04 上线，但 import 路径在 S03 完成后立即切换）

## 14. 非目标（明确禁止）

- 不实施 `wait_for_kv_seconds` H3 修复（留 round-2 / 后续 sprint）
- 不实施 `enabled` 状态用户开关（POST /api/kvtc/preview/accept）—— 首版强制走 `default_off → preview → blocked_by_gate_fail`
- 不真改 H1/H2 prompt_too_short / 鉴权（属 server inference loop 范围，未来再做）
- 不写 HTML/JS/CSS（无 frontend）
- 不动 S03 任何 KVTC 模块
- 不真跑 `scripts/kvtc_ab_correctness.py`（S05）
- 不写 `.github/workflows/`（S05）
- 不动 ~/.solar/STATE.md / epic.* / S01/S02 artifacts
- 不用乐观词；不放宽 hard 阈值；不把禁用 API 状态码留为 422

## 15. 给 S05 的接力清单（C4 输入要点）

- S05 在 CI 中需调用 `GET /api/kvtc/state` 验证 state machine（属 N7 evidence-E1..E6）
- S05 提供 `reports/kvtc-ab/<ts>/ab_correctness.summary.json` schema 与本 sprint Schema 7 一致；若 schema 不一致 → S05 round-2
- S05 在 N6 CI 中必须验证 410 路径 + 200 路径（取决于 env）
- S04 不写 CI；S05 注册 CI hook
