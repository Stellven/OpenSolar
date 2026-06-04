# Plan — Tech Hotspot Radar Social Browser Backend for X S01

gate: `sprint-20260525-tech-hotspot-radar-social-browser-backend-for-x-大咖监控-s01-requirements:passed`
hard_blocker: 上游 sprint-20260525-browser-agent-global-operator-cutover 必须 PASS 才能进 S02+

## 0. DAG

```
            ┌─→ N1_backend_operator_ratelimit (O1+O2+O3) glm-5.1 ─┐
(无上游) ───┼─→ N2_extraction_dedup_downstream (O4+O5+O6) glm-5.1 ─┼─→ N4_join sonnet
            └─→ N3_cli_webui_blocker (O7+O8+O9) glm-5.1            ─┘
```

## 1. 节点验收

| 节点 | 验收 |
|------|------|
| **N1** | O1+O2+O3 ≥9 验收 (Backend 4 顺序 + Browser 6 capabilities + Rate limiting 5 子项) |
| **N2** | O4+O5+O6 ≥9 验收 (post 11 字段 + dedup 2 种 key + Downstream 10 步链路) |
| **N3** | O7+O8+O9 ≥9 验收 (CLI 2 命令 + WebUI 7 指标 + Hard blocker 显式) |
| **N4** | traceability 12 字段 + outcomes=10 + non_goals_aggregate ≥10 + hard_blocker 显式记录 + S02 启动等待 |

## 2. Stop Rules

- 不实施代码
- 不真跑 browser agent (上游未完成, hard blocker)
- 不绕 X 风控/登录
- 不新增重复 Browser / ThunderOMLX 实例
- 不打印 X cookie/token
- 不用乐观词

## 3. 给下游 S02

N4 traceability 必须明示 hard blocker: `s02_architecture_blocked_until: sprint-20260525-browser-agent-global-operator-cutover:passed`
