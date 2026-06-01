# Plan — sprint-20260521-thunderomlx-anthropic-prefix-cache

## 概述

修复 ThunderOMLX AnthropicProxy 路径无条件禁用 Block Prefix Cache 的问题。当前 pane4/Claude 兼容请求经 `/v1/messages` 路由时，`_run_local_anthropic_inference()` 硬编码 `disable_prefix_cache: True`，导致重复 system prompt 无法复用前缀缓存，prefill 开销不变。

## 问题根因

```
server.py:5198-5201  _run_local_anthropic_inference()
  chat_kwargs = {
      ...
      "disable_prefix_cache": True,   ← 无条件硬编码
  }
      ↓
engine/batched.py:628  add_request(disable_prefix_cache=True)
      ↓
scheduler.py:3565  request.prompt_cache = None
                   request.cached_tokens = 0
                   → 强制全量 prefill，每次请求
```

历史原因：Claude Code 发出 haiku/sonnet 重叠请求时，prefix reuse 导致乱码多语言 token 流（BAK 文件记录 2026-05-20）。

## 架构变更

```
                    ┌──────────────────────────────────┐
                    │  settings_v2.py (CloudSettingsV2) │
                    │  + anthropic_prefix_cache_enabled │
                    │    bool = False (safe default)    │
                    └──────────────┬───────────────────┘
                                   │ getattr chain
                                   ▼
            ┌──────────────────────────────────────────┐
            │  server.py: _run_local_anthropic_inference │
            │  disable_prefix_cache = NOT(setting)      │
            │                                          │
            │  False(default) → disable=True (安全)     │
            │  True(opt-in)  → disable=False (启用)     │
            │  None/missing  → disable=True (安全)      │
            └──────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
             scheduler.py                    scheduler.py
          prompt_cache=None              prompt_cache=cached
          (full prefill)                 (prefix reuse)
```

## DAG 并行化策略

```
N1 (审计/复现 before)     ← 无依赖，独立
    │
    ▼
N2 (实现 + 测试)          ← 依赖 N1 的根因定位
    │
    ▼
N3 (活验证 + 报告)        ← 依赖 N2 代码变更
```

- **N1 → N2 → N3 串行链**：write_scope 有重叠（ThunderOMLX/src），不可并行。
- 每节点独立 gate，失败可精确回滚。

## 节点详情

### N1: 审计 AnthropicProxy 请求流 + 采集 before metrics
- **目标**: 定位 disable_prefix_cache 硬编码位置，采集 3 次重复请求的 cache_read=0 证据
- **write_scope**: handoff.md + N1-before.md（不改代码）
- **验收 gate**: `before evidence and root cause found`
- **stop rule**: 无法定位代码路径 → 升级

### N2: 实现 settings 开关 + 替换硬编码 + 回归测试
- **目标**:
  1. `settings_v2.py` 新增 `anthropic_prefix_cache_enabled: bool = False`
  2. `server.py` 用 `not getattr(...)` 链替换硬编码 `True`
  3. 8+ 单元测试覆盖所有分支
- **write_scope**: `settings_v2.py`, `server.py`, `tests/test_anthropic_prefix_cache.py`
- **验收 gate**: `minimal patch and tests complete`
- **stop rule**: pytest 不通过 → 不进 N3; OpenAI 路径必须无回归

### N3: 活验证 + 最终报告
- **目标**: pane4 等价请求验证 HTTP 200 + bad_chars=false + 写入 before/after 中文报告
- **write_scope**: handoff.md + monitor-reports/ 报告
- **验收 gate**: `after validation and final report written`
- **stop rule**: 服务不健康 → 回滚 → 报告

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 乱码根因未解决，opt-in 可能重现 | 高 | 默认 False，opt-in 仅供受控测试；报告明确警告 |
| SSD 写放大（cache 写入但不读回） | 低 | 后续可优化 disable 时跳过写入 |
| settings.json 旧版本无此字段 | 低 | Pydantic 默认值 False 自动生效 |

## 验证命令

```bash
# 确认代码变更
grep -n "anthropic_prefix_cache_enabled" /Users/lisihao/ThunderOMLX/src/omlx/settings_v2.py
grep -n "anthropic_prefix_cache_enabled" /Users/lisihao/ThunderOMLX/src/omlx/server.py

# 单元测试
cd /Users/lisihao/ThunderOMLX && venv/bin/python3 -m pytest tests/test_anthropic_prefix_cache.py -v

# 活测试
curl -s -X POST http://127.0.0.1:8002/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: omlx-oo5ccf7zctkfvb8u" \
  -d '{"model":"claude-3-5-sonnet-latest","max_tokens":80,"system":"你是一个有用的AI助手。请用中文回答。","messages":[{"role":"user","content":"介绍一下你自己。"}]}' \
  | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); u=d.get('usage',{}); print('cache_read:', u.get('cache_read_input_tokens',0))"
```
