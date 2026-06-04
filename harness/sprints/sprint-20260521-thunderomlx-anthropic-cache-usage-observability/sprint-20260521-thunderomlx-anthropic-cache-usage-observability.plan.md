# Plan — sprint-20260521-thunderomlx-anthropic-cache-usage-observability

## 概述

修复 ThunderOMLX AnthropicProxy 响应 usage 可观测性缺口：内部 `cached_tokens` 已在 scheduler/metrics 层可用，但 Anthropic 兼容 API 的 JSON usage 中 `cache_read_input_tokens` 始终为 0 或缺失。

## 架构变更点

```
scheduler.py (Cache HIT, cached_tokens=N)
    │
    ▼
server.py:5348 → convert_internal_to_anthropic_response(...)
    │  ← 新增: 传入 output.cached_tokens
    ▼
anthropic_utils.py:522 → convert_internal_to_anthropic_response
    │  ← 新增: cached_tokens 参数
    ▼
anthropic_utils.py:592 → AnthropicUsage(cache_read_input_tokens=cached_tokens)
    │
    ├─ 非流式: 直接填入 response.usage
    └─ 流式:   anthropic_utils.py:747 → message_delta usage chunk 增加 cache_read_input_tokens
```

## DAG 并行化策略

```
N1 (审计/复现)          ← 无依赖, 独立
    │
    ▼
N2 (实现 + 测试)        ← 依赖 N1 产出的根因定位
    │
    ▼
N3 (活验证 + 报告)      ← 依赖 N2 代码变更
```

- **N1 → N2 → N3 串行链**：write_scope 有重叠（均涉及 ThunderOMLX/src），不可并行。
- 每个节点有独立 gate 和 acceptance，失败时可精确回滚。

## 节点详情

### N1: 审计 Usage 转换路径 + 复现缺失
- **目标**: 定位 cached_tokens 被丢弃的代码路径，确认复现方法
- **write_scope**: handoff.md + audit report (不改代码)
- **验收 gate**: `usage conversion root cause found`
- **stop rule**: 如无法在 server.py / anthropic_utils.py 中定位转换路径 → 升级到手动检查

### N2: 实现 cached_tokens 透传 + 回归测试
- **目标**: 
  1. `convert_internal_to_anthropic_response` 增加 `cached_tokens` 参数
  2. `AnthropicUsage` 填充 `cache_read_input_tokens`
  3. streaming `message_delta` usage 增加 `cache_read_input_tokens`
  4. 3+ 回归测试覆盖非流式/流式/无缓存三种场景
- **write_scope**: `src/omlx/api/anthropic_utils.py`, `src/omlx/server.py`, `tests/test_anthropic_cache_usage_observability.py`
- **验收 gate**: `usage propagation tests pass`
- **stop rule**: pytest 不通过 → 不能进 N3; OpenAI 兼容路径必须无回归

### N3: 活服务验证 + 最终报告
- **目标**: 
  1. 重启 ThunderOMLX 8002 (如需)
  2. 发送重复 Anthropic prefix 请求
  3. 确认 Run 2 的 `cache_read_input_tokens > 0`
  4. 写入最终中文报告
- **write_scope**: handoff.md + monitor-reports/ 报告
- **验收 gate**: `live usage observability verified`
- **stop rule**: 服务不健康 → 回滚代码 → 报告问题

## 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 流式路径无 usage chunk | 中 | N2 先检查是否有 message_delta usage event；无则文档化 |
| 代码变更影响 OpenAI 路径 | 低 | N2 必须验证 OpenAI 路径无回归 |
| 服务重启后缓存冷 | 低 | N3 需要两次请求：第一次建缓存，第二次命中 |

## 验证命令

```bash
# 单元测试
cd /Users/lisihao/ThunderOMLX && venv/bin/python3 -m pytest tests/test_anthropic_cache_usage_observability.py -v

# 活测试 (第二次应 cache hit)
curl -s http://127.0.0.1:8002/v1/messages -H "Content-Type: application/json" \
  -H "x-api-key: <key>" -d '...' | jq '.usage'
```
