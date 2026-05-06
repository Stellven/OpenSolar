# Solar Harness 路线图

> 来源: 2026-04-14 业界对标分析 + Phase 1-3 实施

## 已完成

### Bugfix
- [x] 监控中心快捷指令无法使用 (stdin 绑定 /dev/tty)
- [x] Sprint 显示编号而非需求描述 (title 字段)

### P0 — 全自动协同
- [x] 协调器守护进程 (coordinator.sh)
- [x] Persona 自动状态推进 (planner/builder/evaluator)
- [x] Monitor 集成协调器 (后台启动 + 日志 + 状态)

### P1 — 防护机制
- [x] Plan-before-build (planning/approved 新状态)
- [x] Git worktree 隔离 (builder 独立工作树)
- [x] 质量门禁 (gate_check: 文件存在 + schema + FAIL检测)

### P2 — 扩展能力
- [x] Webhook/API 触发 (bun HTTP server, port 9876)
- [x] 结构化 Agent 输出 (validate.sh schema 校验)
- [x] 自动检查点 (git tag checkpoint/{sid}/{status}/{time})

## 待评估
- [ ] Agent 间消息协议 — 协调器已覆盖 80%，等真实使用暴露需求
- [ ] Task 依赖 DAG — 等需要并行多任务时实现

## Sprint 生命周期 (v2.0)

```
drafting → active → planning → approved → reviewing → passed
                     ↑ Builder    ↑ Evaluator    ↓
                     写计划       审批计划    FAIL → 打回
```

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                    Solar Harness v2.0                     │
├──────────┬──────────┬──────────┬────────────────────────┤
│ 规划者    │ 建设者    │ 审判官    │ 监控+协调器            │
│ (Opus)   │ (GLM)    │ (GLM)    │ coordinator.sh         │
│          │ worktree │          │ + monitor.sh           │
├──────────┴──────────┴──────────┴────────────────────────┤
│ gate_check (质量门禁) + validate.sh (schema 校验)        │
├─────────────────────────────────────────────────────────┤
│ auto_checkpoint (git tag) + rollback                     │
├─────────────────────────────────────────────────────────┤
│ webhook-server.ts (port 9876) — curl/Slack/GitHub        │
└─────────────────────────────────────────────────────────┘
```

## 独有优势
- Meta-harness 自进化
- D&D 人格 10 旋钮
- 7+ 模型多厂商路由
- Sprint 合约生命周期 (8 状态)
- 全自动协同 (协调器 + tmux send-keys)
- Plan-before-build (防跑偏)
- Git worktree 隔离 (防冲突)
- 质量门禁 + Schema 校验 (系统级强制)
- 自动检查点 + 回滚 (git tag)
- Webhook API (外部触发)
- 实时监控仪表盘 (6 快捷键)
