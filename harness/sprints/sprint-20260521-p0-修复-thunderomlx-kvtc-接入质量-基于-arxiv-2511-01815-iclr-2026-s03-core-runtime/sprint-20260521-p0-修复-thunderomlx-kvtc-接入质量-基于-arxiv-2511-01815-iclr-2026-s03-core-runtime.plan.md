# Plan — S03 Core-Runtime 切片：执行计划

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime`
slice: `core-runtime`
generated_at: `2026-05-22T08:50:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `S02 passed/completed 2026-05-22T08:39:39Z`

## 1. 交付切片顺序（5 wave）

| Wave | 节点 | 类型 | 并发 | 依赖 |
|------|------|------|------|------|
| W1 | B0 | new file `kvtc_errors.py` | 1 路 | 无 |
| W2 | B1, B2, B3, B4 | calibration_store / recon_gate / paged_ssd_cache / recalibrate CLI | 4 路并行 | B0 |
| W3 | B5 | `kvtc_codec.py` encode 入口（classifier + sink/recent + recon_gate hook + K/V config + env） | 1 路 | B1, B2, B3 |
| W4 | B6 | `tests/kvtc/test_*.py` ≥22 cases | 1 路 | B0..B5 |
| W5 | B7 | join: handoff.md + traceability.json | 1 路 | B6 |

合计 7 节点；5 layer。

## 2. 文件级写入范围（强制 write_scope）

