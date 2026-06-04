# Plan — sprint-20260521-thunderomlx-readiness-probe-auth

## 概述

修复 ThunderOMLX 8002 readiness 探针误判：当服务启用 API-key 鉴权后，未鉴权的 `GET /v1/models` 返回 401 被探针误判为"端口不健康"，导致 monitor/restart 循环误触发。实际上服务完全正常，只是需要鉴权。

## 问题根因

```
Monitor/Restart Loop
    │
    ├─ GET /v1/models (无 auth header)
    │       ↓
    │  HTTP 401 "API key required"
    │       ↓
    │  探针判定: 端口不健康 ← 误判!
    │       ↓
    │  触发: 超时等待 / 误报 / 可能重启
    │
    └─ 实际情况:
       GET /health → HTTP 200 "healthy" (无需鉴权)
       POST /v1/messages (带 auth) → HTTP 200 + 正常响应
```

## 架构设计

```
                    ┌─────────────────────────────────────┐
                    │  thunderomlx_health_probe.py         │
                    │  (新增 auth-aware readiness helper)  │
                    └─────────────┬───────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
     GET /health          GET /v1/models        GET /v1/models
     (无需 auth)          (无 auth)             (带 auth)
         │                    │                     │
         ▼                    ▼                     ▼
     HTTP 200             HTTP 401              HTTP 200
     "healthy"            "API key required"    model_count=23
         │                    │                     │
         └────────┬───────────┴─────────────────────┘
                  ▼
         三态判定矩阵:
         ┌──────────────────────────────────────────────┐
         │ /health=200 + auth_models=200 → ok           │
         │ /health=200 + models=401      → auth_required│
         │                                  _alive      │
         │ /health≠200 或 连接拒绝/超时  → error        │
         └──────────────────────────────────────────────┘
```

## 关键决策

1. **优先用 `/health` 做基本存活检查** — 无需鉴权，快速判断进程是否响应
2. **`/v1/models` 的 401 = auth_required_alive** — 不是 down，是需要鉴权
3. **已鉴权探针从 settings.json 读 key** — 不打印，不泄漏
4. **三态返回值** — `ok` / `auth_required_alive` / `error`，下游脚本可按需处理

## DAG 并行化策略

```
N1 (审计探针 + 确认 /health 存在)     ← 无依赖
    │
    ▼
N2 (实现 probe helper + 测试)          ← 依赖 N1 的端点发现
    │
    ▼
N3 (活验证 + 报告)                     ← 依赖 N2 代码
```

串行链（write_scope 重叠于 `~/.solar/harness/tools/`）。

## 节点详情

### N1: 审计 readiness 探针 + 确认 ThunderOMLX health 端点
- **目标**: 找出所有使用未鉴权 `/v1/models` 的探针脚本，确认 `/health` 可用
- **write_scope**: handoff.md + N1-audit.md（不改代码）
- **验收 gate**: `readiness probe root cause found`
- **stop rule**: ThunderOMLX 无 /health 端点 → 需先实现

### N2: 实现 auth-aware readiness probe + 测试
- **目标**:
  1. 新增 `thunderomlx_health_probe.py`：三态判定（ok/auth_required_alive/error）
  2. 从 `~/.omlx/settings.json` 读取 API key，不打印
  3. 同时用 `x-api-key` 和 `Authorization: Bearer` header
  4. 2+ 单元测试覆盖 401-as-alive 和 authenticated-success
- **write_scope**: `tools/thunderomlx_health_probe.py`, `tests/test_thunderomlx_health_probe.py`
- **验收 gate**: `auth aware readiness tests pass`
- **stop rule**: pytest 不通过 → 不进 N3; 任何 key 打印 → 立即修复

### N3: 活验证 + 最终报告
- **目标**: probe status=ok，cache smoke cache_read>0，bad_chars=false，写报告
- **write_scope**: handoff.md + monitor-reports/ 报告
- **验收 gate**: `live readiness and cache smoke verified`
- **stop rule**: probe 返回 error → 调查并修复

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 探针误打印 API key 进日志/报告 | 高 | 代码审查 + 测试覆盖 key 不出现在 stdout |
| 401 一律视为 alive 掩盖真实鉴权配置错误 | 中 | 三态区分：authenticated probe 仍需 200 |
| 下游 monitor 脚本未更新仍用旧探针 | 中 | N1 审计列出所有调用点，N2 逐一更新 |

## 验证命令

```bash
# 单元测试
cd /Users/lisihao/.solar/harness && python3 -m pytest tests/test_thunderomlx_health_probe.py -v

# 活探针
python3 ~/.solar/harness/tools/thunderomlx_health_probe.py --base-url http://127.0.0.1:8002

# Cache smoke (第二次应 cache hit)
curl -s http://127.0.0.1:8002/v1/messages -H "Content-Type: application/json" \
  -H "x-api-key: <key>" -d '...' | python3 -c "import sys,json; u=json.loads(sys.stdin.read()).get('usage',{}); print('cache_read:', u.get('cache_read_input_tokens',0))"
```
