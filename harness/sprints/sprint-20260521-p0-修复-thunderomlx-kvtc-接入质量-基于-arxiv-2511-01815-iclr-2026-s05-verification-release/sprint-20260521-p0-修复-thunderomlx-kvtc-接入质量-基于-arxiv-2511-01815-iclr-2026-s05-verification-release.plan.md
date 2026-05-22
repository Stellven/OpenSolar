# Plan — S05 Verification-Release 切片：执行计划

epic_id: `epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026`
sprint_id: `sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release`
slice: `verification-release`
generated_at: `2026-05-22T09:25:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream: `S03 passed 09:09Z · S04 passed 09:22Z` (epic 仅剩 S05)

## 1. 交付切片顺序（5 wave）

| Wave | 节点 | 类型 | 并发 | 依赖 |
|------|------|------|------|------|
| W1 | D0 | scripts/kvtc_ab_correctness.py 升级（CLI flags + jsonl emit） | 1 路 | 无 |
| W2 | D1, D2, D3 | fixtures + e2e tests + CI YAML | 3 路并行 | D0 |
| W3 | D4 | smoke run + evidence capture | 1 路 | D1, D2, D3 |
| W4 | D5 | docs/KVTC_RELEASE.md release notes | 1 路 | D4 |
| W5 | D6 | handoff + traceability join (epic close prerequisite) | 1 路 | D5 |

合计 7 节点；5 layer。

## 2. 文件级写入范围（强制 write_scope）

| 节点 | 写入文件（绝对路径） | 动作 |
|------|---------------------|------|
| D0 | `/Users/lisihao/ThunderOMLX/scripts/kvtc_ab_correctness.py` | MODIFY |
| D1 | `/Users/lisihao/ThunderOMLX/tests/fixtures/kvtc/manifest.json` + `qwen36_ssd_block_*.npz` + `same_dim_family_*.npz` + `hybrid_family_*.npz` + `synthetic_outlier_*.npz` + `named_prompt_cache_*.npz`（15 cells）+ `/Users/lisihao/ThunderOMLX/scripts/fetch_kvtc_fixtures.sh` | NEW |
| D2 | `/Users/lisihao/ThunderOMLX/tests/regression/test_kvtc_e2e.py` | NEW |
| D3 | `/Users/lisihao/ThunderOMLX/.github/workflows/kvtc-regression.yml` | NEW |
| D4 | `/Users/lisihao/ThunderOMLX/reports/kvtc-ab/<ts>/{ab_correctness.summary.json, recon_gate.jsonl, per_fixture/*.json}` | RUN-PRODUCE |
| D5 | `/Users/lisihao/ThunderOMLX/docs/KVTC_RELEASE.md` | NEW |
| D6 | `~/.solar/harness/sprints/<s05-sid>.handoff.md` + `<s05-sid>.traceability.json` | NEW |

**严格禁止 write_scope 外路径**，包括：
- `src/omlx/cache/kvtc_*.py`（S03 范围）
- `src/omlx/cache/kvtc_ui_*.py`（S04 范围）
- `src/omlx/server.py`（S04 范围）
- 任何 `src/omlx/` 业务代码
- `~/.solar/STATE.md`、epic.*、S01/S02/S03/S04 artifacts

## 3. 并发边界

- W1 D0 单节点（CLI 升级是其他节点的前置）
- W2 D1/D2/D3 write_scope 互不重叠（不同目录） → 3 路并行
- W3 D4 单节点（真跑 ab_correctness.py，产 evidence）
- W4 D5 单节点（docs，引用 D4 evidence）
- W5 D6 单节点 join
- 同 pane 内禁止并发；max-parallel 建议 3（W2 三节点可同 batch）

## 4. 每节点段落契约

D0 commit 必须含：

1. **CLI Flags Added**：列出 `--fixture-set / --report-dir / --fail-on-gate-violation / --emit-recon-gate-jsonl / --dump-meta / --dump-family-decisions`
2. **Exit Codes**：0 = pass / 1 = SLO violation / 2 = fixture loader / 3 = recon_gate exception
3. **Compat Notes**：旧 CLI 行为保留（lines 25-30 import + 83-100 run_case 现状不破坏）
4. **Imports**：从 `omlx.cache.kvtc_recon_gate` 拿 `evaluate`

D1 commit 必须含：

1. **Coverage Matrix**：列出 15 cells 全集 + 每 fixture id + source + expect_decision
2. **Synthetic Generation**：合成方法（numpy seed + shape + 注入策略）
3. **Manifest JSON**：fixture_id / fixture_class / source / expect_decision / 元数据 7+ 字段

D4 commit 必须含：

1. **Run Command**：实际命令 + 时间戳
2. **Exit Code**：0 (期望)
3. **Summary Snapshot**：`ab_correctness.summary.json` 关键字段 (total / kvtc_accept / lz4_fallback / failed / hard_violations / soft_violations)
4. **Recon Gate JSONL**：行数 + sample 第一行字段集
5. **Files Produced**：reports/kvtc-ab/<ts>/ 目录树
6. **SLO Compliance**：observed vs threshold 对照

D6 join 节点必须含：

- R1..R7 全部状态（implemented + verified）
- OQ1..OQ4 最终状态
- evidence_collection_plan 全集（N1-E1..N7-E6）的状态对照
- `epic_required_gates_status` = 5 sprint gate 状态汇总
- `parent_check_ready = true`
- epic close 前置 checklist

## 5. 验证命令

```bash
SID5=sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s05-verification-release
THUNDEROMLX=/Users/lisihao/ThunderOMLX
EPIC=epic-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026

# A. DAG schema 校验
~/.solar/bin/solar-harness graph-scheduler validate --graph ~/.solar/harness/sprints/$SID5.task_graph.json

# B. ready / layers / batches
~/.solar/bin/solar-harness graph-scheduler ready    --graph ~/.solar/harness/sprints/$SID5.task_graph.json
~/.solar/bin/solar-harness graph-scheduler layers   --graph ~/.solar/harness/sprints/$SID5.task_graph.json
~/.solar/bin/solar-harness graph-scheduler batches  --graph ~/.solar/harness/sprints/$SID5.task_graph.json --max-parallel 3

# C. 文件齐全性
test -f $THUNDEROMLX/scripts/kvtc_ab_correctness.py
test -f $THUNDEROMLX/scripts/fetch_kvtc_fixtures.sh
test -d $THUNDEROMLX/tests/fixtures/kvtc
test -f $THUNDEROMLX/tests/fixtures/kvtc/manifest.json
test -f $THUNDEROMLX/tests/regression/test_kvtc_e2e.py
test -f $THUNDEROMLX/.github/workflows/kvtc-regression.yml
test -d $THUNDEROMLX/reports/kvtc-ab
test -f $THUNDEROMLX/docs/KVTC_RELEASE.md

# D. CLI flags 已加
grep -E "\-\-fixture-set|\-\-report-dir|\-\-fail-on-gate-violation|\-\-emit-recon-gate-jsonl" \
  $THUNDEROMLX/scripts/kvtc_ab_correctness.py | head -5

# E. 15 cells 覆盖
python3 -c "
import json
m=json.load(open('$THUNDEROMLX/tests/fixtures/kvtc/manifest.json'))
fs = m['fixtures'] if isinstance(m, dict) else m
assert len(fs) >= 15, f'expected 15 cells, got {len(fs)}'
stable = sum(1 for f in fs if f.get('source')=='stable-ci')
assert stable >= 12, f'expected >=12 stable-ci, got {stable}'
print(f'OK: {len(fs)} cells, {stable} stable-ci')
"

# F. e2e test 跑通
cd $THUNDEROMLX && ./venv/bin/python -m pytest tests/regression/test_kvtc_e2e.py -v --tb=short

# G. D4 smoke run 真跑 (builder 执行)
cd $THUNDEROMLX && ./venv/bin/python scripts/kvtc_ab_correctness.py \
  --fixture-set stable-ci \
  --report-dir reports/kvtc-ab/$(date +%Y%m%d-%H%M%S)/ \
  --fail-on-gate-violation \
  --emit-recon-gate-jsonl
echo "exit code: $?"   # 期望 0

# H. summary.json schema 完整
LATEST=$(ls -1d $THUNDEROMLX/reports/kvtc-ab/*/ | tail -1)
python3 -c "
import json
d=json.load(open('${LATEST}ab_correctness.summary.json'))
for k in ['schema_version','generated_at','fixture_set','summary','slo','named_prompt_cache_status','tracking_sprint']:
    assert k in d, f'missing {k}'
