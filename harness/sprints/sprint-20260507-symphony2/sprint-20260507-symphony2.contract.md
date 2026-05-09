---
name: symphony-sprint-2-workspace-hooks
description: Symphony Sprint 2 — workspace 4 hook 生命周期 + 强隔离 + Sprint 1 D6 prerequisites
triggers: [pm-manual]
---

# Sprint Contract — sprint-20260507-symphony2
Created: 2026-05-07T14:42:08Z
Status: active
Phase: spec
Project: /Users/sihaoli

## When to Use

### Use When
- 需要为 Symphony Workspace 引入生命周期 hook 能力 (pre/post claim + pre/post release)
- 需要修复 Sprint 1 D6 留下的 CLAUDECODE guard 环境冲突 (阻塞真实执行验证)
- 需要把 hook 执行环境与 host env 隔离 (token 不泄漏)

### Do NOT Use When
- 想引入容器/namespace 强隔离 (本 sprint 仅 env-level)
- 想把 hook 当 LLM/Codex agent 调用 (hook 只是 shell 命令)
- 想替换 coordinator.sh 主循环 (本 sprint 是增量)

## Requirements

在 Sprint 1 (workflow-loader/scheduler/issue-adapter/workspace-manager/runner) 之上,
为 Symphony workspace 引入 4 个标准生命周期 hook + 强隔离执行模型:

1. **WORKFLOW front matter 扩展 hooks: 段** — workflow-loader.py 解析新增字段
2. **workspace-manager.sh 接入 4 个 hook 调用点** — create / clean 各 2 个
3. **强隔离 (受限环境执行)** — env 白名单 + token 清空 + timeout 兼容
4. **修复 D6 CLAUDECODE guard** — 改用 SOLAR_SYMPHONY_DRY_RUN=1 标记 dry-run
5. **测试覆盖** — 8 用例 (4 hook + 1 隔离 + 1 白名单 + 2 D6)
6. **文档 + ADR 更新** — Hook Lifecycle Design ≥ 200 字

详细 product brief: `~/.solar/harness/sprints/sprint-20260507-symphony2.product-brief.md`

## Process

1. **Spec**: 已完成 (本合约 + product-brief.md)
2. **Plan**: builder 读 brief 后产出 D1-D8 实现顺序
3. **Build**: builder=glm-5.1 主, deepseek-v3 fallback (hook 边界条件)
4. **Test**: 8 测试用例全 PASS + Sprint 1 14/14 无回归
5. **Review**: evaluator=deepseek-r1 红队 (重点 env 泄漏 + race)
6. **Ship**: planner 双 Gate (Day 2 / Day 4) 主持判定

## Definition of Done

- [ ] D1: workflow-loader.py 解析 hooks: 段 (4 lifecycle + global_timeout_ms + on_failure)
  <!-- verify: cmd="python3 ~/.solar/harness/lib/symphony/workflow-loader.py --validate ~/.solar/harness/templates/WORKFLOW.solar.md" expected_exit=0 output_pattern="hooks.*ok|valid" -->

- [ ] D2: workspace-manager.sh create 调用 pre_claim / post_claim hook (有则执行, 无则跳过)
  <!-- verify: cmd="bash ~/.solar/harness/test-symphony-hooks.sh --case pre_claim_post_claim" expected_exit=0 output_pattern="PASS" -->

- [ ] D3: workspace-manager.sh clean 调用 pre_release / post_release hook
  <!-- verify: cmd="bash ~/.solar/harness/test-symphony-hooks.sh --case pre_release_post_release" expected_exit=0 output_pattern="PASS" -->

- [ ] D4: hooks.sh 的 run_hook 实现强隔离 (token 清空 + env 白名单 + timeout)
  <!-- verify: cmd="bash ~/.solar/harness/test-symphony-hooks.sh --case env_isolation" expected_exit=0 output_pattern="ZHIPU_AUTH_TOKEN.*empty.*PASS" -->

- [ ] D5: env_allow 白名单扩展 (hooks.<name>.env_allow=["FOO"] 后 hook 内可见 FOO)
  <!-- verify: cmd="bash ~/.solar/harness/test-symphony-hooks.sh --case env_allow_extension" expected_exit=0 output_pattern="PASS" -->

- [ ] D6: 修复 D6 CLAUDECODE guard 环境冲突 (--dry-run 在当前 Claude Code 内 exit 0)
  <!-- verify: cmd="bash ~/.solar/harness/lib/symphony/runner.sh --dry-run --sprint sprint-20260507-symphony2" expected_exit=0 output_pattern="dry.run.*ok|complete" -->

