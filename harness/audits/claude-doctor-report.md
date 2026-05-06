# Claude /Doctor 审计报告

**日期**: 2026-04-22
**Sprint**: sprint-20260422-164413

## Hook 脚本审计 (24 OK → 修复后 24 OK, 0 MISSING)

### PostToolUse (2 hooks)
| 状态 | 脚本 |
|------|------|
| OK | ~/.claude/hooks/state-read-tracker.sh |
| OK | ~/.claude/hooks/post-tool-dispatcher.sh |

### PreToolUse (2 hooks)
| 状态 | 脚本 |
|------|------|
| OK | ~/.claude/hooks/state-read-enforcer.sh |
| OK | ~/.claude/hooks/experience-reminder.sh |

### SessionEnd (6 hooks, 原 7)
| 状态 | 脚本 |
|------|------|
| OK | /Users/lisihao/Solar/hooks/session-end-save.sh |
| OK | ~/.claude/hooks/session-reflect.sh |
| OK | ~/.claude/hooks/ses-session-end.sh |
| OK | ~/.claude/hooks/enhanced-memory-writer.sh |
| OK | ~/.claude/hooks/session-refresh-assets.sh |
| ~~MISSING~~ → **已删除** | ~/.claude/hooks/state-session-end.sh |
| OK | ~/.claude/hooks/state-auto-updater.sh |

### SessionStart (4 hooks)
| 状态 | 脚本 |
|------|------|
| OK | ~/.claude/hooks/solar-session-start.sh |
| OK | ~/.claude/hooks/context-preload.sh |
| OK | ~/.claude/hooks/perf-auto-refresh.sh |
| OK | ~/.claude/hooks/state-inject.sh |

### UserPromptSubmit (9 hooks, 原 10)
| 状态 | 脚本 |
|------|------|
| OK | ~/.claude/hooks/personality-anchor-hook.sh |
| OK | ~/.claude/hooks/asset-reminder.sh |
| OK | ~/.claude/hooks/cortex-hook.sh |
| ~~MISSING~~ → **已删除** | ~/.claude/hooks/intent-learning-hook.sh |
| OK | ~/.claude/hooks/learning-capture.sh |
| OK | ~/.claude/hooks/memory-influence.sh |
| OK | ~/.claude/hooks/ree-first-hook.sh |
| OK | ~/.claude/hooks/mid-refresh.sh |
| OK | ~/.claude/hooks/identity-reminder.sh |
| OK | ~/.claude/hooks/executor-reminder.sh |

## 修复记录

### Fix 1: state-session-end.sh (SessionEnd)
- **Before**: settings.json 引用 `~/.claude/hooks/state-session-end.sh` — 文件不存在
- **After**: 从 SessionEnd 数组中删除该条目
- **Impact**: 无功能影响，该 hook 从未执行过

### Fix 2: intent-learning-hook.sh (UserPromptSubmit)
- **Before**: settings.json 引用 `~/.claude/hooks/intent-learning-hook.sh` — 文件不存在
- **After**: 从 UserPromptSubmit 数组中删除该条目
- **Impact**: 无功能影响，该 hook 从未执行过

## Permission 规则统计

- **settings.local.json**: 221 条 allow 规则
- 部分规则含编码后的中文/特殊字符（Claude Code 权限系统自动生成）
- 建议: 定期清理过期规则（低优先级，不影响功能）

## 需用户批准

以下项目未自动修改，需昊哥决策：

1. **SessionEnd 7→6 个 hook**: 性能角度是否需要精简？每次会话结束 6 个 hook 串行执行可能影响退出速度
2. **UserPromptSubmit 10→9 个 hook**: 每次 prompt 触发 9 个 hook，是否需要合并/精简？
3. **MCP server 配置**: 未在本次审计范围内，如 /doctor 仍报 issue 可能来自 MCP 配置
4. **settings.local.json 221 条权限规则**: 部分含过期/项目特定的规则，是否需要清理？
