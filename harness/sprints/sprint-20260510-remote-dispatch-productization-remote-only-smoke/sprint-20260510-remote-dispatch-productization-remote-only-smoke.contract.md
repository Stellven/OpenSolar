---
id: sprint-20260510-remote-dispatch-productization-remote-only-smoke
title: Remote-Only Dispatch Productization Smoke
priority: P0
lane: verification
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: mac-mini-solar-harness
---

# Contract — Remote-Only Dispatch Productization Smoke

## Intent
验证本地 `solar-remote-dispatch` 可以把一个未被 MacBook 本地 coordinator 消费的 sprint 发到 Mac mini，并由 Mac mini 的 Solar Harness builder/evaluator 完成闭环。

## Done
- D1: builder 必须在 Mac mini 上记录 `hostname`、`pwd`、`date -u`。
- D2: builder 写 `~/.solar/harness/sprints/sprint-20260510-remote-dispatch-productization-remote-only-smoke.handoff.md`，包含关键 stdout。
- D3: builder 将 status 更新为 `reviewing` / `implementation_complete`。
- D4: evaluator 写 `eval.md` 和 `eval.json`。
- D5: evaluator 将 status 标为 `passed`。

## Verify Commands
```bash
hostname
pwd
date -u +%Y-%m-%dT%H:%M:%SZ
test -f ~/.solar/harness/sprints/sprint-20260510-remote-dispatch-productization-remote-only-smoke.contract.md
```

## Constraints
- 不修改源码。
- 不访问 secrets。
- 不下载依赖。
- 若 hostname 不是 Mac mini，不得通过。
