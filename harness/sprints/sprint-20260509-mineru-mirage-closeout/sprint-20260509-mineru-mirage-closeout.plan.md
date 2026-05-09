# Plan — MinerU + Mirage Full Closure

> Sprint: sprint-20260509-mineru-mirage-closeout
> Author: planner
> Date: 2026-05-09
> Inputs: contract.md (A1-A7), prd.md (FR-1..7), design.md (component contracts §2, persistence §3, ADR §4)

## §0 Plan Scope & Discipline

本 plan 把 sprint 拆成 **4 个独立可 evaluate 的 builder slice**。规则：

1. **slice 不跨界**：S1 不许碰 Mirage，S3 不许碰 MinerU；共享变更（如 `/integrations` UI）必须放 S4。
2. **每 slice 必须独立通过 evaluator**：fresh shell 重跑探针，不允许"在我机器上能跑"。
3. **任何 slice 触发 Stop Rule → 立即停手 + 写 round-2 contract 修订请求**，不自行扩 scope。
4. **builder 不许加新 vendor 或新 npm 依赖**（除非 design §2 已枚举）。

## §1 Slice Topology

```
   ┌────────────────┐
   │ S1: MinerU     │
   │  Runtime+Doctor│ ─── 必须 first（venv 是 S2 前置）
   └───────┬────────┘
           │
           ▼
   ┌────────────────┐         ┌────────────────┐
   │ S2: PDF        │         │ S3: Mirage     │
   │  Extract+Audit │         │  SDK/FUSE+Mount│ ── 与 S1/S2 并行
   └───────┬────────┘         └───────┬────────┘
           │                          │
           └──────────┬───────────────┘
                      ▼
           ┌────────────────┐
           │ S4: Status UI  │ ── 必须 last (依赖 S1-S3 的真实 doctor 信号)
           │  + BG Isolation│
           └────────────────┘
```

依赖：S2 ← S1 (硬依赖); S3 ⫫ S1/S2 (并行); S4 ← S1∧S2∧S3 (硬依赖)

## §2 Slice S1 — MinerU Runtime Foundation

### Deliverables
| # | 文件/产物 | 说明 |
|---|----------|------|
| D1.1 | `vendor/mineru/bootstrap.sh` | 单条命令产生 `.venv`、安装依赖、生成 `requirements.lock` |
| D1.2 | `vendor/mineru/.venv` | 真实可激活 venv，`python -m pip check` 通过 |
| D1.3 | `vendor/mineru/install-report.json` | 含 python 版本、平台、wheel 列表、安装耗时 |
| D1.4 | `solar-harness wiki mineru-doctor` 升级 | 输出 design §2.1 schema；`venv` 字段基于 `pip check` |

### Gates (必须全部 pass 才能交付)
- **G1.A1** (contract A1): `solar-harness wiki mineru-doctor --json` 返回 `venv=ok` （fresh shell）
- **G1.S1**: `bash vendor/mineru/bootstrap.sh` 在 5 分钟内零交互完成
- **G1.S2**: `python -c "import <核心模块>"` 在 venv 内成功（具体模块名由 vendor 文档决定）
- **G1.M1** (manual): doctor 报错时给出 actionable 错误（缺什么、装什么命令）

### Stop Conditions → 触发 round-2 修订
- 若 vendor 必须 GPU/CUDA，记录 `reports/mineru-cpu-fallback-2026-05-09.md` 并把 contract A1 标 unsupported
- 若 wheel 链冲突无解（pip 锁死），停手；contract 需要松绑"venv=ok"判定

### Round-Retry Trigger
- evaluator 失败 → 把失败探针输出贴入 round-2 contract
- planner 重审 contract，决定是放宽 G1 还是加 builder 时间预算

## §3 Slice S2 — PDF Deep Extraction + Provenance

