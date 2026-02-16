# Mission
人格提示词系统 P0 优化实现与验证

# Constraints
- Token 成本可控 (当前 ~683)
- 输出一致性 > 90%

# Current Plan (Top-5)
1. ✅ KNOBS 带解释优化
2. ✅ JSON Schema 结构定义
3. ✅ Few-shot 示例
4. ✅ 三模型验证通过
5. 🔧 MCP 服务修复 (httpx)

# Decisions (Why)
- [2026-02-16] Few-shot 示例效果好，输出一致性 100%
- [2026-02-16] Token 从 ~410 增至 ~683，值得投入

# Progress
- Done: 三个 P0 优化全部实现并验证
- Done: MCP brain-router 修复 (pip install httpx)
- Done: 验证结果保存 sys_favorites ID=75
- In-Progress: 等待重启后继续

# Next Actions (Exact)
- [ ] 重启 Claude Code
- [ ] 验证 MCP 服务正常
- [ ] 用 mcp__brain-router__complete 测试不同模型