| 节点 | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| B0 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_errors.py` | NEW |
| B1 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_calibration_store.py` | MODIFY (保留旧 API，加 5 维 key 路径) |
| B2 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_recon_gate.py` | NEW |
| B3 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/paged_ssd_cache.py` | MODIFY（限 KVTC 区域：lines 395-466 metadata + 1604-1998 IO；其他不动） |
| B4 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_tools_recalibrate.py` | NEW |
| B5 | `/Users/lisihao/ThunderOMLX/src/omlx/cache/kvtc_codec.py` | MODIFY |
| B6 | `/Users/lisihao/ThunderOMLX/tests/kvtc/test_calibration_key.py`, `test_family_classifier_bypass.py`, `test_reconstruction_gate.py` | NEW（3 file） |
| B7 | `~/.solar/harness/sprints/<s03-sid>.handoff.md`, `<s03-sid>.traceability.json` | NEW |

**严格禁止 write_scope 外路径**，包括但不限于：
- `/Users/lisihao/ThunderOMLX/src/omlx/server.py`（S04）
- `/Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py`（S05）
- `/Users/lisihao/ThunderOMLX/.github/workflows/**`（S05）
- 任何 UI / frontend 路径（S04）
- `~/.solar/STATE.md`、epic.*、S01/S02 artifacts

## 3. 并发边界

- W1 B0 单节点（其他都 import 自它）。
- W2 B1/B2/B3/B4 write_scope 互不重叠 → 4 路并行。
- W3 B5 单节点；write_scope 与 W2 不冲突，但语义上必须等 B1/B2/B3 完成（runtime 集成）。
- W4 B6 单节点（3 测试文件可分子节点，但简化为 1 个节点以减少 DAG 噪音）。
- W5 B7 单节点 join。
- 同 pane 内禁止并发；max-parallel 建议 3（W2 4 个节点会分 2 batch）。

## 4. 每节点 markdown 段落契约

每个 B0..B7 必须在 commit message / handoff 中含：

1. **Implemented**：本节点实现了哪些 acceptance（引用 N2-Ax / N3-Ax / N4-Ax / S02-A3-API-x）
2. **Files Touched**：diff 涉及文件 + 行数变更
3. **API Signatures**（B5 必须）：encode/decode 公共签名摘要
4. **Test Evidence**（B6 必须）：pytest 输出 ≥22 PASS 的 raw 行
5. **Compat Notes**：保留了哪些旧 API alias
6. **Stop-Rule Compliance**：明示未触碰 server.py / ab_correctness.py / UI

B7 join 节点必须额外含：

- R1..R7 状态（继承 S01）
- OQ1..OQ4 状态（继承 S02，可调整）
- builder_forbidden_aggregate 全文
- S04 / S05 接力清单（输入文件 / 期望输出 / 禁止动作 / 验证证据计划）

## 5. 验证命令

```bash
SID3=sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s03-core-runtime
THUNDEROMLX=/Users/lisihao/ThunderOMLX

# A. DAG schema 校验
~/.solar/bin/solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/$SID3.task_graph.json

# B. ready / layers / batches
~/.solar/bin/solar-harness graph-scheduler ready    --graph ~/.solar/harness/sprints/$SID3.task_graph.json
~/.solar/bin/solar-harness graph-scheduler layers   --graph ~/.solar/harness/sprints/$SID3.task_graph.json
~/.solar/bin/solar-harness graph-scheduler batches  --graph ~/.solar/harness/sprints/$SID3.task_graph.json --max-parallel 3

# C. 文件齐全性
test -f $THUNDEROMLX/src/omlx/cache/kvtc_errors.py
test -f $THUNDEROMLX/src/omlx/cache/kvtc_recon_gate.py
test -f $THUNDEROMLX/src/omlx/cache/kvtc_tools_recalibrate.py
test -f $THUNDEROMLX/tests/kvtc/test_calibration_key.py
test -f $THUNDEROMLX/tests/kvtc/test_family_classifier_bypass.py
test -f $THUNDEROMLX/tests/kvtc/test_reconstruction_gate.py

# D. 公共错误类齐全
grep -E "^class (KVTCError|CalibrationKeyIncompleteError|LegacyKeyWriteRejectedError|ClassifierInputIncompleteError|InvalidTensorError|ReconGateException|ReconGateThresholdViolationError|ReconGateInternalError|ReconGateConfigError|ForceKVTCUnsupportedFamilyError)" \
  $THUNDEROMLX/src/omlx/cache/kvtc_errors.py | wc -l   # 期望 ≥ 10

# E. encode 入口签名钉死
grep -E "def encode\(.*tensor.*meta.*sink_tokens=4.*recent_window=64.*force_kvtc=False" \
  $THUNDEROMLX/src/omlx/cache/kvtc_codec.py | head -1

# F. recon_gate evaluate 签名钉死
grep -E "def evaluate\(meta.*decoded.*expected\).*-> ?ReconResult" \
  $THUNDEROMLX/src/omlx/cache/kvtc_recon_gate.py | head -1

# G. env 开关存在
grep -E "THUNDEROMLX_KVTC_DISABLE|THUNDEROMLX_KVTC_FORCE_LEGACY_CALIBRATION|THUNDEROMLX_KVTC_HOME" \
  $THUNDEROMLX/src/omlx/cache/kvtc_codec.py | head -3

# H. pytest 22+ cases pass（builder/evaluator 实际跑）
cd $THUNDEROMLX && ./venv/bin/python -m pytest tests/kvtc/ -v --tb=short

# I. 未触碰禁区
! git -C $THUNDEROMLX diff --name-only HEAD | grep -E "^src/omlx/server\.py|^scripts/kvtc_ab_correctness\.py|^\.github/"

# J. parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph ~/.solar/harness/sprints/epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026.task_graph.json
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- 禁止真实跑 `scripts/kvtc_ab_correctness.py`（即使是 smoke test；属 S05 范围）
- 禁止 `curl .../v1/cache/prompt/*` 或启动 ThunderOMLX server
- 禁止修改 ThunderOMLX `server.py`、`scripts/`、`.github/workflows/`、UI / frontend
- 禁止改 `~/.solar/STATE.md`、epic.traceability.json、epic.task_graph.json、S01/S02 任何 artifact
- 禁止真实创建 `$THUNDEROMLX_KVTC_HOME/calibration/v2/` 与 production 重叠的目录（测试用 tmp_path）
- pytest 必须在 ThunderOMLX 仓库 venv 内跑：`./venv/bin/python -m pytest`（per MEMORY 入口）
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 的节点
- B0 缺任一钉死错误类（10 个） → 立即 FAIL
- B5 encode 签名漂移（不含 `sink_tokens=4 / recent_window=64 / force_kvtc=False` 默认） → 立即 FAIL
- B2 recon_gate.evaluate 签名不是 `(meta, decoded, expected) -> ReconResult` → 立即 FAIL
- B6 pytest 任一 case 失败 → S03 不许 passed
- 任何 builder 触发 live pane mutation 或越权写禁区 → FAIL + ATLAS repair
- 任何文档/代码使用乐观词（已修复 / 稳定 / 完美） → FAIL
- 任何放宽 hard 阈值（0.02 / 0.999） → FAIL
- 任何 `force_kvtc` 被暴露到 env / model card → FAIL
- 任何 codec encode 被异步化 → FAIL
- 任何 `paged_ssd_cache.py` 非 KVTC 区域代码（行号区间 395-466 与 1604-1998 之外）被修改 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由建议（coordinator 决定）

- B0 错误类 module：`glm-5.1`（机械写）
- B1 calibration_store：`sonnet`（涉及兼容性 + 迁移）
- B2 recon_gate：`sonnet`（涉及 numpy 计算 + buffer 物理保证）
- B3 paged_ssd_cache：`sonnet`（涉及 4030 行文件的局部修改，需要 surgical edit）
- B4 recalibrate CLI：`glm-5.1`
- B5 codec encode：`opus`（最关键 + 跨多组件 + 错误类层级落地）
- B6 pytest：`sonnet`（22 cases 需精确覆盖 acceptance）
- B7 handoff/traceability：`sonnet`（join + 全局一致性）

## 9. 时间预算

- W1 B0：单 dispatch round（~10 min）
- W2 B1/B2/B3/B4 并行：~30 min（B3 最重 — 修 4030 行文件局部）
- W3 B5：~45 min（最复杂，整合 W2 全部）
- W4 B6：~30 min（写 22 case + 跑过）
- W5 B7：~15 min
- S03 整体目标 4-5 个 dispatch round 内 passed → 解锁 S04（部分独立）和 S05（依赖 S03）

## 10. 完成定义（呼应 DoD 7 条）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件齐全
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（0 errors / 0 warnings）
3. **已完成**：planning.html 通过 `html_artifact.py register`
4. **未验证**：B0..B7 builder 节点尚未执行（属下一 dispatch round）
5. **未验证**：22 pytest cases、本节点的 8 个具体 acceptance 都未真跑
6. **风险**：S03 是首个真改业务代码的 sprint，越权风险最高；`paged_ssd_cache.py` 4030 行文件局部修改需 surgical edit，可能误改非 KVTC 区域
7. **后续待办**：coordinator 按 task_graph 派发 W1→W5 → builder 实施 7 节点 → pytest 22+ PASS → evaluator 抽检 → S03 passed → epic 激活 S05（S04 已可独立并行）
