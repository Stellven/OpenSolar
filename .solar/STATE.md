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

# Progress
- Done:
  - 小爱邮件监控修复 (prompt 策略调整)
  - 诊断失忆根因 (上下文当内存)
  - 创建抗失忆三文件架构 (STATE.md + DECISIONS.md + CLAUDE.md 更新)
- In-Progress:
  - 验证新架构有效性
- Blocked: 无

# Next Actions (Exact)
- [x] 创建 .solar/STATE.md (本文件)
- [x] 创建 .solar/DECISIONS.md
- [x] 更新 CLAUDE.md 加入铁律指令
- [ ] git add -A && git commit -m "feat: 抗失忆工作流 - STATE/DECISIONS 架构"
- [ ] 验证：新会话启动时能否正确读取态势
