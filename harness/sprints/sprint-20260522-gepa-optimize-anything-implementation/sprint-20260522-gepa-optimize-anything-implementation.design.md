# Design — GEPA optimize_anything Stage 1 Implementation

sprint_id: `sprint-20260522-gepa-optimize-anything-implementation`
role: `planner`
status: `planning_complete`
generated_at: `2026-05-22T13:05:00Z`
knowledge_context: `solar-harness context inject used (mirage degraded -> qmd/obsidian/solar_db fallback)`
upstream:
  - design sprint: `sprint-20260522-gepa-optimize-anything-integration` (final report at `~/.solar/harness/monitor-reports/gepa-optimize-anything-integration.md`)
  - PRD + Contract created by Codex PM 2026-05-22T16:55:00Z
  - task_graph.json already validated (12 nodes, 7 layers, 0 errors / 0 warnings)
  - I0 (dry-run install gate) **passed** 2026-05-22T16:51:32Z — namespace confirmed: `from gepa.optimize_anything import optimize_anything, GEPAConfig, EngineConfig`
  - I1 (package init) **reviewing** — `integrations/gepa_optimizer/__init__.py` 21 exports，lazy-load，零副作用
parallel_with: `sprint-20260522-gepa-optimize-anything-integration (design sprint, may still be wrapping up)`

## 0. 本切片的边界（强制 read-first）

- 本 sprint 是 GEPA optimizer 的 **Stage 1 实施**：在 `integrations/gepa_optimizer/` 下建独立 package + `tests/integrations/gepa_optimizer/` 测试 + MVP `/tmp/gepa_seed.txt` 演练，**绝不**接入 production。
- **允许 Write/Edit** 的路径（per contract package_boundary + write_scope per node）：
  - `/Users/lisihao/.solar/harness/integrations/gepa_optimizer/{__init__,adapter,cli,evaluator,artifact_store,operator_router,budgets,promote}.py`
  - `/Users/lisihao/.solar/harness/tests/integrations/gepa_optimizer/**`
  - `/Users/lisihao/.solar/harness/optimizer-runs/<run_id>/**`（IM 节点真跑产出）
  - `/tmp/gepa_seed.txt`（IM 节点唯一 promote target）
  - sprint 自身 artifact：`sprints/<sid>.{design,plan,I0..I8-handoff,IT-handoff,IM-handoff,IH-handoff,task_graph,traceability,planning_html}.md/json/html`
  - 最终报告：`monitor-reports/gepa-optimize-anything-implementation.md`
- **严格禁止**：
  - 全局 `pip install gepa`（必须 venv 隔离 / dry-run only）；I0 已用 dry-run 完成 namespace 校验
  - 任何 production path 作为 promote target（contract Hard Safety Rule + I8 必须 enforce）
  - 修改 Solar hooks / skills / prompts / config / operator registry / `~/.solar/STATE.md` / epic.*
  - 真跑 cloud LLM 优化循环（除非 CLI 显式 `--execute` + 三 budget caps，且本 sprint 不演练 cloud；MVP 用 mocked evaluator）
  - 打印或落盘 secrets（env / API key / OAuth）
  - 把 `solar-harness optimizer gepa ...` shell wrapper 拼到主 `solar-harness.sh`（属下一 sprint）
- 知识库降级 `mirage:nonzero`：本 sprint self-contained（不依赖外部检索）。

## 1. 上游摘要（design sprint → 实施 sprint）

design sprint 的 N5 最终报告应已落 `monitor-reports/gepa-optimize-anything-integration.md`；本 sprint **不重读**全文，仅继承以下钉死决策（contract + PRD 已固化）：

| 决策 | 来源 | Stage 1 实施 |
|------|------|--------------|
| 8 模块 package | contract Required Modules | I1..I8 一一映射 |
| 默认 dry-run / `--execute` 三 budget caps | design §5 安全模型 | I3 CLI + I7 budgets |
| Evaluator subprocess 沙箱 | design §5 | I4 evaluator.py |
| Candidate lineage 11 字段 | design §10 数据模型 | I5 artifact_store.py |
| Operator router 多模态门 | design §4 primitives 映射 | I6 operator_router.py |
| Promote/rollback 单独命令 + 备份 | design §5 + §8 CLI | I8 promote.py |
| 隔离 run 目录 `~/.solar/harness/optimizer-runs/<run_id>/` | design §5 | I5 + IM |
| MVP target = `/tmp/gepa_seed.txt` | contract Hard Safety Rule | IM 演练；其他路径 reject |
| Tests CPU-only + 无 cloud 调用 | PRD Acceptance | IT |

