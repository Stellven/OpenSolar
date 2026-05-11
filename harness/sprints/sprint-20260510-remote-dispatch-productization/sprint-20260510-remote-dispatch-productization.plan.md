# Plan — Solar Remote Dispatch Productization

## Strategy

先把远端执行产品化的硬边界做实：配置驱动、manifest checksum、幂等、状态回收、pane submit ack、parent_ready_check 收口、测试套。UI 可以先给 CLI/status JSON，再补页面。

## DAG

- N1: Remote config + doctor + manifest/checksum.
- N2: Dispatch idempotency + pull/reconcile.
- N3: Graph dispatcher pane submit reliability + ack evidence.
- N4: Product test suite.
- N5: Status/docs/UI surface.
- N6: Mac mini e2e smoke + final handoff.

## Gate

N6 是最终 gate，只有 N1-N5 全部通过后才执行。Evaluator 必须复跑关键测试，不能只看 handoff。
