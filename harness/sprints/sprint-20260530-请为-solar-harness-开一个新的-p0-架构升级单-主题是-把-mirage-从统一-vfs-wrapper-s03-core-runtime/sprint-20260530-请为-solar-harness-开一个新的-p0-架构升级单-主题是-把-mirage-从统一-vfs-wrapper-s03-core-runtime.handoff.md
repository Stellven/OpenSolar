# Handoff — sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime
Builder: 建设者化身
Round: 2

## 变更文件
- `lib/cocoindex_adapter.py`, `tools/cocoindex_adapter.py`: 新增 CocoIndex adapter surface；优先调用真实 `solar-harness coco query`/`SOLAR_COCO_QUERY_CMD`，不可用时走只读代码扫描 fallback，并显式标记 degraded。
- `lib/understand_anything_adapter.py`, `tools/understand_anything_adapter.py`: 新增 understanding artifact adapter；读取 `SOLAR_UNDERSTANDING_STORE` / `~/.solar/understanding` artifact store 并输出 normalized hits。
- `lib/mirage_search.py`, `tools/mirage_search.py`: 注册 `source_type=cocoindex/understanding`，加入 source layer、dedupe、ranking、source_counts、lineage_refs、source_hash_refs。
- `lib/solar-unified-context.py`, `tools/solar-unified-context.py`: 扩展 retrieve 为多源 fusion，支持 sources/layers/task_kind/limit/token_budget，保留 mirage_path/qmd/solar_db fallback。
- `lib/context_projection.py`, `tools/context_projection.py`: context_injected payload 增加 context_sources/degraded_sources/lineage_refs/source_hash_refs；修复空 session 仍需 KB recall。
- `lib/runtime_context_inject.py`, `tools/runtime_context_inject.py`: sidecar 升级到 v2，记录 source_counts、required_sources、used_sources、required_source_policy_ok。
- `lib/verifier/context_usage.py`, `tools/verifier/context_usage.py`: 新增 verifier.context_usage，可回放 sidecar 并检查 code/paper/doc required source policy。
- `tests/runtime/test_mirage_context_access_plane.py`: 覆盖 adapter registration、understanding artifact、verifier pass/fail。

## Done 定义达成
1. 真实调用链接入: ✅ `./solar-harness.sh mirage search ...` 真实进入 `solar_mirage.py -> mirage_search.py -> cocoindex_adapter.py`；`runtime_context_inject.py` 真实写出 sidecar 并由 `verifier/context_usage.py` 回放。
2. 禁止硬编码: ✅ 路径使用 `HARNESS_DIR`、`HOME`、`SOLAR_UNDERSTANDING_STORE`、`SOLAR_COCO_QUERY_CMD`；未写 token/credential；CocoIndex CLI 不可用时显式 degraded。
3. 执行证据齐全: ✅ 见“验证方法”命令与结果摘要。
4. 结构化收尾: ✅ 本 handoff 和 PM result 均含已完成/已验证/未验证/风险/后续。

## 验证方法
- `python3 -m py_compile lib/mirage_search.py lib/solar-unified-context.py lib/runtime_context_inject.py lib/context_projection.py lib/cocoindex_adapter.py lib/understand_anything_adapter.py lib/verifier/context_usage.py`
  - 结果: 通过，无语法错误。
- `python3 -m pytest tests/runtime/test_mirage_context_access_plane.py -q`
  - 结果: `4 passed`。
- `./solar-harness.sh mirage search 'code unified_search' --json --sources cocoindex --max-hits 3 --max-chars 1200`
  - 结果: 返回 3 条 `source_type=cocoindex` / `layer=code-chunk` hit，含 `source_counts.cocoindex=3`、`lineage_refs`、`source_hash_refs`；因未发现真实 CocoIndex CLI，明确 `degraded_sources=["cocoindex_cli_unavailable:local_code_scan_fallback"]`。
- `python3 lib/runtime_context_inject.py runtime/s03-core-runtime-smoke/dispatch.md --session-id s03-core-runtime-smoke-3 --pane test --dispatch-id s03-core-runtime-smoke --query "code unified_search" --json`
  - 结果: sidecar v2 写出，`context_sources={"cocoindex":3,"solar_db":3}`，`required_sources=["cocoindex"]`，`required_source_policy_ok=true`。
- `python3 lib/verifier/context_usage.py runtime/s03-core-runtime-smoke/dispatch.md.runtime-context.json --task-kind code --json`
  - 结果: `ok=true`，`missing_sources=[]`，`replayable=true`，`lineage_refs_count=12`，`source_hash_refs_count=6`。

## 未验证
- 真实外部 CocoIndex CLI/API 健康态未验证；本机当前只验证到 adapter command surface 和 degraded local-code-scan fallback。
- 大规模 understanding artifact store 性能未压测；单测验证了真实 artifact JSON 读取和 normalized hit 输出。

## 风险/限制
- `solar-harness coco query` 当前未在 shell frontdoor 注册，adapter 会尝试调用并在 rc!=0 后降级；后续 S04/S05 可补 doctor/frontdoor。
- 当前目录不是 git repository，无法按全局策略 commit/push。

## 备注
- Knowledge Context: `solar-harness context inject` used；命中主要是“真实调用链”约束，当前 S03 设计细节来自本 sprint 的 design/plan/task_graph。
