# Mission
验证 EmotionPrompt (PUA) 技术是否真实提升代码质量

# Constraints
- 必须使用 MCP brain-router 调用大模型（不能用静态脚本）
- A/B 测试：CONTROL vs EMOTION 两组对比
- 测试任务：实现 TypeScript LRU Cache
- 评估标准：10分制质量评分

# Current Plan (Top-5)
1. ✅ 确认 EmotionPrompt 已集成到 buildNiumaCall
2. ✅ 创建完整 A/B 测试设计文档
3. 🔧 解决 MCP brain-router 工具不可用问题
4. ⏳ 实际运行 A/B 测试
5. ⏳ 对比分析 CONTROL vs EMOTION 结果

# Decisions (Why)
- [2026-02-20] MCP 诊断：mcp.json 配置正确，服务显示已连接，但工具未注册
- [2026-02-20] 需要重启 Claude Code 让它重新加载 MCP 配置

# Progress
- Done: 论文证据收集（arXiv 2307.11760）
- Done: 确认 EmotionPrompt 集成到 call-niuma.ts
- Done: 创建 /tmp/emotion-prompt-ab-comparison.md
- Done: MCP 配置诊断（mcp.json 存在且正确）
- Done: 确认 brain-router 服务已连接（claude mcp list）
- Blocked: MCP 工具调用失败（需要重启 Claude Code）
- In-Progress: 等待重启后测试 MCP 调用

# Next Actions (Exact)
- [ ] 重启 Claude Code
- [ ] 测试调用 mcp__brain-router__list_models
- [ ] 运行 CONTROL 组：调用 glm-4-plus 实现 LRU Cache（无 emotion）
- [ ] 运行 EMOTION 组：调用 glm-4-plus 实现 LRU Cache（有 emotion）
- [ ] 评分对比并得出结论
