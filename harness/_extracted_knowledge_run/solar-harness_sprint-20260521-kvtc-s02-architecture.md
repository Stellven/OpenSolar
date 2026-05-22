# solar-harness_sprint-20260521-kvtc-s02-architecture（passed）

## 功能模块

- Sprint 切片：S02 `architecture`（KVTC 接入质量修复 · 架构设计与接口契约）。
- 目标：基于上游需求矩阵，产出系统分层、接口、数据模型、兼容策略与迁移方案（不写业务代码）。

## 用户价值

- 给下游 S03/S04/S05 提供可执行的“架构合同”（接口签名、schema 版本、迁移与回滚、观测与门禁策略）。
- 通过明确 Stop Rules / 非目标，降低越权修改、不可复现验证、以及 scope 漂移风险。

## 设计结构（摘要）

- 控制面：UI gate（default_off 状态机）、服务端路由兼容策略、feature flags。
- 数据面：codec / cache / calibration / recon gate 的边界与调用路径。
- 状态：calibration v1→v2 共存窗口、side-band 元数据策略、旧块永久可读承诺。
- 可观测：指标、日志（`recon_gate.jsonl`）、告警与 ATLAS 修复 hook 的边界。

## 关键文件（仓库内）

- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/*.contract.md`
- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/*.design.md`
- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/*.eval.md`
- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/*.dispatch.md`
- `harness/sprints/sprint-20260521-p0-修复-thunderomlx-kvtc-接入质量-基于-arxiv-2511-01815-iclr-2026-s02-architecture/*.status.json`

## 核心 API / 命令（从设计中抽取）

- 归档导出：`/Users/lisihao/Solar/scripts/export-harness-artifacts.sh --commit`
- 兼容/回滚（范式）：通过 feature flag/env 控制 v1/v2 或禁用分支，要求“可立即回滚”。
- 公共 API（范式）：`recon_gate.evaluate(meta, decoded, expected)` 要求签名稳定、扩展 kwargs 必须默认值兼容。

## 验证方法（从 eval 中抽取）

- 验收项：
  - 覆盖 control/data plane、状态、失败恢复与观测。
  - 接口边界与旧系统兼容明确。
  - 冲突、依赖与降级策略明确。
- 约束验证：
  - 不修改 ThunderOMLX 源码（read-only 扫描仅用于补全架构合同证据）。
  - schema 全含 `schema_version`。
  - 文档自包含，可离线审计。

## 风险边界

- S02 为“合同”，不等价于实现；真实 pytest / staging / CI 回归由下游 sprint 负责。
- 知识检索降级（mirage degraded）时，证据链应优先来自源码实测引用与可复现脚本片段。

## 后续改进

- 将本 sprint 的关键接口与 schema 的“最小可机读摘要”同步到统一索引（便于下游自动生成实现 TODO / CI gate）。

