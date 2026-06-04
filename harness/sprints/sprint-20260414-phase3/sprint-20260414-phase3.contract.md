# Sprint Contract — sprint-20260414-phase3
Created: 2026-04-14
Status: ready_for_builder
Project: /Users/lisihao

## 需求

实现 SkillRL Phase 3: 创建 `~/.claude/core/solar-farm/skill-evolve.ts` — 独立的技能 Q-learning 引擎，提供 record/recommend/decay/trace/report/distill/promote 8 个 CLI 命令。

## Done 定义

- [ ] **D1**: `record` 命令正确更新 Q-value (从 0.5→0.55 after pass, alpha=0.1) 和 Beta(alpha+1 on pass)
- [ ] **D2**: `recommend coding` 在 5x pass + 5x fail 后正确排序 (高分在前)
- [ ] **D3**: `decay --dry-run` 报告正确的过期数量；无 dry-run 时 Q 向 0.5 收敛
- [ ] **D4**: `trace-start` + 多次 `record` + `trace-finish` 正确回传折扣奖励 (step2 涨幅 > step1)
- [ ] **D5**: `report` 输出格式正确，覆盖 top/bottom/coverage 三部分
- [ ] **D6**: `distill --dry-run` 识别 avg_quality<0.4 的技能并列出候选

## 范围

- 包含: 新建 `skill-evolve.ts` + `skill_executions` 表
- 不包含: 修改 evolve.ts / skill-retriever / buildNiumaCall / Hook

## 约束

1. 独立于 evolve.ts (不 import)
2. 数据库: `~/.solar/skill-index.db`
3. Runtime: Bun + bun:sqlite
4. Thompson Sampling 复制 (不共享)
5. trace-id 路径: `~/.solar/.current-skill-trace-id`
6. promote 仅日志推荐 (skills_meta 无 layer 字段)
7. distill 通过 Bun.spawn 调 trace2skill.ts

## 实现文件清单 (建设者完成后填写)

> (待填)

## 审判官评估维度

1. **功能完整性**: D1-D6 逐条检查
2. **代码质量**: Q-update 数学正确性、SQLite 参数化、错误处理、WAL + busy_timeout
3. **合约合规**: 不碰 evolve.ts / skill-retriever / buildNiumaCall
4. **独立性**: 零外部 import (除 bun:sqlite, node:os, node:path, node:fs)
5. **可维护性**: 与 evolve.ts 同构风格