## 2. 包结构

```
integrations/gepa_optimizer/
├── __init__.py        [I1 reviewing]    21 exports, lazy-load, no side effects
├── adapter.py         [I2 pending]      from gepa.optimize_anything import …; config builder; evaluator wrapper; graceful unavailable-package errors
├── cli.py             [I3 pending]      argparse: propose | run | review | promote | rollback | status
├── evaluator.py       [I4 pending]      subprocess JSON evaluator + timeout + env whitelist + RLIMIT fallback
├── artifact_store.py  [I5 pending]      run dirs / candidates / pareto.jsonl / summary.json / audit.log / cache / secret scan
├── operator_router.py [I6 pending]      physical-operators.json 选择 + multimodal gate
├── budgets.py         [I7 pending]      SpendStopper / EvalStopper / WalltimeStopper / PlateauStopper / StopFileStopper
└── promote.py         [I8 pending]      target allowlist / backup / diff / atomic replace / rollback

tests/integrations/gepa_optimizer/
└── test_*.py          [IT pending]      覆盖每模块 + CLI gates + 沙箱 + 全 stopper + promote/rollback

optimizer-runs/<run_id>/  [IM pending]   propose/review/promote/rollback 演练产物（only /tmp/gepa_seed.txt as target）

monitor-reports/gepa-optimize-anything-implementation.md  [IH pending]   最终评估报告
```

## 3. 模块责任矩阵

| 模块 | 依赖 | 关键 API | 安全控制点 |
|------|------|----------|------------|
| `__init__.py` | 无 | lazy-load 21 exports；`__version__` | 无 side effect；不 import gepa 本体 |
| `adapter.py` | I1 | `class GEPAAdapter` 包装 `optimize_anything()`；`build_config()` 包装 `GEPAConfig`；`wrap_evaluator()` | import-time 不调用 gepa；gepa 未安装时优雅退化 (`AdapterError("gepa unavailable")`) |
| `cli.py` | I1 | argparse 6 subcommand | `run` 没有三 budget caps 时 exit 2；`propose` 默认 dry-run；`promote` target allowlist 校验 |
| `evaluator.py` | I1 | `class SubprocessEvaluator(timeout, env_whitelist)` → `EvaluatorResult{score, asi, error?}` | subprocess + `signal.SIGKILL` timeout；env 白名单；RLIMIT_CPU + RLIMIT_AS fallback；exception → ASI-safe diagnostic |
| `artifact_store.py` | I1 | `class ArtifactStore`、`RunRecord`、`CandidateRecord` | secret regex 过滤（`(?i)(api[_-]?key|token|bearer|secret|password)\s*[:=]`）+ append-only 校验 + sha256 cache key |
| `operator_router.py` | I1 + `config/physical-operators.json`（read-only） | `class OperatorRouter`、`OperatorSpec` | 拒绝 disabled / unavailable；image task 要求 operator `input_modalities ⊇ {image}` |
| `budgets.py` | I1 | 5 个 Stopper 类（共抽象基类 `Budget`） | 每个 stopper 给出 structured `StopReason{kind, ts, detail}`；停止后 idempotent |
| `promote.py` | I5 | `class Promoter(allowlist, backup_dir)` | allowlist 默认仅 `/tmp/gepa_seed.txt`；prod 路径 reject；备份用 sha256 命名；rollback 字节级一致 |

## 4. CLI surface（I3 实施细化）

```bash
# 默认 dry-run
python3 -m integrations.gepa_optimizer.cli propose \
  --target /tmp/gepa_seed.txt \
  --evaluator mocked:identity \
  --dataset path.jsonl \
  [--objective "..."] [--background "..."] \
  [--proposer glm-5.1]

# 真跑必须显式 3 budget caps
python3 -m integrations.gepa_optimizer.cli run \
  --target /tmp/gepa_seed.txt --evaluator mocked:identity --dataset path.jsonl \
  --execute --budget-usd 0 --budget-evals 5 --max-wall-time-min 1
# 缺任一 budget → argparse exit 2

# 列 run + candidate
python3 -m integrations.gepa_optimizer.cli review --run <run_id>

# 审批 promote
python3 -m integrations.gepa_optimizer.cli promote \
  --run <run_id> --candidate <c_id> --target /tmp/gepa_seed.txt \
  --backup-dir ~/.solar/harness/backups/

# 撤销
python3 -m integrations.gepa_optimizer.cli rollback --run <run_id>

# 状态查询
python3 -m integrations.gepa_optimizer.cli status --run <run_id>
```

