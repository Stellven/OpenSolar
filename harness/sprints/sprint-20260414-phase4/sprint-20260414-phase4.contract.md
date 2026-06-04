# Sprint Contract — sprint-20260414-phase4
Created: 2026-04-14
Status: ready_for_builder
Project: /Users/lisihao

## 需求

SkillRL Phase 4: 将 skill-evolve.ts 接入 Solar 运行时，形成 推荐→执行→反馈→Q-update 闭环。

## Done 定义

- [ ] **D1**: `bun skill-evolve.ts select coding` 输出合法 JSON，无数据时输出 `{"skill":"none"}`
- [ ] **D2**: `buildNiumaCall({model:'glm-5', task:'实现OAuth'})` 返回 `recommendedSkill` 非空 (有数据时)
- [ ] **D3**: `skipSkillRecommend: true` 时 `recommendedSkill` 为 undefined
- [ ] **D4**: system prompt 包含 `Recommended Skill Pattern` (有推荐时)
- [ ] **D5**: hook Skill 分支同时调用 evolve.ts record 和 skill-evolve.ts record
- [ ] **D6**: 总超时 ≤ 5s

## 范围

- 包含: skill-evolve.ts 新增 select + call-niuma.ts 推荐注入 + hook 记录
- 不包含: Phase 5 端到端验证 / 新 hook 文件 / settings.json 变更

## 约束

1. 不新建 hook 文件 (增强现有 evolve-auto-record.sh)
2. NiumaCallResult 扩展全部 optional (向后兼容)
3. skill-evolve select timeout = 2s
4. hook 记录后台运行 (&)
5. 提取 scoreSkills() 共享函数避免 select/recommend 逻辑重复

## 实现文件清单 (建设者完成后填写)

> (待填)

## 审判官评估维度

1. 功能完整性: D1-D6 逐条检查
2. 向后兼容: skipSkillRecommend + 无数据 graceful 退化
3. 合约合规: 不超范围
4. 代码质量: 错误处理、超时、后台进程
