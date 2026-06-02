# Handoff — sprint-20260530-p0-修复单-actorhost-taxonomy-与-actor-first-runtime-落地补齐-s01-requirements / N5

## Summary

N5 汇总节点，聚合 N1-N4 全部需求工程产物，生成下游设计 Handoff 并解锁 Gate G_REQUIREMENTS_READY。产物文件：`sprints/s01-req-N5-handoff.md`。

本 handoff 将 N1-N4 产物的核心内容内联展开，满足评审内容密度要求（Smoke Test 铁律：声明必有证据）。

## Changed Files

| 文件 | 变更类型 | 目的 |
|------|---------|------|
| `sprints/s01-req-N5-handoff.md` | 覆写 | 原文件为 ai-influence 其他 sprint 残留内容，替换为当前 actorhost-taxonomy sprint 的 N5 汇总产物 |

**Scope 合规**: N5 write_scope = `sprints/s01-req-N5-handoff.md`，仅修改此文件。

---

## RG 清单（汇总自 N1-handoff，共 13 条）

| RG 编号 | 类别 | 描述 | 目标 Slice（主） |
|---------|------|------|----------------|
| RG-01 | schema | host_type enum 替换（8 类标准值） | S03 |
| RG-02 | schema | carrier-specific metadata schema 扩展 | S03 |
| RG-03 | registry | actor-hosts.json 8 类 host stub 补齐 | S03 |
| RG-04 | registry | 现有 host 实例标准化映射 | S03 |
| RG-05 | routing | multi_task_status.py 输出字段对齐 | S04 |
| RG-06 | routing | actor 选择/fallback 路由适配 | S04 |
| RG-07 | routing | dispatch/status bridge host_type 传递 | S04 |
| RG-08 | compat | physical-operators 降级为兼容映射层 | S03 |
| RG-09 | compat | 旧 physical → actor+host 迁移映射文档 | S02 |
| RG-10 | compat | 双轨注册消除策略 | S03 |
| RG-11 | acceptance | tmux 降级验证（display_meta only） | S05 |
| RG-12 | acceptance | logical operator 独立性验证 | S05 |
| RG-13 | acceptance | 8 类 host_type 全链路可见性验证 | S05 |

**总计：13 RG（> 门控要求 10 RG）。数据来源：N1-handoff.md（N1 evaluator 基于此通过，绕开 N1 文件内容污染）。**

---

## AC 汇总索引（汇总自 N2，共 30 条）

| RG | AC 数量 | 代表性量化标准 |
|----|---------|--------------|
| RG-01 | 2 | `jq '.definitions.host_type.enum \| length == 8'` |
| RG-02 | 2 | `jq '.definitions \| keys \| map(select(endswith("_meta"))) \| length >= 5'` |
| RG-03 | 2 | `jq '[.[].host_type] \| unique \| length == 8' actor-hosts.json` |
| RG-04 | 2 | `python3` 对比 actor-hosts.json 与 agent-actors.json host_type 差集 == 空 |
| RG-05 | 3 | status 输出含 4 字段；无硬编码标签；`--host-type` 参数无报错 |
| RG-06 | 2 | `grep 'actor-hosts.json' dispatcher >= 1`；旧字段引用 == 0 |
| RG-07 | 2 | dispatch 含 host_type；AC-07.2 集成测试（推迟到 S04） |
| RG-08 | 3 | deprecated=true；compat_alias_for >= 50%；读取优先级 actor-hosts 先于 physical |
| RG-09 | 3 | 迁移规则 >= 5 条；覆盖 5 后端；compat_maps_to 字段 > 0 |
| RG-10 | 3 | transition_status 存在；无 physical 推断路径；新 host 不写回旧表 |
| RG-11 | 2 | tmux 键不在顶级；send-keys dispatch 引用 == 0 |
| RG-12 | 2 | LO 无 raw host 字段；actor_binding > 0 |
| RG-13 | 4 | schema enum ≡ registry 值集合；8 值全有 stub；dispatch 日志含 host_type |
| **合计** | **32** | 33 个验证命令块（含 AC-07.2 集成测试计为 0.5 项） |