## 5. 数据模型（per design §10，I5 实施）

`~/.solar/harness/optimizer-runs/<run_id>/` 目录结构：

```
<run_id>/
├── seed.txt              复制自 --target（不直读 production；本 sprint 只允 /tmp/gepa_seed.txt）
├── config.json           run-time 配置摘要（含 budgets / proposer model）
├── pareto.jsonl          每行一条 frontier 候选；append-only
├── candidate-c-001.json  schema `gepa.candidate.v1`，11 字段
├── candidate-c-002.json
├── ...
├── summary.json          schema `gepa.run_summary.v1`，含 stopper_triggered / best_candidate_id / total_cost_usd / wall_time_min / promoted=false
└── audit.log             人读 + 时间线 + 所有决策 + spend log
```

`run_id` 格式：`r-<UTC compact>-<sha8>`，例如 `r-20260522T130500Z-a1b2c3d4`。

## 6. 安全模型（per design §5，I3+I4+I5+I7+I8 共同 enforce）

| 维度 | 实施落点 | enforce 方式 |
|------|----------|--------------|
| 默认 dry-run | I3 cli.py | `propose` 子命令 = dry-run；`run` 必须 `--execute` + 三 budget caps |
| Budget caps | I7 budgets.py | spend / evals / walltime 任一越界 → `Budget.tick()` 返回 `StopReason` |
| Plateau stopper | I7 | 末 N 候选 score 改进 < ε → 停止 |
| STOP-file stopper | I7 | 文件 `<run_dir>/STOP` 存在 → 立即停止（运维 escape hatch） |
| Evaluator 沙箱 | I4 evaluator.py | subprocess + `signal.alarm(timeout)` + 子进程 env 白名单 + RLIMIT_CPU/AS |
| Secrets 过滤 | I5 artifact_store.py | 写盘前 regex 扫描；命中 → 直接 reject (`SecretLeakError`) |
| Candidate lineage | I5 | 11 字段强制；缺字段抛 `ArtifactSchemaError` |
| Multimodal gate | I6 operator_router.py | image task 要求 operator `input_modalities ⊇ {image}` |
| Promote allowlist | I8 promote.py | 默认 `["/tmp/gepa_seed.txt"]`；prod path → `PromotionTargetRejected` |
| Backup + rollback | I8 | 备份用 `<backup_dir>/<sha256>.bak`；rollback 字节一致校验 |

## 7. 测试矩阵（IT 实施）

per PRD Acceptance + contract Done：

| 模块 | 测试覆盖 |
|------|----------|
| `__init__` | import 无 side effect / `__all__` 完整 / py_compile |
| `adapter` | gepa 未安装 → `AdapterError`；安装时 namespace 正确；wrap_evaluator 透传 |
| `cli` | propose 默认 dry-run；`run --execute` 缺 budget → exit 2；review/promote/rollback/status 各 1 路径 |
| `evaluator` | timeout 返回 structured failure；异常 → ASI-safe；env 白名单生效 |
| `artifact_store` | candidate lineage schema 校验；secret 写入 reject；cache sha256 命中 |
| `operator_router` | 选 enabled / available；image 任务无 image modality → reject |
| `budgets` | 5 stopper 各 1 case；structured reason；idempotent |
| `promote` | prod target reject；MVP target /tmp 接受；rollback 字节一致 |

测试要求：

- **CPU only**，无 cloud 调用，无真 GEPA optimization run
- `tmp_path` fixture 隔离
- `monkeypatch` env 注入
- 总耗时 < 30s

## 8. MVP 演练（IM 实施）

`propose → review → promote → rollback` 全链路，**target 严格限 `/tmp/gepa_seed.txt`**：

