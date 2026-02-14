# Solar 架构文档 (ARCH.md)

> 模块边界 | 数据流 | 约定 | 日志规范
> 每次多文件开发前必读

## 模块边界

```
Solar/
├── core/           # 核心逻辑 (无外部依赖)
│   ├── ree/        # 资源执行引擎
│   ├── cortex/     # 数据中枢
│   └── memory/     # 记忆系统
├── skills/         # 技能 (命令式, 单一职责)
├── agents/         # Agent 定义
├── hooks/          # Claude Code hooks
├── web/            # Web 界面
└── .solar/         # 项目状态 (STATE/DECISIONS/LOG)
```

## 数据流

```
用户输入
    │
    ▼
┌─────────────┐
│ Intent Engine│ → 解析意图
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    REE      │ → 匹配资源
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Executor   │ → 执行任务
└──────┬──────┘
       │
       ▼
    输出/持久化
```

## 接口约定

### 函数签名
```typescript
// 输入: 显式参数，不依赖全局状态
// 输出: 明确返回值或 throw Error
// 副作用: 仅在函数名体现 (save*, write*, update*)
```

### 错误处理
```typescript
// ✓ 抛出明确错误
throw new Error(`[模块名] 具体错误: ${details}`);

// ✗ 不要静默失败
return null; // 禁止
```

### 性能预算
| 操作 | 预算 |
|------|------|
| 本地文件读取 | <50ms |
| 数据库查询 | <100ms |
| API 调用 | <2s |
| 牛马调用 | <10s |

## 日志规范

```typescript
// 格式: [时间] [级别] [模块] 消息
console.log(`[${new Date().toISOString()}] [INFO] [REE] 匹配到资源: ${id}`);

// 级别
// ERROR: 需要干预的错误
// WARN:  可能的问题
// INFO:  关键业务事件
// DEBUG: 调试信息 (生产环境关闭)
```

## 文件命名

| 类型 | 命名 | 示例 |
|------|------|------|
| 入口文件 | index.ts | core/ree/index.ts |
| 类型定义 | types.ts | core/ree/types.ts |
| 工具函数 | utils.ts | core/ree/utils.ts |
| 测试文件 | *.test.ts | core/ree/index.test.ts |

## 禁止事项

- ❌ 硬编码路径 (用环境变量或配置)
- ❌ 全局状态 (用依赖注入)
- ❌ 隐式依赖 (import 必须显式)
- ❌ 魔数 (用命名常量)

## 检查点

多文件修改时，每落地一个模块必须:
1. 单元测试通过
2. 接口契约满足
3. 更新 STATE.md
4. git commit (WIP 可接受)
