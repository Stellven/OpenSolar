# /skill - 技能系统管理

> 在对话中用自然语言管理技能，无需命令行

## 功能

当用户提到技能相关操作时，自动调用 Skill Distiller 系统。

## 支持的操作

### 创建技能
```
创建技能：调试 TypeError
描述：系统化调试 TypeError 错误
```

### 查看技能
```
查看技能 skill_xxx
显示技能详情
```

### 搜索技能
```
搜索 调试
找一下性能相关的技能
```

### 发布/订阅
```
发布技能 skill_xxx
订阅技能 skill_xxx
```

### 反馈
```
skill_xxx 执行成功了
skill_xxx 失败了，原因是超时
```

### 市场统计
```
技能市场统计
推荐一些技能
```

### 进化
```
执行技能进化
进化报告
```

## 实现方式

解析用户意图后，调用对应的 CLI 命令：

```typescript
import { execSync } from 'child_process';

const CLI = '~/.claude/core/skill-distiller/cli.ts';

// 示例：搜索技能
function searchSkills(query: string) {
  return execSync(`bun ${CLI} search "${query}"`).toString();
}

// 示例：记录反馈
function recordFeedback(skillId: string, success: boolean, comment?: string) {
  const outcome = success ? 'success' : 'failure';
  const cmd = comment
    ? `bun ${CLI} feedback ${skillId} --outcome ${outcome} --comment "${comment}"`
    : `bun ${CLI} feedback ${skillId} --outcome ${outcome}`;
  return execSync(cmd).toString();
}
```

## 自动触发

当检测到以下模式时自动执行：

| 用户说 | 自动操作 |
|--------|----------|
| "创建技能：XXX" | `bun cli.ts create --name "XXX"` |
| "查看技能 XXX" | `bun cli.ts show XXX` |
| "搜索 XXX 技能" | `bun cli.ts search XXX` |
| "XXX 执行成功/失败" | `bun cli.ts feedback XXX --outcome success/failure` |
| "技能统计" | `bun cli.ts stats` |
| "进化报告" | `bun cli.ts report` |

## CLI 命令速查

```bash
# 基础
bun cli.ts create --name "名称" --description "描述" --tags "tag1,tag2"
bun cli.ts list --status pending_review
bun cli.ts approve <skill_id>
bun cli.ts search "关键词"
bun cli.ts show <skill_id>
bun cli.ts stats

# P1 进化
bun cli.ts evolve              # 执行进化
bun cli.ts report              # 查看报告
bun cli.ts feedback <id> --outcome success/failure --comment "评论"

# P2 市场
bun cli.ts publish <id> --author builder
bun cli.ts subscribe <id> --agent architect
bun cli.ts market
bun cli.ts recommend --agent builder
```