```bash
# step 1: seed
echo "you are a helpful assistant." > /tmp/gepa_seed.txt

# step 2: propose (mocked evaluator, mocked proposer)
python3 -m integrations.gepa_optimizer.cli propose \
  --target /tmp/gepa_seed.txt \
  --evaluator mocked:identity \
  --dataset tests/integrations/gepa_optimizer/fixtures/mini_dataset.jsonl

# step 3: review → 列 candidate
python3 -m integrations.gepa_optimizer.cli review --run <run_id>

# step 4: promote 最佳 candidate 到 /tmp/gepa_seed.txt
python3 -m integrations.gepa_optimizer.cli promote \
  --run <run_id> --candidate c-001 --target /tmp/gepa_seed.txt \
  --backup-dir ~/.solar/harness/backups/

# step 5: 验证 promote 后内容
cat /tmp/gepa_seed.txt

# step 6: rollback
python3 -m integrations.gepa_optimizer.cli rollback --run <run_id>

# step 7: 验证 rollback 字节一致
diff /tmp/gepa_seed.txt <(echo "you are a helpful assistant.")  # 期望无差异
```

**禁止**：任何步骤指向 production path；任何 cloud LLM 调用；任何 GEPA 真跑（mocked evaluator + mocked proposer only）。

## 9. 失败恢复 / 观测

- `audit.log` 每步落盘；`monitor-reports/gepa-optimize-anything-implementation.md` 引用 audit.log
- evaluator timeout → 候选标 `score=null, asi=evaluator_timeout`，run 继续（不全 abort）
- secret leak → 立即 abort + 删该 candidate JSON；audit.log 标 `secret_leak_aborted`
- promote 期间 target 被外部修改 → diff check → abort（保护现状）
- rollback 备份缺失 → abort + 提示手动恢复
- 任一 budget 越界 → `StopReason` 写 summary.json，标 `stopper_triggered`

## 10. 兼容性 / 冲突 / 降级

**冲突**：

- GEPA package install 全局风险：本 sprint 不全局安装；I2 adapter.py 处理 `from gepa.optimize_anything import …` ImportError 优雅退化（returns `AdapterError("gepa unavailable")`）
- Solar `physical-operators.json` 现有 schema：I6 read-only 引用，禁止改 registry
- Solar `solar-harness` shell wrapper：本 sprint 不修改；CLI 通过 `python3 -m integrations.gepa_optimizer.cli` 直接调用；shell wrapper 接入属下一 sprint

**依赖**：

- I2..I7 全部依赖 I1（package init）
- I8 依赖 I5（artifact_store）
- IT 依赖 I2..I8
- IM 依赖 IT
- IH 依赖 IM

**降级**：

- gepa package 未安装 → adapter import 自动捕获 ImportError；CLI `run` 显示 "gepa unavailable" 退出码 3
- mirage degraded 持续 → 本 sprint self-contained
- monitor-reports/gepa-optimize-anything-integration.md（design sprint 最终报告）若未产 → IH 仍可独立产出本 implementation 报告，不阻塞

## 11. 非目标（明确禁止）

- 不接入 `solar-harness optimizer gepa ...` shell wrapper（下一 sprint）
- 不真跑 cloud LLM 优化循环
- 不全局安装 GEPA package
- 不让 promote allow 任何非 `/tmp/gepa_seed.txt` 路径
- 不修改 Solar hooks / skills / prompts / config / operator registry
- 不修改 `~/.solar/STATE.md`、epic.*、其他 sprint artifact
- 不打开 live tmux pane / 不重启 harness
- 不打印或落盘 secrets
- 不使用乐观词

## 12. 给 IH + 下一 sprint 的接力

IH 节点必须产 `monitor-reports/gepa-optimize-anything-implementation.md`：

- PRD Acceptance 6 条逐项对照（含命令输出截屏 / 文件路径证据）
- DAG 全节点 passed 证据 (`graph-scheduler validate` + `node_results` 摘录)
- "current problem" + "next action" 显式段落
- 下一 sprint outline（shell wrapper `solar-harness optimizer gepa ...` 接入 + 第二批 use case）

下一 sprint 建议（IH 留给 PM 决策）：

- 主 `solar-harness.sh` 加 `optimizer gepa` 子命令路由到 `python3 -m integrations.gepa_optimizer.cli`
- 第二批 use case：skill template tuning（仍 staging only）
- 引入 cloud LLM 真跑（在隔离 budget + audit 下）
