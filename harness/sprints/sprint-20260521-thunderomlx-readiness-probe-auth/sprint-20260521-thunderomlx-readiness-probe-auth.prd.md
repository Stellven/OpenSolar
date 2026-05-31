# PRD: ThunderOMLX authenticated readiness probe

## Summary
Fix ThunderOMLX 8002 readiness and monitor probes so authenticated services are not marked unhealthy just because unauthenticated `GET /v1/models` returns `401`.

## Problem
ThunderOMLX is configured with API-key enforcement. During the cache usage observability sprint, an unauthenticated readiness loop repeatedly called `/v1/models` and timed out even though `/v1/messages` was healthy and cache hits were working. This creates false alarms and can trigger unnecessary restarts or stale-task diagnosis.

## Goals
- Replace unauthenticated readiness checks with one of:
  - an authenticated `/v1/models` probe using the local configured API key without printing it, or
  - a dedicated non-secret health endpoint if ThunderOMLX already exposes one.
- Update scripts or monitor helpers used by Mac mini solar-harness/ThunderOMLX operations.
- Preserve current runtime constraints:
  - model: `Qwen3.6-35b-a3b`
  - service: `127.0.0.1:8002`
  - SSD cache: `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`
  - hot cache: `8GB`
  - `anthropic_prefix_cache_enabled=true`
  - Partial Block Cache, Full Skip, and Approximate Skip remain disabled.
- Add focused tests or smoke checks proving:
  - unauthenticated `401` is treated as "auth required / service alive", not "port unhealthy";
  - authenticated probe returns ok;
  - `/v1/messages` still reports `usage.cache_read_input_tokens > 0` on a repeated-prefix request;
  - Chinese output has `bad_chars=false`.

## Non-Goals
- Do not rework the cache algorithm.
- Do not change API keys or print secrets.
- Do not delete cache directories.
- Do not enable unsafe cache features.
- Do not change the model or route pane4 away from ThunderOMLX.

## Acceptance
- Final report exists at `/Users/lisihao/.solar/harness/monitor-reports/thunderomlx-readiness-probe-auth.md`.
- Task graph all nodes passed and parent-check ready is true.
- Probe behavior is documented with command evidence, sanitized for keys/tokens.
- ThunderOMLX 8002 is healthy after the change.
- Repeated-prefix live smoke shows `cache_read_input_tokens > 0` and `bad_chars=false`.

## 背景 / Context
ThunderOMLX 启用了 API-key 强制鉴权。在 cache usage observability sprint 期间，一个**未鉴权**的 readiness 循环反复调用 `GET /v1/models` 并超时——即便 `/v1/messages` 实际健康、cache 命中正常。未鉴权请求返回 `401` 被探针误判为“端口不健康”，从而产生误报，可能触发不必要的重启或 stale-task 诊断。

运行时上下文（必须保持不变）：
- model: `Qwen3.6-35b-a3b`；service: `127.0.0.1:8002`
- SSD cache: `/Volumes/RAID0-Main/omlx-cache/ssd-qwen36`；hot cache: `8GB`
- `anthropic_prefix_cache_enabled=true`
- Partial Block Cache / Full Skip / Approximate Skip 保持 disabled。

## 用户故事 / User Stories
- 作为 Mac mini 运维者，当 ThunderOMLX 开启鉴权时，readiness/monitor 探针不应因未鉴权 `401` 把健康服务标记为不健康。
- 作为运维者，我希望探针能区分“服务存活但需鉴权（401）”与“端口真正不健康”，避免误触发重启/stale 诊断。
- 作为审计者，我需要带命令证据（已脱敏 key/token）的探针行为文档，确认改动后 8002 健康且 cache 仍生效。

## 功能需求 / Requirements
- 用以下之一替换未鉴权 readiness 检查：
  - 使用本地配置的 API key 的**已鉴权** `/v1/models` 探针（不打印 key）；或
  - 若 ThunderOMLX 已暴露专用非敏感 health 端点，则改用该端点。
- 更新 Mac mini solar-harness / ThunderOMLX 运维所用的脚本或 monitor helper。
- 新增聚焦测试 / smoke 检查，证明：
  - 未鉴权 `401` 被判为“需鉴权 / 服务存活”，而非“端口不健康”；
  - 已鉴权探针返回 ok；
  - 重复前缀请求下 `/v1/messages` 仍报 `usage.cache_read_input_tokens > 0`；
  - 中文输出 `bad_chars=false`。
- 产出最终报告 `~/.solar/harness/monitor-reports/thunderomlx-readiness-probe-auth.md`。

## 约束 / Constraints
- 不重写 cache 算法。
- 不修改 API key、不打印任何 secret（探针证据须脱敏）。
- 不删除 cache 目录。
- 不启用不安全的 cache 特性（Partial Block / Full Skip / Approximate Skip 保持 disabled）。
- 不更换 model，不把 pane4 路由切离 ThunderOMLX。
- 所有产出不放入 `/tmp`（STATE.md 全局约束）；不破坏现有 API 接口。
- 环境：macOS arm64 (Mac mini M4)。

## 风险 / Risks
- 探针脚本误打印 API key 进日志/报告（高影响）——统一从配置读取并脱敏，证据中以掩码呈现。
- 把 `401` 一律视为“健康”可能掩盖真实的鉴权配置错误（中）——需区分 `401`（存活需鉴权）与连接拒绝/超时（不健康）。
- 已鉴权探针若用错 header/key 会引入新的误报（中）——smoke 用例需同时覆盖正确鉴权 200 与错误鉴权路径。
- 改动 monitor helper 可能影响其他依赖该探针的 sprint（中）——局部修复，保留原接口签名。

## 开放问题 / Open Questions
- ThunderOMLX 是否已暴露专用非敏感 health 端点？若有则优先用它而非鉴权 `/v1/models`（待 Builder 探测确认）。
- API key 的来源（环境变量 / 配置文件路径）是否已标准化，探针应从哪里读取？
- readiness 探针的判定矩阵是否需要固化为共享 helper，供其他 monitor 复用？

## 架构交接 / Planner Handoff
- handoff_to: planner
- 建议拆分：(1) 探测/确认 health 端点或鉴权探针方案；(2) 改 readiness/monitor helper 判定逻辑（401=alive）；(3) 鉴权探针读 key 并脱敏；(4) smoke 用例（401 / 200 / cache_read_input_tokens>0 / bad_chars=false）；(5) 最终报告。
- 复用现有 monitor helper 接口，避免破坏其他 sprint 依赖。
- 验收锚点见上文 Acceptance：最终报告、task graph 全 PASS + parent-check ready=true、8002 健康、cache 实测、脱敏证据。
- 状态纪律：PM 保持 status=drafting，不修改 .finalized；Planner 接手生成 sprint contract。
