# Solar Harness 可用功能归档提交（2026-05-22）

> 说明：按自动化要求本应写入 `/Users/lisihao/.solar/extracted_knowledge/`，但当前执行环境对该目录写入受限（operation not permitted）。
> 本次先把知识产物落在仓库内，便于审阅与手动同步。

## 功能模块

- Harness 产物归档：将 `~/.solar/harness` 中 **status=passed** 的 sprint 产物镜像到 Solar 仓库 `harness/`。
- 运行入口：`/Users/lisihao/Solar/scripts/export-harness-artifacts.sh --commit`。
- 提交约束：仅允许提交 `harness/` 与（如有变更）`scripts/export-harness-artifacts.sh`。

## 用户价值

- 把“已验证可用”的 harness 能力（contracts/design/eval/dispatch/events）沉淀到代码仓库，便于审计、复用、回滚与协作。
- 跳过非 passed 状态，降低把未完成/失败方案误当稳定能力的风险。

## 设计结构

- 仓库侧产物根：`/Users/lisihao/Solar/harness/`
- 关键分组：
  - `harness/sprints/<sprint_id>/`：每个 sprint 的结构化产物（`*.status.json`、`*.contract.md`、`*.design.md`、`*.eval.md`、`*.dispatch.md`、`*.events.jsonl` 等）。
  - `harness/coordinator.sh`：协调器能力与归档配套逻辑。
  - `harness/brain/lessons.jsonl`：经验/教训沉淀。

## 关键文件（本次归档的增量）

- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/`
- `harness/coordinator.sh`
- `harness/brain/lessons.jsonl`

## 核心 API / 命令

- 导出并提交：`/Users/lisihao/Solar/scripts/export-harness-artifacts.sh --commit`
- 状态门禁：active/reviewing/queued/failed/cancelled/superseded/interrupted 一律跳过（以 sprint `status` 为准）。

## 验证方法

- 产物齐全性：检查 sprint 目录至少包含 `*.status.json`、`*.contract.md`、`*.design.md`、`*.eval.md`。
- 提交范围：`git show --name-only <sha>` 不应包含 `harness/` 之外的路径（允许 `scripts/export-harness-artifacts.sh` 例外）。
- 状态统计：以 `~/.solar/harness/sprints/*.status.json` 中的 `.status` 聚合为准。

## 风险边界

- knowledge 检索源可能降级（本次记录为 mirage degraded），因此要求产物自包含、可离线审计。
- “归档通过”只表示产物验收通过，不等价于下游代码已落地；下游仍需按 handoff 推进。

## 后续改进

- 产出机器可读的 export report（含 exported/skip 统计）落盘到 `harness/_reports/`，避免仅依赖 stdout。
- 打通 `harness/_extracted_knowledge_fallback/` → `/Users/lisihao/.solar/extracted_knowledge/` 的同步链路，减少重复写入与权限差异导致的失败。

## 手动同步到 extracted_knowledge

> 运行环境允许时，将本目录内容复制到本机知识提取目录：
>
> - `cp -R /Users/lisihao/Solar/harness/_extracted_knowledge_run/* /Users/lisihao/.solar/extracted_knowledge/`

