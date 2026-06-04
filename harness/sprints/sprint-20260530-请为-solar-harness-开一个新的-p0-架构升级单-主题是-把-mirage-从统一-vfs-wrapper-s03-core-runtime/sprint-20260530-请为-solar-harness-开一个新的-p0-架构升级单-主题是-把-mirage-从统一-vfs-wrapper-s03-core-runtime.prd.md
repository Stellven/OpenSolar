# PRD: 核心实现与数据模型

epic_id: `epic-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper`
sprint_id: `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

请为 solar-harness 开一个新的 P0 架构升级单，主题是“把 Mirage 从统一 VFS wrapper 升级为完整 Context Access Plane，并收口 CocoIndex / understand-anything / runtime_context_inject / verifier 的上下文闭环”。

这张单是对现有“统一数据访问层 / 上下文数据平面升级”方向的进一步刷新和压实，要求先基于当前仓库真实状态立项，不要按假想状态写。

当前已确认的真实状态：
1. Solar 已经有 Mirage 入口层：
   - harness/lib/solar_mirage.py 是 VFS wrapper，支持 doctor/workspace/mounts/exec/search。
   - 其 doctor/health 设计明确当前是 wrapper_only，不是完整 FUSE：macOS/SIP 下 sdk_decision=wrapper_only。
   - Mirage 的安全边界已经存在：logical path -> physical path rewrite、禁止 ../ / symlink escape、默认不挂整个 HOME、Drive 默认只读、stdout/events 脱敏。
2. 当前 mirage.solar.yaml mount 已有：
   - /knowledge
   - /raw
   - /sources
   - /papers
   - /qmd (virtual_command)
   - /solar-db
   - /cortex
   - /sprints
   - /drive
   但没有：
   - /cocoindex
   - /understanding
   - /code-index
   - /callgraph
   - /symbols
3. 当前 mirage_search.py 的统一 source 只有：
   - mirage_path
   - qmd
   - solar_db
   注释和实现都表明 unified_search 目前还没有 cocoindex / understanding source。
4. 当前真正给 agent/pane 注入上下文的主链仍是：
   - runtime_context_inject.py
   - ContextProjection
   - solar-unified-context.py
   其中 runtime_context sidecar 当前只稳定记录：
   - kb_hit_count
   - included_event_count
   - context_event_id
   还没有细粒度 context_sources/source counts/lineage_refs。
5. 当前 /qmd 属于 virtual_command mount，不应假设 shell 中普通 `rg/grep/find` 能像物理目录一样自由遍历全部虚拟源。

因此这次单的核心判断要写清楚：
- Mirage 是必要入口层，但不是完整闭环答案。
- 要真正“用好” CocoIndex 和 understand-anything，还必须把它们注册成 Mirage source / mount，接入 solar-unified-context，多源融合后进入 runtime_context_inject，并由 verifier 检查 agent 是否真的使用了这些上下文。
- 短期目标不是追求 shell-native FUSE 幻觉，而是先把 search/evidence/injection/verifier 闭环打通。

请按以下架构方向产出 requirements 和 architecture：

一、总体分层
1. Mirage = Access Plane / logical VFS entry / search adapter orchestration
2. CocoIndex = Index Plane / incremental fresh semantic index / lineage engine
3. understand-anything = Understanding Artifact Producer / semantic distiller
4. solar-unified-context = Fusion + Ranking + Dedupe Plane
5. runtime_context_inject = Agent Context Delivery Plane
6. verifier.context_usage = Context Usage Verification Plane

要求 builder/architect 明确这六层的边界，不允许再把它们混成“一个 search 工具”。

二、Mirage 升级目标
1. 把 Mirage 从“wrapper/search 工具”升级为完整 Context Access Plane。
2. 新增 Mirage mount/source 设计，至少包括：
   - /cocoindex        (virtual_command or adapter-backed source)
   - /understanding    (disk or structured artifact mount)
3. 给 Mirage 设计标准 source adapter 输出 schema，至少包含：
   - mount
   - path
   - source_type
   - snippet
   - provenance
   - score_or_rank
   - layer
   - source_hash
   - lineage
4. 在 Mirage search 层加入 CocoIndex / understanding source，不再只停留在 mirage_path/qmd/solar_db。
5. 保持 fail-open，但 degraded source 不能伪装成正常 evidence。

三、CocoIndex 接入要求
1. 定义 CocoIndex 在 Solar 中的角色：不是替代 Mirage，而是 Mirage 背后的 Index Plane。
2. 第一版可通过 Mirage source 或 adapter 接入，至少支持：
   - code chunks
   - symbols
   - callgraph
   - blast-radius relevant relations
   - docs / dispatch / evidence artifacts
3. 需要提供命令面：
   - solar-harness coco doctor
   - solar-harness coco update --source solar
   - solar-harness coco query "..." --json
   - solar-harness coco lineage <artifact_id> --json
4. 明确 freshness / delta / lineage 指标，例如：
   - last_update_at
   - changed_files_processed
   - stale_sources
   - lineage_ok

四、understand-anything 接入要求
1. 定义 understand-anything 在 Solar 中的角色：不是直接“给 TUI pane 手动调用”，而是理解产物生成器。
2. 输出标准 understanding artifact，至少包含：
   - source_path
   - source_hash
   - modality
   - title
   - summary
   - claims
   - entities
   - decisions
   - open_questions
   - citations
   - confidence
   - degraded
3. 需要提供命令面：
   - solar-harness ua doctor
   - solar-harness ua understand <path> --json
   - solar-harness ua ingest <path>
4. 默认理解产物应进入统一落盘路径，并可通过 Mirage /understanding source 暴露。

五、Unified Context / Injection 改造要求
1. solar-unified-context.py 必须扩展为真正的多源融合器，而不仅是 Mirage/QMD/Solar DB 聚合器。
2. retrieve(query) 需要支持融合：
   - mirage_path
   - qmd
   - solar_db
   - cocoindex
   - understanding
   - ragflow(optional)
   - session events
3. 需要明确 source layering，例如：
   - synthesis
   - concepts
   - references
   - raw-evidence
   - retrieval-evidence
   - code-symbol
   - code-callgraph
   - code-chunk
   - understanding-summary
   - understanding-claim
   - understanding-entity
4. runtime_context_inject.py / ContextProjection sidecar 需要新增：
   - context_sources
   - source-specific hit counts
   - degraded_sources
   - lineage_refs
   - source_hash refs
5. Dispatch 注入文本中要明确列出 Knowledge Sources，而不是只给无来源摘要块。

六、Verifier / Evidence 闭环要求
1. 新增 verifier.context_usage 或等效检查：
   - runtime_context_sidecar_exists
   - required_context_source_available
   - degraded_sources_declared
   - code task 至少具备 cocoindex/code intelligence source
   - paper/doc task 至少具备 understanding source
   - final handoff/report 引用 context sources
2. Evidence Ledger 要能回放：
   - query
   - source
   - hit path
   - source hash
   - lineage
   - degraded sources
   - context event id
3. 明确“能搜到”不等于“已用上”；只有被注入、被引用、被 verifier 检查，才算真正进入执行闭环。

七、Mirage 使用原则
1. 第一阶段不要追求“普通 shell 直接 rg/grep/find 所有虚拟源像物理目录一样工作”。
2. 第一阶段以命令面和 adapter 面为主：
   - solar-harness mirage search "..." --json
   - solar-harness mirage exec -- grep ... /knowledge
   - solar-harness coco query "..." --json
   - solar-harness ua understand <path> --json
3. 如需 shell-native VFS/FUSE，应列为后续阶段，不得阻塞当前 context/evidence/verifier 主闭环。

八、验收标准
至少包含以下 7 类：
1. mirage doctor / coco doctor / ua doctor 都能给出 machine-verifiable health。
2. mirage search 能出现 source_type=mirage_path/qmd/solar_db/cocoindex/understanding。
3. runtime_context_inject sidecar 能记录 cocoindex_hit_count / understanding_hit_count 或等价 context_sources 结构。
4. agent dispatch prompt 中能看到 Knowledge Sources 分层。
5. verifier 能对“required context source 未被使用”给出 WARN/FAIL。
6. Evidence Ledger 能追踪 query/source/source_hash/lineage/degraded/context_event_id。
7. CocoIndex freshness 可观测，understanding artifacts 可追溯。

九、产出要求
请输出：
1. requirements
2. architecture
3. Mirage source/mount extension design
4. unified context fusion design
5. verifier/evidence design
6. phased rollout（P0/P1/P2/P3）
7. risks / degraded mode / non-goals

一句话定性：
这张单的目标不是“再做一个搜索工具”，而是把 Mirage 从必要入口层升级成完整 Context Access Plane，并把 CocoIndex、understand-anything、runtime_context_inject 和 verifier 接成真正的数据访问闭环。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper.epic.md`、`epic-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.design.md`
- `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.plan.md`
- `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.task_graph.json`
- `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.handoff.md`
- `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.eval.md` 或 `sprint-20260530-请为-solar-harness-开一个新的-p0-架构升级单-主题是-把-mirage-从统一-vfs-wrapper-s03-core-runtime.eval.json`
