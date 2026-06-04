# Plan: S03 Core-Runtime (Mirage Context Access Plane)

## Wave 1: Adapter Surface

1. `cocoindex_adapter.py`
2. `understand_anything_adapter.py`
3. `mirage_search.py` source registration

## Wave 2: Unified Context Fusion

1. extend `solar-unified-context.py`
2. add source layering / dedupe / ranking
3. preserve legacy source order fallback

## Wave 3: Runtime Injection + Verifier

1. extend `runtime_context_inject.py`
2. extend context sidecar
3. implement `verifier.context_usage`

## Wave 4: Verification

1. doctor/health for mirage/coco/ua
2. source_type surfaced in search
3. sidecar / evidence ledger replay

## Stop Rules

1. 不追求 shell-native FUSE 幻觉。
2. 不允许把 degraded source 伪装成正常命中。
3. 任何改动若会破坏现有 mirage_path/qmd/solar_db 主链，必须停下来写 tradeoff。