print('OK ab_summary fields complete')
"

# I. recon_gate.jsonl 字段完整
head -1 ${LATEST}recon_gate.jsonl | python3 -c "
import json, sys
d=json.loads(sys.stdin.read())
need=['ts','model_id','tensor_family','shape_signature','layer_type','rope_state','decision','reason','sample_count','sample_seed','codec_version']
for k in need: assert k in d, f'missing {k}'
print('OK recon_gate.jsonl fields complete')
"

# J. CI YAML 含 pre-merge + post-merge
grep -E "kvtc_regression|kvtc-regression|fixture-set stable-ci" \
  $THUNDEROMLX/.github/workflows/kvtc-regression.yml | head -5

# K. docs/KVTC_RELEASE.md 含 rollback + ATLAS hook 名
grep -E "THUNDEROMLX_KVTC_DISABLE|THUNDEROMLX_NAMED_PROMPT_CACHE_SAVE_ENABLED|atlas\.kvtc\.recon_gate_repair" \
  $THUNDEROMLX/docs/KVTC_RELEASE.md | head -3

# L. 未触碰禁区
! git -C $THUNDEROMLX diff --name-only HEAD | grep -E "^src/omlx/cache/(kvtc_codec|kvtc_calibration_store|kvtc_recon_gate|paged_ssd_cache|kvtc_errors|kvtc_tools_recalibrate|kvtc_ui_gate|kvtc_ui_i18n)\.py|^src/omlx/server\.py"

