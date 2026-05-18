# Handoff — sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture

## 证据表

| 节点 | 产物 | 验证命令 | 真实输出 | 结果 |
|------|------|----------|----------|------|
| N1 | model_usage.schema.json | `jq '.properties | length' *.model_usage.schema.json` | 11 | PASS |
| N1 | execution_metrics.schema.json | `jq '.required | length' *.execution_metrics.schema.json` | 11 | PASS |
| N1 | footer_fields.md | `grep -c 'Document word count' *.footer_fields.md` | 2 | PASS |
| N2 | state-machine.md | `test -f *.state-machine.md && echo EXISTS` | EXISTS | PASS |
| N2 | state-machine.md | `grep -c 'mermaid\|stateDiagram' *.state-machine.md` | 2 | PASS |
| N3 | compatibility-matrix.md | `grep -cE 'Codex\|module' *.compatibility-matrix.md` | 9 | PASS |
| N4 | fallback-policy.json | `jq '.levels | length' *.fallback-policy.json` | 4 | PASS |
| N4 | fallback-policy.json | `python3 -m json.tool *.fallback-policy.json > /dev/null; echo $?` | 0 | PASS |
| N4 | fallback-policy.md | `grep -cE '^\| ' *.fallback-policy.md` | 44 (≥5) | PASS |
| N5 | planning.html | `wc -c < *.planning.html` | 41571 (≥4096) | PASS |
| N5 | planning.html | `grep -c '系统分层' *.planning.html` | 2 (≥1) | PASS |
| N5 | planning.html | `grep -c '总体策略' *.planning.html` | 2 (≥1) | PASS |
| N5 | planning.html | `grep -c 'model_usage' *.planning.html` | 17 (≥1) | PASS |
| N6 | architecture-adr.md | `test -f *.architecture-adr.md && echo EXISTS` | EXISTS | PASS |
| N6 | architecture-adr.md | `grep -c 'ADR-' *.architecture-adr.md` | 5 | PASS |

## 上游依赖

| 上游来源 | 内容 | S02 消费方式 |
|----------|------|-------------|
| S01 design.md §5-§7 | token 用量 schema 需求 + footer 字段定义 | N1 冻结为 JSON Schema |
| S01 design.md §6 | 真实/估算切换策略 (5-row table) | N4 冻结为 fallback-policy.md + .json |
| S01 plan.md §3 | DAG 布局 + 7 节点分工 | N5 合并渲染到 planning.html |
| S01 plan.md §6 | S03/S04/S05 入参需求 | N7 锚点汇总到本 handoff |
| S01 handoff.md | N1-N5 产物清单 + 验证证据 | N7 交叉引用确认完整 |

## 下游影响

| 下游 Sprint | 消费的 S02 产物 | 用途 |
|-------------|----------------|------|
| S03 (implementation) | model_usage.schema.json | model_usage.jsonl 写入时校验字段类型和约束 |
| S03 (implementation) | execution_metrics.schema.json | report_metrics.py 输出校验，footer 字段提取 |
| S03 (implementation) | state-machine.md | 控制面/数据面状态机代码实现参考 |
| S03 (implementation) | fallback-policy.json | report_metrics.py 中 degrade 级别判断逻辑 |
| S03 (implementation) | compatibility-matrix.md | Codex 集成模块兼容性检查 |
| S04 (verification) | execution_metrics.schema.json | 集成测试断言 schema 符合性 |
| S04 (verification) | model_usage.schema.json | model_usage.jsonl 行校验 |
| S05 (release) | 全部 schema + policy | 发布清单完整性检查 |

## 未闭环项

| # | 项目 | 状态 | 风险 |
|---|------|------|------|
| 1 | footer 字段命名分歧: schema 用 `estimated` / `usage_source`，report_metrics.py 用 `token_usage_is_estimated` / `token_usage_source` | 已记录于 footer_fields.md | S03 实现时需统一 |
| 2 | fallback-policy Level 4 (all_unavailable) 从未实际测试 | 未验证 | S04 集成测试需覆盖 |
| 3 | fallback_reason 枚举值未在 schema 中约束为 enum | 未验证 | S03 可选添加 enum |
| 4 | planning.html 无自定义 CSS | 已知限制 | 不阻塞功能 |
| 5 | N6 architecture-adr.md 中 ADR-001..ADR-005 的状态均为 proposed | 待 S03 实现后更新 | 低风险 |

## S03 入参锚点

S03 实现阶段必须读取以下 S02 产物：

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S02-SCHEMA-MODEL | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.model_usage.schema.json` | `build_model_usage_event()` 输出校验 |
| S02-SCHEMA-METRICS | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.execution_metrics.schema.json` | `build_execution_metrics()` 输出校验 |
| S02-FOOTER | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.footer_fields.md` | footer 4 字段渲染模板 |
| S02-STATEMACHINE | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.state-machine.md` | 控制面/数据面状态流转实现参考 |
| S02-FALLBACK | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.fallback-policy.json` | degrade 级别判断 + fallback_reason 枚举 |
| S02-COMPAT | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.compatibility-matrix.md` | Codex 模块兼容性实现 |

## S04 入参锚点

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S02-SCHEMA-METRICS | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.execution_metrics.schema.json` | 集成测试断言: jsonschema.validate() |
| S02-SCHEMA-MODEL | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.model_usage.schema.json` | model_usage.jsonl 行校验 |
| S02-FALLBACK | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.fallback-policy.json` | 至少验证 Level 1-3 fallback 路径 |

## S05 入参锚点

| 锚点 ID | 文件路径 | 消费方式 |
|---------|---------|---------|
| S02-ALL-SCHEMAS | model_usage + execution_metrics schema | 发布前 schema 符合性终检 |
| S02-FALLBACK | fallback-policy.json | 发布文档引用 |
| S02-PLANNING | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.planning.html` | 架构全景文档 |
| S02-ADR | `sprints/sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.architecture-adr.md` | 发布时 ADR 状态更新为 accepted |

## 命令清单

```bash
# N1 验证
jq '.properties | length' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.model_usage.schema.json
jq '.required | length' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.execution_metrics.schema.json
grep -c 'Document word count' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.footer_fields.md

# N2 验证
grep -c 'mermaid\|stateDiagram' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.state-machine.md

# N3 验证
grep -cE 'Codex\|module' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.compatibility-matrix.md

# N4 验证
jq '.levels | length' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.fallback-policy.json
python3 -m json.tool sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.fallback-policy.json > /dev/null
grep -cE '^\| ' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.fallback-policy.md

# N5 验证
wc -c < sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.planning.html
grep -c '系统分层' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.planning.html
grep -c '总体策略' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.planning.html
grep -c 'model_usage' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.planning.html

# N6 验证
grep -c 'ADR-' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.architecture-adr.md

# N7 验证 (本文件)
grep -c '^## ' sprint-20260518-p0-deepresearch-real-backend-execution-and-evidence-closeou-s02-architecture.handoff.md
```