- [ ] D7: Sprint 1 14/14 无回归 (issue-adapter 3 + scheduler 5 + workspace 5 + no-live-pane-mutation 1)
  <!-- verify: cmd="bash -c 'cd ~/.solar/harness && for t in test-symphony-issue-adapter.sh test-symphony-scheduler-dry-run.sh test-symphony-workspace.sh test-symphony-no-live-pane-mutation.sh; do bash $t || exit 1; done; echo ALL_PASS'" expected_exit=0 output_pattern="ALL_PASS" -->

- [ ] D8: 文档 + ADR (symphony-integration-adr.md 含 Hook Lifecycle Design ≥ 200 字 + WORKFLOW.solar.md 4 hook 示例)
  <!-- verify: cmd="awk '/Hook Lifecycle Design/,/^## /{print}' ~/.solar/harness/docs/symphony-integration-adr.md | wc -w" expected_exit=0 output_pattern="^[2-9][0-9]{2,}|^[1-9][0-9]{3,}" -->

## Scope

### In Scope
- `~/.solar/harness/lib/symphony/hooks.sh` (新建)
- `~/.solar/harness/lib/symphony/workspace-manager.sh` (修改, 接入 hook)
- `~/.solar/harness/lib/symphony/runner.sh` (修改, D6 guard)
- `~/.solar/harness/lib/symphony/workflow-loader.py` (修改, 解析 hooks:)
- `~/.solar/harness/templates/WORKFLOW.solar.md` (修改, 含 hooks: 示例)
- `~/.solar/harness/test-symphony-hooks.sh` (新建)
- `~/.solar/harness/test-symphony-d6-guard.sh` (新建)
- `~/.solar/harness/docs/symphony-integration-adr.md` (扩展 §Hook Lifecycle Design)

### Out of Scope
- Linear webhook hook (留 Sprint 3)
- 容器/chroot/namespace 隔离
- coordinator.sh 主循环改动
- 旧 sprint 强制接 hook (新 WORKFLOW 用 hooks: 即可)
- hook 间状态传递机制 (通过文件通信即可)

## Red Flags

- **No mock/stub/TODO**: `grep -rE 'TODO|FIXME|mock|stub|模拟'` in implementation files must return empty
- **No hardcoded secrets**: `grep -rE 'password|secret|token|api.key' --include='*.sh' --include='*.ts' --include='*.py'` must return empty (excluding template placeholders)
- **No temp artifacts**: 任何 hook 日志写到 `~/.solar/harness/sprints/<sid>.hook-<name>.log`, 不放 /tmp
- **No live pane mutation**: hook 不能 `tmux send-keys` / `kill-pane` / `respawn-pane` (继承 Sprint 1 §Forbidden Actions)

## Constraints

- 7 天硬上限, 工期 > 8 天必须暂停重估
- bash 脚本必须 `bash -n` 通过, 兼容 bash 5.x (homebrew /opt/homebrew/bin/bash)
- env 隔离白名单默认: SPRINT_ID, WORKSPACE_DIR, WORKSPACE_ROOT, SOLAR_SYMPHONY_HOOK_NAME, PATH
- 显式清空所有 *_TOKEN / *_KEY env (含 ZHIPU_AUTH_TOKEN, ANTHROPIC_AUTH_TOKEN, ZHIPU_API_KEY)
- timeout 用 perl alarm 或 gtimeout (macOS 兼容), 超时 SIGTERM → 5s 后 SIGKILL
- D6 修复**第一天必须完成**, 否则 P1 真实执行测试无法运行
- 任何 Sprint 1 测试 (14/14) 出现回归 → 立即 STOP

## Implementation Files

> Builder fills in after completion

## Evaluation Dimensions

1. **Functional completeness**: D1-D8 全部 PASS, verify 命令逐项验证
2. **Code quality**: hook 执行的 race condition / SIGKILL 兼容 / 退出码传递
3. **Contract compliance**: 范围严格在 In Scope 内, 不偷偷扩 (Linear / 容器 / coordinator 改动)
4. **Maintainability**: hooks.sh 函数命名 (run_hook / sanitize_env / wait_with_timeout)
5. **Security**: token/key 不在 hook 子进程可见, env_allow 白名单不可绕过
6. **Backward compat**: Sprint 1 14/14 无回归

## Crew

- builder_main: glm-5.1
- builder_fallback: deepseek-v3 (hook 边界 / timeout / signal)
- evaluator: deepseek-r1 (红队: env 泄漏 + race + 退出码)
- gate_judge: planner (Day 2 Gate A, Day 4 Gate B)

## Gates

- **Gate A (Day 2)**: D1 + D2 + D6 PASS → 进入 Day 3-4
- **Gate B (Day 4)**: D1-D6 PASS + 5+ test cases PASS → 进入 Day 5-7 (文档/ADR/审判官)
- **Gate B 失败**: Day 5-7 收缩到必过项, 文档/ADR 后移
