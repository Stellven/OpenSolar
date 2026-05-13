# Sprint Contract — sprint-20260414-phase5
Created: 2026-04-14
Status: ready_for_builder
Project: /Users/sihaoli

## 需求

SkillRL Phase 5: 端到端验证。创建 E2E 测试脚本验证完整闭环 (Hook→record→DB→select→call-niuma)。

## Done 定义

- [ ] **D1**: E1 Hook 管线 — 模拟 Skill stdin → skill_executions 有记录
- [ ] **D2**: E2 Q-learning — 5x pass/fail 后 select 返回高分技能
- [ ] **D3**: E3 MCP feedback — 直接调 skill_feedback 后两表一致
- [ ] **D4**: E4 buildNiumaCall — recommendedSkill 非空 + system prompt 含推荐
- [ ] **D5**: E5 Decay+Report — report 输出覆盖 top/bottom/coverage
- [ ] **D6**: 5/5 PASS，测试数据已清理

## 范围

- 包含: 新建 test-skillrl-e2e.ts + 运行验证
- 不包含: 修改任何现有代码

## 约束

1. 测试数据前缀 `e2e-` 开头，便于清理
2. 测试完成后必须清理所有 e2e- 数据
3. E4 可以用 import 直接调 buildNiumaCall (Bun 支持 TS import)
4. E1 hook 测试需要 sleep 等待后台进程