### Deliverables
| # | 产物 | 说明 |
|---|------|------|
| D2.1 | `solar-harness mineru extract <pdf>` 命令 | 接受 PDF 路径，调 vendor pipeline，输出 markdown |
| D2.2 | Obsidian `references/<slug>/` 内容 | 至少 2 个 PDF 端到端产物，含 design §5 provenance frontmatter |
| D2.3 | `~/.solar/reports/mineru-audit-<ts>.json` | source → generated_pages 列表 |

### Gates
- **G2.A2** (contract A2): audit report 列出 ≥ 2 个 source 的 generated pages
- **G2.S1**: 至少一个 PDF 含数学公式或表格，验证 layout detection 实际工作
- **G2.S2**: provenance frontmatter 含 `source_pdf_sha256` 字段（可追溯）
- **G2.M1** (manual): 抽样检查一个 generated page 内容与原 PDF 对应位置语义一致

### Stop Conditions
- 若用户的 PDF 触发 vendor crash（OOM/segfault），降级到记录"已知不兼容 PDF 列表"，不强求覆盖所有
- 若 OCR 时间 > 30 分钟/PDF，加 `--background` 强制后台跑，避免阻塞

### Round-Retry Trigger
- audit report 行数 < 2 → 必须在 round-2 增加 PDF 数量或调整 PDF 选择策略

## §4 Slice S3 — Mirage SDK/FUSE Decision + Mount Completeness

### Deliverables
| # | 产物 | 说明 |
|---|------|------|
| D3.1 | `reports/mirage-sdk-fuse-decision-2026-05-09.md` | ADR，含 design §4 五段结构 |
| D3.2 | Mirage mount 配置 | 至少 `/knowledge /raw /sprints /db /qmd` 可达 |
| D3.3 | `solar-harness mirage doctor` 升级 | 输出 design §2.2 schema |
| D3.4 | Drive 凭据探活 | 有 token 时真挂载；无 token 时 `dead_end` + `unblock.env_var` |

### Gates
- **G3.A4** (contract A4): ADR 文件存在且包含 5 段
- **G3.A5** (contract A5): `solar-harness mirage doctor --json` 列出 5+ mount，全部 `status != down`
- **G3.S1**: `solar-harness mirage exec -- 'cat /knowledge/README.md'` 能读到内容（或合理 404 if 无 README）
- **G3.S2**: ADR 决策选 wrapper 时，明确说明 macFUSE/SIP 测试结果

### Stop Conditions
- 若 macFUSE 安装弹系统授权且用户拒绝 → 走 ADR option B（wrapper），不强制
- 若 Drive OAuth 流程要求浏览器交互 → 标 dead_end，不阻塞 sprint

### Round-Retry Trigger
- ADR 不含 5 段 → 退回重写
- mount 数 < 5 → contract 需明确允许的最小 mount 集

## §5 Slice S4 — Status UI Precision Labels + Background Isolation

### Deliverables
| # | 产物 | 说明 |
|---|------|------|
| D4.1 | `/integrations` 前端改造 | 4 档标签 (basic/default/closed/dead) + evidence 字段 |
| D4.2 | `/integrations` JSON schema | 符合 design §2.4 |
| D4.3 | JSON schema 测试 | 单测覆盖 4 种 label 渲染 |
| D4.4 | `~/Library/LaunchAgents/io.solar.qmd-mcp.plist` | QMD MCP launchd 守护 |
| D4.5 | `~/Library/LaunchAgents/io.solar.mineru-worker.plist` | 后台 worker，含 idle guard |
| D4.6 | idle guard 实现 | 检测用户活跃即降速/暂停 |

### Gates
- **G4.A3** (contract A3): `solar-harness wiki qmd-mcp status` 在 fresh shell 仍显示 v4+v6 双协议
- **G4.A6** (contract A6): `/integrations` 视觉显示 4 档 + JSON schema test 通过
- **G4.A7** (contract A7): 触发后台 PDF 抽取，前台 shell 能立即敲下一条命令（< 2s 阻塞）
- **G4.S1**: `launchctl list | grep io.solar` 列出 ≥ 2 个 service
- **G4.S2**: idle guard 在用户敲键盘时实际降速（日志可见）

