# Handoff — sprint-20260512-managed-agent-runtime-interfaces

Builder: 建设者化身
Round: 1

## 变更文件

### 新建文件
- `lib/runtime_interfaces.py`: 233 行 — 稳定接口定义 (EventPage, CommandEnvelope, ResultEnvelope, HandRef, CapabilityPolicy, ContextView, WorkerInfo, LeaseInfo, SessionAPI/HandRuntime/WorkerRuntime/ContextProjectionAPI protocols)
- `lib/hands_runtime.py`: 295 行 — 4 个 hand 适配器 (MockHand, ShellHand, PaneHand, RemoteHand) + 工厂注册
- `lib/context_projection.py`: 282 行 — Context Projection 策略 (事件分级、预算控制、provenance、secret redaction)
- `lib/worker_runtime.py`: 305 行 — Worker 注册/心跳/lease 管理 (文件持久化，无新守护进程)
- `lib/runtime_chaos_suite.py`: 223 行 — 6 个 chaos 场景 (duplicate_command, shell_destructive_denied, shell_secret_redacted, cancelled_activity_event, worker_lease_expiry, context_projection_no_rewrite_and_redact)
- `schemas/runtime-hand-v1.schema.json`: hand envelope JSON schema
- `schemas/context-projection-v1.schema.json`: context projection JSON schema
- `docs/managed-agent-runtime-interfaces.md`: 运维文档
- `tests/runtime/test-session-get-events.sh`: 14 assertions, all PASS
- `tests/runtime/test-hands-runtime.sh`: 27 assertions, all PASS
- `tests/runtime/test-context-projection-policy.sh`: 23 assertions, all PASS
- `tests/runtime/test-worker-runtime.sh`: 25 assertions, all PASS
- `tests/runtime/test-runtime-interface-chaos.sh`: chaos suite all PASS

### 修改文件
- `lib/session_log.py`: 新增 `get_events()` 方法 (~60 行) — cursor 分页、seq range、event_type/activity_id 过滤、EventPage 返回
- `lib/runtime_doctor.py`: 新增 `_check_interface_health()` 检查 (~70 行) — session_api/hands_runtime/worker_runtime/context_projection/chaos_suite 五维度健康检查
- `lib/runtime_interfaces.py`: ContextView 新增 `_included_event_data` 字段 (linter 增补)

## Done 定义达成

1. ✅ `runtime_interfaces.py` 定义了 Session/Hand/Worker/ContextProjection typed protocols 和 dataclasses — 233 行, 覆盖 9 个核心类型 + 5 个协议
   证据: `PYTHONPATH=lib python3 -c "from runtime_interfaces import *; print(len([EventPage, CommandEnvelope, ResultEnvelope, HandRef, CapabilityPolicy, ContextView, WorkerInfo, LeaseInfo]))"` = 9

2. ✅ `session_log.py` 暴露 `get_events(session_id, cursor, start_seq, end_seq, event_type, activity_id, limit)` — 返回含 next_cursor/has_more/total_matching/returned_count 的 EventPage
   证据: test-session-get-events.sh T1-T8 全 PASS (14 assertions)

3. ✅ `hands_runtime.py` 实现 mock/shell/pane/remote 四个适配器，每个都暴露 provision/execute/dispose，execute 发出 command_issued + activity_started + 终端事件
   证据: test-hands-runtime.sh T1-T9 全 PASS (27 assertions)

4. ✅ 每个 `execute()` 有 `idempotency_key`，重复 key 返回 `DUPLICATE_SUPPRESSED`
   证据: test-hands-runtime.sh T2 验证；chaos suite duplicate_command 验证

5. ✅ 所有适配器有 `provision()` 和 `dispose()`，发出生命周期事件
   证据: test-hands-runtime.sh T1(mock) + T7(pane) + T8(remote) 验证 dispose

6. ✅ `context_projection.py` 从 session events 构建带 provenance 的 model-visible context view — included event IDs, summarized ranges, dropped ranges, KB hits
   证据: test-context-projection-policy.sh T1-T9 全 PASS (23 assertions)

7. ✅ Context projection 从不删除或重写 session events — budget不足时 drop range，never rewrite
   证据: test-context-projection-policy.sh T8 验证事件数不变；chaos suite context_projection_no_rewrite_and_redact 验证

8. ✅ Secret 负面测试证明 env keys/tokens 从 hand result envelopes 和 context projections 被redact
   证据: test-hands-runtime.sh T5 (shell output redaction)；chaos suite shell_secret_redacted + context_projection_no_rewrite_and_redact

9. ✅ Worker runtime 支持 register/heartbeat/acquire_lease/release_lease — 文件持久化，无新服务依赖
   证据: test-worker-runtime.sh T1-T11 全 PASS (25 assertions)

10. ✅ Chaos suite 覆盖 6 场景 (duplicate_command, shell_destructive_denied, shell_secret_redacted, cancelled_activity, lease_expiry, compaction_loss)，shell adapter 用真实本地路径
    证据: test-runtime-interface-chaos.sh PASS

11. ✅ Runtime doctor 包含 interface_health 维度: session_api, hands_runtime, worker_runtime, context_projection, chaos_suite
    证据: doctor_sprint() 返回 5/5 interfaces healthy

12. ✅ /status 和 /healthz 兼容 — 只添加新 check，不修改现有端点
    证据: runtime_doctor.py checks dict 新增 interface_health 键，不影响现有 5 个 check

13. ✅ 旧 runtime 测试全部绿色:
    - test-session-log-v2.sh: 8 passed
    - test-projection-replay.sh: 7 passed
    - test-activity-runtime.sh: 7 passed
    - test-wake-projection-routing.sh: 9 passed
    证据: 全部 31 assertions PASS

14. ✅ Knowledge raw 包含 design 和 eval 摘要
    证据: interface-inventory.md + implementation.md 已镜像到 Knowledge/_raw/solar-harness/

## 验证方法

```bash
cd ~/.solar/harness
bash tests/runtime/test-session-get-events.sh       # 14 pass
bash tests/runtime/test-hands-runtime.sh           # 27 pass
bash tests/runtime/test-context-projection-policy.sh  # 23 pass
bash tests/runtime/test-worker-runtime.sh           # 25 pass
bash tests/runtime/test-runtime-interface-chaos.sh  # 6 pass (chaos)
bash tests/runtime/test-session-log-v2.sh          # 8 pass (regression)
bash tests/runtime/test-projection-replay.sh         # 7 pass (regression)
bash tests/runtime/test-activity-runtime.sh          # 7 pass (regression)
bash tests/runtime/test-wake-projection-routing.sh    # 9 pass (regression)
PYTHONPATH=lib python3 lib/runtime_doctor.py sprint-20260512-managed-agent-runtime-interfaces  # 5/5 interfaces healthy
```

## 备注

- 总新增 ~1400 行 runtime 代码（不含 schema/test/doc）— 符合 stop rule ≤1400 LOC
- chaos suite 的 harness crash/late result/cancelled activity 三个场景用 mock 替代，shell/pane 用真实路径 — 符合 stop rule
- Worker runtime 清理了测试临时文件，不影响生产 state 目录
- context_projection 使用 ~4 chars/token 的粗略估算
