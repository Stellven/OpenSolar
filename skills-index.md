# Skills 索引 (按需加载)

> 只加载索引，需要时读取完整 skill

| Skill | 路径 | 用途 |
|-------|------|------|
| `/solar` | `skills/solar/SKILL.md` | 启动开发流程 |
| `/phase` | `skills/phase/SKILL.md` | 阶段转换 |
| `/commit` | `skills/commit/SKILL.md` | Git 提交 |
| `/pr` | `skills/pr/SKILL.md` | 创建 PR |
| `/benchmark` | `skills/benchmark/SKILL.md` | 性能测试 |
| `/review` | `skills/review/SKILL.md` | 代码审查 |
| `/test` | `skills/test/SKILL.md` | 运行测试 |
| `/build` | `skills/build/SKILL.md` | 构建项目 |
| `/save` | `skills/save/SKILL.md` | 保存状态 |
| `/restore` | `skills/restore/SKILL.md` | 恢复状态 |
| `/office` | `skills/office/SKILL.md` | 办公模式 |
| `/docs` | `skills/docs/SKILL.md` | 生成文档 |
| `/email-search` | `skills/email-search/SKILL.md` | 邮件搜索 (CLI) |
| `/email-web` | `skills/email-web/SKILL.md` | 邮件搜索 Web 界面 |
| `/selfie` | `skills/selfie/SKILL.md` | 摄像头拍照 |
| `/shortcut` | `skills/shortcut/SKILL.md` | 执行 Apple Shortcuts (AI OS 技能层) |
| `/shortcut-builder` | `skills/shortcut-builder/SKILL.md` | 苹果快捷指令编辑器 - 自动创建并执行 Shortcuts |
| `/shortcut-search` | `skills/shortcut-search/SKILL.md` | 搜索并下载快捷指令 - 从网上查找 Shortcuts |
| `/hn-monitor` | `skills/hn-monitor/SKILL.md` | 监控 Hacker News 热门话题 (定时更新) |
| `/learn` | `skills/learn/SKILL.md` | 学习新知识，写入记忆 |
| `/reflect` | `skills/reflect/SKILL.md` | 元认知反思，智慧检验 |
| `/memory-review` | `skills/memory-review/SKILL.md` | 记忆回顾与总结压缩 |
| `/forget` | `skills/forget/SKILL.md` | 主动遗忘，清理低价值记忆 |
| `/ppt` | `skills/ppt/SKILL.md` | MD→华为风格HTML演示文稿 |
| `/precise-edit` | `skills/precise-edit/SKILL.md` | 精准定位编辑 (Grep→Read→Edit 三步合一) |
| `/search` | `skills/search/SKILL.md` | Tantivy 全文搜索 - 对话/记忆/代码 |
| `/favorites` | `skills/favorites/SKILL.md` | 收藏管理 - 保存有价值的问答 |
| `/recall` | `skills/recall/SKILL.md` | 记忆快速检索 - 搜索所有记忆层 |
| `/sql` | `skills/sql/SKILL.md` | 数据库查询助手 - 自然语言转SQL |
| `/analyze` | `skills/analyze/SKILL.md` | 代码质量分析 - 复杂度/依赖/安全 |
| `/cron` | `skills/cron/SKILL.md` | 定时任务管理 - launchd/crontab |
| `/watch` | `skills/watch/SKILL.md` | 文件监控 - 变化时自动执行 |
| `/deps` | `skills/deps/SKILL.md` | 依赖管理 - 检查/更新/安全扫描 |
| `/http` | `skills/http/SKILL.md` | API 测试 - curl 智能封装 |
| `/diff` | `skills/diff/SKILL.md` | 智能差异 - 可读变更摘要 |
| `/template` | `skills/template/SKILL.md` | 代码模板 - 快速生成骨架 |
| `/env` | `skills/env/SKILL.md` | 环境管理 - 开发/测试/生产切换 |
| `/log` | `skills/log/SKILL.md` | 日志分析 - 错误模式/智能摘要 |
| `/perf` | `skills/perf/SKILL.md` | 性能分析 - profiling/火焰图 |
| `/graph` | `skills/graph/SKILL.md` | 知识图谱 - 关系可视化 |
| `/backup` | `skills/backup/SKILL.md` | 自动备份 - 定时/云端 |
| `/migrate` | `skills/migrate/SKILL.md` | 数据迁移 - 版本化 Schema |
| `/alert` | `skills/alert/SKILL.md` | 监控告警 - 健康检查/通知 |
| `/sandbox` | `skills/sandbox/SKILL.md` | 沙箱执行 - Docker 安全运行 |
| `/queue` | `skills/queue/SKILL.md` | 任务队列 - 串行执行避免冲突 |

## 加载规则

1. **启动时**: 只加载 CLAUDE.md (~200 tokens)
2. **模式触发**: 加载对应 modes/*.md (~500 tokens)
3. **Skill 调用**: 加载对应 skills/*/SKILL.md
4. **Agent 调用**: 加载对应 agents/*.md

## Token 预算

| 场景 | 估算 |
|------|------|
| 基础 | 200 |
| + 开发模式 | +500 |
| + 1个Skill | +200 |
| + 1个Agent | +150 |
| 典型开发会话 | ~1,500 |
