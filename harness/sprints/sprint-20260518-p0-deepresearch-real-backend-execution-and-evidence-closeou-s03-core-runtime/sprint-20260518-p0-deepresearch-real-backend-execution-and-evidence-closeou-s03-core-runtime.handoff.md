# Handoff — sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s03-core-runtime

## 证据表

| 节点 | 产物 | 验证命令 | 真实输出 | 结果 |
|------|------|----------|----------|------|
| N2 | fallback_policy.py | `python3 -c "from harness.lib.research.fallback_policy import FallbackLevel; print(len(FallbackLevel))"` | 4 | PASS |
| N2 | fallback_policy.py | `python3 -c "from harness.lib.research.fallback_policy import decide_fallback; print(decide_fallback(True,True,True))"` | L1_FULL_REAL | PASS |
| N2 | fallback_policy.py | `python3 -c "from harness.lib.research.fallback_policy import decide_fallback; print(decide_fallback(False,False,False))"` | L4_TOKENIZER_DECLARED | PASS |
| N2 | fallback_policy.py | `grep -c 'FallbackLevel' fallback_policy.py` | 12 | PASS |
| N4 | schema_adapter.py | `python3 -c "from harness.lib.research.schema_adapter import normalize_to_s02; print(normalize_to_s02({'token_usage_source':'provider_usage_ledger'}))"` | {'usage_source': 'provider_usage_ledger'} | PASS |
| N4 | schema_adapter.py | `grep -c 'normalize_to_s02\|denormalize_from_s02\|validate_' schema_adapter.py` | 4 | PASS |
| N4 | schema_adapter.py | jsonschema.ValidationError on bad data | raises correctly | PASS |
| N5 | report_metrics.py | `grep -cE 'usage_source\|estimated\|fallback_reason\|token_usage_source\|token_usage_is_estimated' report_metrics.py` | 24 (≥5) | PASS |
| N5 | report_metrics.py | build_execution_metrics output keys | usage_source ✓ estimated ✓ fallback_reason ✓ | PASS |
| N5 | report_metrics.py | footer 4-field text | Document word count / Total token consumption / Token usage source / Token usage estimated ✓ | PASS |
| N8 | test_real_vs_estimated_switch.py | `pytest tests/research/integration/ -q` | 9 passed in 0.06s, exit 0 | PASS |
| N8 | test_footer_fields_render.py | same pytest run | included in 9 passed | PASS |
| N8 | test_real_vs_estimated_switch.py | L1/L2/L3 coverage | test_l1 + test_l2 + test_l3 = 3 tests | PASS |

## 上游 S02 锚点

| S02 产物 | S03 消费节点 | 消费方式 |
|----------|-------------|---------|
| fallback-policy.json (4-level degradation) | N2 | FallbackLevel 枚举 + decide_fallback() 决策逻辑 |
| model_usage.schema.json | N4 | validate_model_usage_line() 校验目标 |
| execution_metrics.schema.json | N4 | validate_execution_metrics() 校验目标 |
| footer_fields.md (4-field contract) | N5 | render_execution_metrics_section() footer 渲染模板 |

## S04 入参锚点

S04 (verification) 必须读取以下 S03 产物进行集成测试：

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S03-FALLBACK | `/Users/sihaoli/Solar/harness/lib/research/fallback_policy.py` | 集成测试: 导入 FallbackLevel + decide_fallback, 验证 4 级切换 |
| S03-ADAPTER | `/Users/sihaoli/Solar/harness/lib/research/schema_adapter.py` | 集成测试: jsonschema.validate 对 S02 schema 校验 |
| S03-METRICS | `/Users/sihaoli/Solar/harness/lib/research/report_metrics.py` | 集成测试: build_execution_metrics S02 字段 + footer 4 字段 |
| S03-TESTS | `/Users/sihaoli/Solar/tests/research/integration/` | 已有 9 个测试; S04 可扩展或重跑验证 |
| S02-SCHEMA-MODEL | `sprints/...model_usage.schema.json` | schema_adapter 校验所需 schema 文件 |
| S02-SCHEMA-METRICS | `sprints/...execution_metrics.schema.json` | schema_adapter 校验所需 schema 文件 |

## S05 入参锚点

S05 (release) 必须读取以下 S03 产物进行发布终检：

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S03-ALL-RUNTIME | fallback_policy + schema_adapter + report_metrics | 发布前功能回归: pytest 重跑 |
| S03-TESTS | tests/research/integration/ | 发布清单: 9 tests 必须全 pass |
| S03-FALLBACK | fallback_policy.py | 发布文档: FallbackLevel 枚举值 + fallback_reason 列表 |
| S03-METRICS | report_metrics.py | 发布清单: footer 4 字段精确文本对照 |

## 未闭环项

| # | 项目 | 状态 | 风险 |
|---|------|------|------|
| 1 | 字段命名分歧: schema 用 `usage_source`/`estimated`, report_metrics.py 旧代码用 `token_usage_source`/`token_usage_is_estimated`; schema_adapter 提供映射但消费方需显式调用 | 已有 adapter | S04 需验证映射正确 |
| 2 | fallback_reason 在 report_metrics.py 中默认为 `None` 或 `"no_provider_usage"`, 未接入 fallback_policy.FallbackLevel 的完整枚举值 | 已有默认值 | S04 可增强 |
| 3 | L4 (TOKENIZER_DECLARED) 在 decide_fallback 中有路径但在 N8 集成测试中未覆盖 | 未测试 | S04 需补充 |
| 4 | schema_adapter.py 的 validate 函数需 caller 提供 schema_path, 无内置默认路径 | 设计如此 (DoD #2) | 不阻塞 |

## 命令清单

```bash
# N2 验证
python3 -c "from harness.lib.research.fallback_policy import FallbackLevel, decide_fallback; print(len(FallbackLevel), decide_fallback(True,True,True), decide_fallback(False,False,False))"

# N4 验证
python3 -c "from harness.lib.research.schema_adapter import normalize_to_s02, denormalize_from_s02; print(normalize_to_s02({'token_usage_source':'x'}), denormalize_from_s02({'usage_source':'x'}))"
python3 -c "
from harness.lib.research.schema_adapter import validate_model_usage_line, validate_execution_metrics
import jsonschema
try: validate_model_usage_line({'bad':1}, schema_path='/Users/sihaoli/.solar/harness/sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.model_usage.schema.json')
except jsonschema.ValidationError: print('ValidationError raised OK')
"

# N5 验证
grep -cE 'usage_source|estimated|fallback_reason|token_usage_source|token_usage_is_estimated' /Users/sihaoli/Solar/harness/lib/research/report_metrics.py

# N8 验证
python3 -m pytest tests/research/integration/ -q

# N10 验证 (本文件)
grep -c '^## ' s03-core-runtime.handoff.md
```
