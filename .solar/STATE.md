# Mission
增强 Solar 记忆与长程工作能力，建立抗失忆工作流

# Constraints
- 不依赖玄学，靠流程+落盘
- 文件要短、硬、可执行
- 压缩发生也不丢态势
- 每个 Next Action 必须是可复制执行的命令

# Current Plan (Top-5)
1. 创建 STATE.md + DECISIONS.md + 更新 CLAUDE.md
2. 实现自动检查点机制 (hooks)
3. 验证压缩后恢复能力
4. 文档化最佳实践
5. 推广到其他项目

# Decisions (Why)
- [2026-02-12] 使用三文件架构（STATE/DECISIONS/CLAUDE）而非单一状态文件
  原因：职责分离，STATE 变化频繁，DECISIONS 追加式，CLAUDE 相对稳定
  影响：每次启动读 2 个文件而非 1 个
  回滚：合并回单文件

- [2026-02-12] 引入冲刺节奏控制 + LOG 目录
  原因：长任务成功率需要靠流程保证，不能只靠记忆
  结构：开场30s读态势 → 执行只做列表 → 收尾2分钟写回
  LOG：cmd.md/bench.md/errors.md/todo.md (轻量 event-sourcing)
  回滚：删除 LOG 目录，恢复自由执行

# Progress
- Done:
  - 小爱邮件监控修复 (prompt 策略调整)
  - 诊断失忆根因 (上下文当内存)
  - 创建抗失忆三文件架构 (STATE.md + DECISIONS.md + CLAUDE.md 更新)
  - git commit ec4af22 + ded70db
  - 验证新会话读取态势 ✅ (2026-02-12 本次会话成功)
  - GLM-5 注册到 brain-router (server.py + collab_model_profiles)
  - 冲刺节奏控制铁律 (sprint-rhythm.md)
  - LOG 目录结构 (.solar/LOG/cmd|bench|errors|todo.md)
  - 第零原则固化 (对话降级为缓存，文件是唯一真相源)
  - 铁律实现修正: 不等"感觉"，每完成一步立即写文件
  - "先读后写"强制机制 ✅ (state-read-tracker.sh + state-read-enforcer.sh)
  - Task-Specific SOP 体系 ✅ (5类任务SOP + ARCH.md + RFC模板 + 实验注册表)
  - 报告工程化流水线模板 ✅ (STATE/OUTLINE/SOURCES/NOTES/CLAIMS)
  - /insight 集成 REPORT 模板 ✅ (initReportDir + 各Phase检查点)
  - /insight 升级四专家 ✅ (增加 GLM-5 马王，角色 synthesizer)
  - insight-v2.ts max_tokens 修复 ✅ (DeepSeek V3 限制 8192，四专家全正常)
  - Phase 1.5 研究搜索阶段 ✅ (WebSearch 生成查询 + 收集文献 + SOURCES.md)
  - RAG架构深度洞察测试通过 ✅ (92篇文献, 4专家大纲, 互评, 综合5章节)
  - 小爱切换 GLM-5 ✅ (通过 MCP 实现，绕过 OpenClaw 模型库限制)
- In-Progress: 无
- Blocked: 无

# Next Actions (Exact)
- [ ] 推广到其他项目 (可选)
- [ ] 实现自动检查点 hooks (可选)
- [ ] 文档化最佳实践 (可选)
