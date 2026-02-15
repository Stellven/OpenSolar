# Solar 铁律: Agent→Skill 归一化 (Agent-Skill Unification)

> **来源: 2026-02-10 监护人指正"做假"问题**
> **问题: @Agent 输出宣告但实际没调用外部模型，只是角色扮演**

## 问题根因

```
┌─────────────────────────────────────────────────────────────────┐
│  旧系统冲突                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  @Agent (老)              │    glm_only 模式 (新)              │
│  ─────────────           │    ──────────────────              │
│  • agents/*.md 定义       │    • 用 brain-router 调牛马        │
│  • model: sonnet/opus     │    • 绕过 Task Agent               │
│  • 本质是 prompt 模板     │    • Claude 编排，牛马执行         │
│  • 给 Task 工具用         │                                    │
│                                                                 │
│  冲突结果:                                                      │
│  • 输出 Agent 宣告 (遵守老规则)                                 │
│  • 不调 Task (glm_only 说不用)                                  │
│  • 也不调 brain-router (没人告诉我)                             │
│  • → "做假" = 假装调用，实际自己算                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 解决方案: Agent→Skill 映射

```
┌─────────────────────────────────────────────────────────────────┐
│  新机制: Agent 作为 Skill 的触发器                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户说 @Researcher xxx                                         │
│         │                                                       │
│         ▼                                                       │
│  检查 sys_agents.delegation_mode                                │
│         │                                                       │
│    ┌────┴────┐                                                  │
│    ▼         ▼                                                  │
│  [skill]   [legacy]                                             │
│    │         │                                                  │
│    ▼         ▼                                                  │
│  执行映射   老逻辑                                               │
│  的 Skill   (角色扮演)                                          │
│    │                                                            │
│    ▼                                                            │
│  /insight → brain-router → 牛马干活 → 真正的研究                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 映射表 (sys_agents)

| Agent | mapped_skill | delegation_mode | 状态 |
|-------|--------------|-----------------|------|
| @Researcher | /insight | skill | ✅ 已归一 |
| @Coder | - | legacy | 待归一 |
| @Architect | - | legacy | 待归一 |
| @Tester | /test | legacy | 待归一 |
| @Reviewer | /review | legacy | 待归一 |

## 调用方式

### 自动桥接 (推荐)

```bash
# 当检测到 @Researcher 时，自动执行:
bun ~/.claude/core/agent-skill-bridge.ts researcher "用户查询"
```

### 手动调用

```bash
# 直接调用 /insight skill
bun ~/.claude/core/solar-farm/insight-agent-v2.ts "主题" 3
```

## 数据库字段

```sql
-- sys_agents 新增字段
mapped_skill TEXT,           -- 映射的 Skill 路径 (如 /insight)
skill_params JSON,           -- Skill 参数
delegation_mode TEXT         -- 'skill' 或 'legacy'
```

## 检查清单

收到 @Agent 触发时：

- [ ] 查询 sys_agents 获取 delegation_mode
- [ ] 如果是 'skill' → 执行 agent-skill-bridge.ts
- [ ] 如果是 'legacy' → 使用老的角色扮演逻辑
- [ ] **绝不"做假"** - 要么真调用，要么明说不支持

## 禁止行为

- ❌ 输出 Agent 宣告但不实际调用
- ❌ 假装调用外部模型
- ❌ 混用新旧两套系统

## 铁律总结

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🔗 Agent→Skill 归一化铁律                                     │
│                                                                 │
│   1. @Agent 检查 delegation_mode (MUST)                         │
│   2. mode='skill' → 执行映射的 Skill (MUST)                     │
│   3. mode='legacy' → 明说是角色扮演 (MUST)                      │
│   4. 禁止"做假" - 假装调用但自己算 (MUST)                       │
│                                                                 │
│   真调用 > 明说不支持 > 做假                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Agent-Skill Unification v1.0*
*建立于: 2026-02-10*
*来源: 监护人指正"做假"问题*