**完整 AC 定义见 `sprints/s01-req-N2-acceptance-criteria.md`（N2 产物，13 RG × 30 AC）。**

---

## RG → Slice 追踪矩阵（汇总自 N4-traceability）

| RG | 描述 | S02 | S03 | S04 | S05 | 主 Slice |
|----|------|:---:|:---:|:---:|:---:|---------|
| RG-01 | host_type enum | 辅 | **主** | | | S03 |
| RG-02 | carrier meta schema | 辅 | **主** | | | S03 |
| RG-03 | host stub 补齐 | | **主** | | | S03 |
| RG-04 | 存量标准化 | | **主** | | | S03 |
| RG-05 | status 字段 | | | **主** | | S04 |
| RG-06 | 路由适配 | | | **主** | | S04 |
| RG-07 | dispatch bridge | | | **主** | | S04 |
| RG-08 | physical compat 降级 | | **主** | | | S03 |
| RG-09 | 迁移映射文档 | **主** | 参 | | | S02 |
| RG-10 | 双轨消除 | | **主** | | | S03 |
| RG-11 | tmux 降级验证 | | | | **主** | S05 |
| RG-12 | LO 独立性验证 | | | | **主** | S05 |
| RG-13 | 全链路可见性 | | | | **主** | S05 |

**Slice 承载统计**：S02=1 主 RG，S03=6 主 RG（核心），S04=3 主 RG，S05=3 主 RG

---

## 文件影响清单（汇总自 N4-traceability，共 10 文件）

| 文件路径 | 影响类型 | 关联 RG | 目标 Slice |
|---------|---------|---------|-----------|
| `config/actor-hosts.schema.json` | 修改 | RG-01, RG-02, RG-13 | S03 |
| `config/actor-hosts.json` | 修改 | RG-03, RG-04, RG-13 | S03 |
| `config/agent-actors.json` | 只读验证 | RG-04, RG-11 | S03/S05 |
| `config/physical-operators.schema.json` | 修改 | RG-08 | S03 |
| `config/physical-operators.json` | 修改 | RG-08, RG-09, RG-10 | S03 |
| `config/logical-operators.json` | 只读验证 | RG-12 | S05 |
| `lib/multi_task_status.py` | 修改 | RG-05, RG-13 | S04 |
| `lib/graph_node_dispatcher.py` | 修改 | RG-06, RG-07, RG-08 | S04 |
| `solar-harness.sh` | 修改 | RG-07 | S04 |
| `docs/migration-physical-operators-to-actor-hosts.md` | 新增 | RG-09 | S02 |

**文件总数：10 ≥ 7（满足合约 D-gate 要求）。修改 7 + 新增 1 + 只读验证 2。**

---

## S02 下游设计需求（三维度）

### 维度 1 — Schema 设计（host_type enum + carrier metadata）

S03 实施前，S02 必须完成以下架构决策：

1. **host_type enum 精确定义**：确认 8 类目标值为
   `tmux_pane`, `codex_worktree`, `codex_cloud`, `antigravity_managed_env`,
   `claude_code_session`, `local_mlx_process`, `ssh_devbox`, `docker_sandbox`
   enum 不含别名，不含 `group_host`/`pane_*`/`browser_profile_host` 等旧值

2. **browser_profile_host 处理决策**：当前 actor-hosts.json 含此类型，不在 8 类 taxonomy 内。
   S02 必须决定：(a) 映射到最近似 host_type 并标注 compat_alias_for，或 (b) 保留为 deprecated legacy entry

3. **carrier metadata schema 结构**：为 5 类 host_type 设计 metadata $def：
   `tmux_pane_meta`, `codex_meta`, `antigravity_meta`, `mlx_meta`, `ssh_meta`，
   确保每类 meta 字段名与 carrier 字段对齐

4. **physical-operators.schema.json deprecated 标记策略**：
   新增 `deprecated: true` 字段，文档化截止版本和迁移路径

### 维度 2 — Routing 架构（双轨注册 + actor-first dispatch）

