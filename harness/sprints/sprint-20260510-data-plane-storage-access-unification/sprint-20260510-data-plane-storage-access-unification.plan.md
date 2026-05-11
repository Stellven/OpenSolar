# Plan — Solar Data Plane Storage And Access Unification

## Strategy

严格按“先盘点、再 manifest、再安全 copy/link、再修访问层、再刷新索引、最后备份对账”的顺序执行。任何会破坏旧路径的动作必须停在 dry-run。

## DAG

- S1: Source library scaffold + manifest generator.
- S2: Safe raw-to-sources migration/copy/link command.
- S3: Mirage mount repair + doctor.
- S4: QMD reindex/reconcile.
- S5: MinerU idle extraction over canonical papers.
- S6: Drive mirror checksum + final evidence.

## Gate

S6 依赖 S1-S5。Evaluator 必须抽样验证 source checksum、Mirage roots、QMD hit、MinerU background policy 和 Drive mirror 状态。
