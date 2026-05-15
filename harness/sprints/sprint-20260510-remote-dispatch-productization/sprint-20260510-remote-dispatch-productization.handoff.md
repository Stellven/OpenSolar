# Handoff — sprint-20260510-remote-dispatch-productization

Builder/Controller: Codex + Solar Harness remote smoke
Round: closeout

## Summary

`solar-remote-dispatch` 已从 beta 链路补齐为产品级可验证闭环：配置、doctor、manifest/checksum、幂等、pull、bash CLI 测试、README、Mac mini remote-only e2e 均已完成。

## D1-D10 结果

| Done | 状态 | 证据 |
|---|---|---|
| D1 doctor --json | PASS | 真实 Mac mini doctor 返回 ok，包含 ssh/rsync/harness/tmux/panes/version/last_sync |
| D2 config-driven | PASS | 支持 config/env/--host/--user/--path，无生产硬编码目标 |
| D3 checksum before wake | PASS | 真实 dispatch 先 rsync，再 verify remote checksums，再 wake |
| D4 idempotent/force | PASS | core tests 覆盖 duplicate/force，dispatch 记录 forced flag |
| D5 pull/reconcile | PASS | `pull` 从 Mac mini 拉回 status/events/handoff/eval，并标 `pulled_from` |
| D6 pane submit | PASS | graph submit/lease tests 通过 |
| D7 parent_ready_check | PASS | parent closeout tests 通过 |
| D8 test suite | PASS | `tests/integrations/test-remote-dispatch-productization.sh` 生成 report |
| D9 Mac mini e2e | PASS | remote-only smoke 在 Mac mini builder/evaluator 闭环为 passed |
| D10 README/docs | PASS | `README-remote-dispatch.md` 已写配置、dispatch、pull、恢复、安全边界 |

## 关键修复

- 修复 `solar-remote-dispatch doctor --json` 的 jq split bug，改用 Python JSON 组装，避免值里包含 `: ` 时崩溃。
- 修复 bash wrapper 调用 `remote_dispatch.py verify` 的参数顺序错误；该 bug 在真实 dispatch 时被 checksum gate 暴露。
- 统一 `--path` 在 bash wrapper 与 Python core 的语义，doctor/verify/pull 都能使用非默认 remote home。
- 新增 bash CLI subprocess 测试，覆盖 doctor JSON 与 dispatch verify-before-wake 路径。
- 新增 integration report 脚本，统一输出 report.md/report.json。

## Mac mini E2E

有效 smoke:

- `sprint-20260510-remote-dispatch-productization-remote-only-smoke`
- remote: `lisihao@100.122.223.55`
- hostname: `lisihaodeMac-mini-3.local`
- final status: `passed / eval_passed / done`
- pulled evidence:
  - `sprint-20260510-remote-dispatch-productization-remote-only-smoke.handoff.md`
  - `sprint-20260510-remote-dispatch-productization-remote-only-smoke.eval.md`
  - `sprint-20260510-remote-dispatch-productization-remote-only-smoke.eval.json`
  - `sprint-20260510-remote-dispatch-productization-remote-only-smoke.status.json`

注意：第一次 `...-smoke` 被 MacBook 本地 coordinator 抢跑，handoff hostname 是 MacBook，不计入 D9。最终采用 `drafting_held + remote wake promote` 的 `remote-only-smoke` 避免本地污染。

## 验证命令

```bash
bash -n /Users/lisihao/.solar/bin/solar-remote-dispatch
python3 -m pytest /Users/lisihao/.solar/harness/tests/remote/test_remote_dispatch_core.py /Users/lisihao/.solar/harness/tests/remote/test_remote_dispatch_cli.py -q
python3 -m pytest /Users/lisihao/.solar/harness/tests/graph/test_graph_dispatch_submit.py /Users/lisihao/.solar/harness/tests/graph/test_parent_ready_closeout.py -q
/Users/lisihao/.solar/harness/tests/integrations/test-remote-dispatch-productization.sh
SOLAR_REMOTE_USER=lisihao SOLAR_REMOTE_HOST=100.122.223.55 SOLAR_REMOTE_PATH=/Users/lisihao /Users/lisihao/.solar/bin/solar-remote-dispatch doctor --json
```

## Evidence Paths

- `/Users/lisihao/.solar/harness/reports/remote-dispatch-productization/20260511T004504Z/report.json`
- `/Users/lisihao/.solar/harness/reports/remote-dispatch-productization/20260511T004504Z/e2e-mac-mini.json`
- `/Users/lisihao/.solar/harness/README-remote-dispatch.md`
- `/Users/lisihao/.solar/harness/tests/remote/test_remote_dispatch_cli.py`
- `/Users/lisihao/.solar/harness/tests/integrations/test-remote-dispatch-productization.sh`