### Stop Conditions
- 若 launchd 因沙盒/权限失败 → 降级 tmux session，UI 标 `default_usable`
- 若前端框架不支持新 schema → 加 `status_legacy` 兼容字段双发，6 周后弃用

### Round-Retry Trigger
- 任一 fresh-shell 探针挂掉 → 探针输出入 round-2 contract
- 视觉 QA 失败 → 截图 + DOM diff 入 round-2

## §6 Cross-Slice Sequencing

| 步骤 | Slice | 阻塞条件 |
|---|---|---|
| 1 | S1 单飞 | venv 必须先就绪 |
| 2 | S2 + S3 并行（S1 完成后启动 S2；S3 任意时刻开） | S2 等 S1，S3 不等 |
| 3 | S1∧S2∧S3 全 pass 后，S4 启动 | S4 必须看到真实 doctor 信号 |
| 4 | S4 完成后，evaluator fresh shell 全量探针 | 任一挂掉 = sprint FAIL |
| 5 | sprint PASS → status=passed，UI 公开新四档标签 | — |

## §7 Constraints Carried Forward

| ID | 来源 | 如何保证 |
|---|---|---|
| C1 (无 GPU) | PRD §8 | S1 bootstrap 默认 CPU 路径；S2 不调 CUDA API |
| C2 (FUSE 权限) | PRD §8 | S3 默认走 wrapper；FUSE 仅 opt-in |
| C3 (Drive 凭据) | PRD §8 | S3 缺 token 时 dead_end，不强求 |
| C4 (loopback only) | PRD §8 | S4 launchd plist 显式 `127.0.0.1` + `[::1]`，不绑 0.0.0.0 |
| C5 (持久化) | PRD §8 | S4 用 launchd；fallback tmux 时 UI 降级 |
| C6 (前台 ≤ 2s) | PRD §8 | S2 默认后台；S4 idle guard |
| C7 (向后兼容) | PRD §8 | S4 保留 `status_legacy` 字段 6 周 |

## §8 Open Questions Routed to Builder Discovery

PRD §10 的 OQ1-OQ6 在 design §8 已大部分决策。剩余 builder 自行判断的：
- **OQ-B1**: `bootstrap.sh` 用 uv 还是 pip？（builder 选；只要 G1.S1 5 分钟内通过即可）
- **OQ-B2**: launchd plist 的 `KeepAlive` 用 `SuccessfulExit=false` 还是 `Crashed=true`？（builder 选；只要 G4.A3 通过即可）
- **OQ-B3**: idle guard 的具体阈值（HIDIdleTime ≥ 60s 还是 30s）？（builder 选；G4.S2 通过即可）

其他越界问题 → builder 必须停手，写入 `~/.solar/harness/sprints/sprint-20260509-mineru-mirage-closeout.handoff.md` 询问 planner。

## §9 Sprint-Level Definition of Done

继承 contract A1-A7 全部 pass + 以下：

- [ ] 4 个 slice 各自 evaluator pass（G1/G2/G3/G4 全绿）
- [ ] Fresh-shell 全量探针 pass（design §6）
- [ ] ADR `mirage-sdk-fuse-decision-2026-05-09.md` 5 段完整
- [ ] `~/.solar/reports/mineru-audit-*.json` 至少 1 个含 ≥ 2 source
- [ ] `/integrations` UI 不再出现单一 `ok` 字符串（grep 验证）
- [ ] `events.jsonl` 含 sprint 完整生命周期事件

## §10 No-Scope-Creep Notice

Builder **不许**：
- 改 MinerU 替代为其他 PDF 工具（即使更快）
- 加 Drive 之外的云盘集成（OneDrive、iCloud）
- 重构 `solar-harness mirage exec` 命令签名
- 加 GPU 加速路径
- 新增 vendor 目录

任何超出 design §2 接口/§9 out-of-scope 的修改 → 必须先写 round-2 contract 修订请求，得 planner 批准后才能动。