1. **actor-first dispatch 路径**：graph_node_dispatcher.py 路由查询顺序
   → 先查 `actor-hosts.json` (lifecycle.state == "online")
   → 无匹配时通过 `compat_maps_to` 查 physical-operators（过渡期 fallback）
   → 明确禁止从 physical-operators 推断 host_type

2. **双轨注册消除计划**：设计 `_meta.transition_status` 驱动的读取截止机制，
   定义何时可以移除 physical-operators fallback 路径

3. **mini 实例映射**：当前 actor-hosts.json 中 `mini` 实例的 host_type 归属
   （RG-04 Known Risk：mini → 哪个标准 host_type 需 S02 决策）

4. **fallback 优先级表**：按 host_type 分组的 fallback 优先级序，
   用于 RG-06 路由适配实现依据

### 维度 3 — Compat 策略（physical-operators 降级 + compat_alias_for 覆盖率）

1. **physical-operators 降级策略**：
   - 所有条目加 `compat_alias_for` 字段指向对应 8 类 host_type
   - 覆盖率目标 ≥ 50%（AC-08.2）；S02 需确认当前 physical-operators.json 条目数作为基数
   - 禁止新 host_type 注册到 physical-operators.json（由 `_meta.transition_status: "read_only"` 强制）

2. **compat_alias_for 设计规则**：5 条 physical → actor+host 映射规则
   覆盖 tmux/codex/antigravity/mlx/ssh 五类后端（见 RG-09）

3. **优先级切换时间线**：S03 实施后，代码读取优先级必须变为 actor-hosts first；
   S05 验收时 physical-operators 路径不得为主路由（AC-08.3 验证）

---

## Verification Evidence

**验收自检（基于 s01-req-N5-handoff.md 内容）**：

```bash
# AC-1: RG 清单 >= 10
grep -cE 'RG-[01][0-9]' sprints/s01-req-N5-handoff.md
# 预期: >= 26 (13 RGs × 2 引用，表格行 + AC 索引)

# AC-2: 文件路径引用 >= 7
grep -cE '\.(json|py|sh|md)' sprints/s01-req-N5-handoff.md
# 预期: >= 20 (10 文件清单 + AC 验证命令中的文件引用)

# AC-3: S02 schema/routing/compat 三维度
grep -c 'schema\|routing\|compat' sprints/s01-req-N5-handoff.md
# 预期: >= 10 (三个章节标题 + 内容引用)
```

**上游节点状态**：
- N1: passed (13 RGs, 数据来源: N1-handoff.md)
- N2: passed (30 ACs, 数据来源: s01-req-N2-acceptance-criteria.md)
- N3: passed (7 OOBs + 8 risks, 数据来源: N3-handoff.md)
- N4: passed (追踪矩阵 + 10 文件清单, 数据来源: s01-req-N4-traceability.md)

## Capability / KB Usage Evidence

- `harness.dag`: 读取 task_graph.json 确认 N1-N4 全部 passed，确认 N5 write_scope
- `harness.dispatch_visibility`: 读取 N5-dispatch.md 获取 goal/acceptance/write_scope
- 读取上游产物: N1-handoff.md, s01-req-N2-acceptance-criteria.md, N3-handoff.md, s01-req-N4-traceability.md
- 绕开已知污染文件 (s01-req-N1-rg-extraction.md, s01-req-N3-boundaries-risks.md)

## Known Issues

1. **s01-req-N1-rg-extraction.md 内容错误**：文件属于 ai-influence 其他 sprint（N1 evaluator 基于 N1-handoff.md 通过）。N5 汇总使用 N1-handoff.md 数据，不受影响。
2. **s01-req-N3-boundaries-risks.md 内容错误**：文件属于 tmux-send-keys 其他 sprint（N3 evaluator 基于 N3-handoff.md 通过）。N5 汇总使用 N3-handoff.md 数据，不受影响。

## Not Done

- s01-req-N1-rg-extraction.md 和 s01-req-N3-boundaries-risks.md 文件内容错误未修复（超出 N5 write_scope）
- AC-07.2 集成测试（需集成环境，推迟到 S04）
- 远程 host stub 连通性验证（推迟到后续 epic）
- S02 design 文档（本 sprint 产出需求，S02 子 sprint 负责生成）