# M. epic parent-check
~/.solar/bin/solar-harness graph-scheduler parent-check \
  --graph ~/.solar/harness/sprints/$EPIC.task_graph.json
# 期望：S01..S05 全 passed → ok
```

## 6. no-live-pane-mutation 保护

- 禁止 `tmux send-keys` / `solar-harness restart` / `solar-harness inject-prompt` / `solar-harness models switch`
- **本 sprint D4 节点是唯一真跑 `scripts/kvtc_ab_correctness.py` 的节点**（在 ThunderOMLX venv 内）；其他节点禁止真跑
- 禁止启动 ThunderOMLX server / uvicorn
- 禁止真实加载 Qwen3.6 模型权重
- 禁止 Write/Edit 任何 S03/S04 范围业务代码
- 禁止改 `~/.solar/STATE.md`、epic.*、S01/S02/S03/S04 任何 artifact
- pytest 必须在 ThunderOMLX venv：`./venv/bin/python -m pytest`
- 违反任一项 → evaluator FAIL + `stop_rule_violation` + ATLAS structured repair

## 7. Rollback / Stop Rule

- 任一节点 evaluator FAIL → 状态回 `planning_complete`，builder 重做被 FAIL 节点
- D1 fixture manifest 不含 15 cells 或 stable-ci < 12 → 立即 FAIL
- D0 CLI flags 缺任一（5 个） → 立即 FAIL
- D4 真跑 exit code ≠ 0 → 立即 FAIL（即触发 S03/S04 round-2 修复）
- D4 任一 hard SLO 越界 → 立即 FAIL
- D4 任一 `kvtc_accept` + `min_cos < 0.999` → 立即 hard FAIL（无 soft 缓冲）
- D4 任一 fixture 输出 decision ≠ expect_decision → 立即 FAIL
- ab_correctness.summary.json 缺 schema_version 字段 → 立即 FAIL
- recon_gate.jsonl 缺 N4-A5 必填 14 字段任一 → 立即 FAIL
- 任何节点改禁区文件 → FAIL + ATLAS
- 任何文档/代码使用乐观词 → FAIL
- 任何放宽 hard 阈值 → FAIL
- PRD/contract mtime 变化 → 本 plan 作废，重跑 planner

## 8. 模型路由建议（coordinator 决定）

- D0 CLI 升级：`sonnet`（涉及 argparse + jsonl emit + 兼容性）
- D1 fixtures：`sonnet`（合成张量 + manifest 设计）
- D2 e2e tests：`sonnet`（集成 + TestClient + jsonl 校验）
- D3 CI YAML：`glm-5.1`（声明式配置）
- D4 smoke run + evidence：`sonnet`（真跑 + 解释 evidence）
- D5 release docs：`sonnet`（释放说明 + rollback + evidence summary）
- D6 join + epic close prerequisite：`opus`（最终一致性 + 全局视图）

## 9. 时间预算

- W1 D0：~30 min（CLI 升级 + 兼容旧测试）
- W2 D1/D2/D3 并行：~45 min（D1 fixture 生成最重）
- W3 D4 smoke run：~10 min（CPU 跑 12+ synthetic fixtures）
- W4 D5 release docs：~20 min
- W5 D6 join：~20 min
- S05 整体目标 3-4 个 dispatch round 内 passed → epic close

## 10. 完成定义（DoD 7 条）

1. **已完成**：design.md / plan.md / task_graph.json / planning.html 4 件齐全
2. **已完成**：task_graph.json 通过 `graph-scheduler validate`（0 errors / 0 warnings）
3. **已完成**：planning.html 通过 `html_artifact.py register`
4. **未验证**：D0..D6 builder 节点未执行
5. **未验证**：15 fixture × expect_decision 未真跑；CI YAML 未在 GitHub 真跑；docs 未审
6. **风险**：D4 真跑可能暴露 S03 实现 bug → 触发 S03 round-2；真实 Qwen3.6 fixture 留 placeholder（OQ1 tentatively_resolved）；ATLAS hook 注册依赖运维
7. **后续待办**：coordinator 派发 W1→W5 → builder 实施 7 节点 → D4 smoke run PASS → evaluator 抽检 → S05 passed → epic parent-check → epic close
