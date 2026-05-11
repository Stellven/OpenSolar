# Eval — sprint-20260510-remote-dispatch-productization

Evaluator: Codex closeout verification
Round: 4
Date: 2026-05-11T00:52:00Z

## 总判定: PASS

之前 FAIL 的四项已经复核修复：D1 doctor jq crash、D8 bash CLI 覆盖缺口、D9 Mac mini e2e、D10 README/docs。D1-D10 全部达成。

## Done 条件逐条

| # | 条件 | 判定 | 证据 |
|---|---|---|---|
| D1 | `doctor --json` 报告 remote target/ssh/rsync/harness/tmux/panes/version/last_sync | PASS | 真实 Mac mini doctor 返回 `ok: true`、panes=10 |
| D2 | config/env/flag 驱动，无生产硬编码 host | PASS | `--host`、`--user`、`--path` 已支持；缺配置 JSON 错误可解释 |
| D3 | manifest/checksum before wake | PASS | 真实 dispatch 输出 checksum `ok: true` 后才 wake |
| D4 | duplicate/force idempotency | PASS | unit tests 覆盖 duplicate 与 forced redispatch |
| D5 | pull status/events/graph/handoff/eval，标 source host | PASS | pull 回 5 个 artifact，status 含 `pulled_from.host=100.122.223.55` |
| D6 | pane submit ack + lease release | PASS | graph submit tests 通过 |
| D7 | parent sprint 只经 parent_ready_check closeout | PASS | parent ready tests 通过 |
| D8 | fake transport + failure path + bash CLI 覆盖 | PASS | integration report status ok |
| D9 | Mac mini e2e smoke passed | PASS | remote-only smoke 由 Mac mini builder/evaluator 完成并 pull 回本地 |
| D10 | README/status docs | PASS | `README-remote-dispatch.md` 覆盖配置、派发、pull、恢复、安全 |

## 关键 stdout

```text
doctor target: lisihao@100.122.223.55
doctor ok: true
remote panes: 10
remote smoke hostname: lisihaodeMac-mini-3.local
remote smoke final: passed / eval_passed / done
tests remote: 27 passed
tests graph: 18 passed
integration report: ok
```

## 风险/备注

- 第一次 smoke 被本地 MacBook 抢跑，已明确作废，不计入通过证据。
- remote-only smoke 中 builder 漏写 `handoff_to=evaluator`，由 controller 做了路由字段归一化；eval/pass 仍由 Mac mini evaluator 独立完成。
- 当前产品级目标是 Mac mini remote target，不代表任意云主机已支持。

## 结论

本 sprint 可以从 failed 改为 passed。远端派发现在具备可配置、可验证、可恢复、可审计的最小产品级闭环。
