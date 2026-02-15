# REE 实现经验教训 (Lessons Learned)

> 来源: 2026-02-03 REE 架构统一重构
> 沉淀: 避免相同错误再次发生

## 核心教训

### 1. 代码写完 ≠ 完成

**问题:** 写了 schema.sql 但没执行，写了注册代码但没跑

**铁律:**
```
完成 = 代码 + 执行 + 验证
```

**检查清单:**
- [ ] SQL schema 执行了吗？
- [ ] 数据插入了吗？
- [ ] 验证查询通过了吗？

### 2. 不要并行架构

**问题:** REE 和 TieredRouter 两套独立系统，功能重复

**铁律:**
```
单一入口原则: 一个功能只有一个入口
```

**正确做法:**
- REE 是入口，TieredRouter 是内部实现
- REE.match() 内部调用 TieredRouter.route()
- 对外只暴露 REE

### 3. Schema 必须在代码前

**问题:** 写了使用 sys_shortcuts 的代码，但表定义不完整

**铁律:**
```
先 Schema，后代码
Schema 不存在的字段，代码不能用
```

**检查清单:**
- [ ] 表结构定义完整？
- [ ] 字段类型匹配？
- [ ] 外键约束正确？

### 4. 语义匹配需要领域关键词

**问题:** TF-IDF 嵌入对所有查询都匹配到 weather-fetch

**原因:** KEYWORD_WEIGHTS 缺少领域特定词汇

**解决:** 为每个脚本的核心关键词设置高权重

```typescript
// 错误: 通用权重
'查询': 2.0, '获取': 2.0

// 正确: 领域特定高权重
'HN': 6.0, 'PPT': 6.0, '待办': 5.0, 'backlog': 6.0
```

### 5. IaST 必须有 Seed Data

**问题:** 定义了 sys_shortcuts 表但里面是空的

**铁律:**
```
系统表 = Schema + Seed Data + Views
三者缺一不可
```

## 标准工作流程 (固化)

```
┌─────────────────────────────────────────────────────────────┐
│                   REE 开发标准流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Schema First                                            │
│     └── 写 SQL → 执行 → 验证表存在                          │
│                                                             │
│  2. Seed Data                                               │
│     └── INSERT → 验证数据存在                               │
│                                                             │
│  3. Code                                                    │
│     └── 写代码 → 单一入口                                   │
│                                                             │
│  4. Test                                                    │
│     └── bun test-*.ts → 全部通过                            │
│                                                             │
│  5. Document                                                │
│     └── 更新 ree-first.md                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## REE 架构总结

```
                    ┌─────────────────────┐
                    │        REE          │  ← 唯一入口
                    │    (index.ts)       │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   TieredRouter      │  ← 智能路由
                    │  L1/L2/L3 分层      │
                    └─────────┬───────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ ResourceMatcher│ │ EmbeddingService │ │ ContextMemory │
    │  (L1 关键词)  │   │  (L2 语义)    │   │  (上下文)   │
    └─────────────┘   └─────────────┘   └─────────────┘
           │                  │                  │
           └──────────────────┼──────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │    solar.db         │
                    │  sys_scripts        │
                    │  sys_shortcuts      │
                    │  sys_resources      │
                    └─────────────────────┘
```

## 每次开发前检查

```bash
# 1. Schema 是否最新
sqlite3 ~/.solar/solar.db ".tables" | grep -E "sys_scripts|sys_shortcuts"

# 2. 脚本是否已注册
sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_scripts WHERE status='active'"

# 3. 嵌入是否已索引
sqlite3 ~/.solar/solar.db "SELECT COUNT(*) FROM sys_script_embeddings"

# 4. Shortcuts 是否已安装
bun ~/.claude/core/ree/test-shortcuts.ts verify
```

---

*REE Lessons Learned v1.0*
*沉淀时间: 2026-02-03*
*知行合一 - 经验必须变成规则才有价值*
