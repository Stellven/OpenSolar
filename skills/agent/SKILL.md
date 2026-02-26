---
name: agent
description: 列出并激活 Solar Agent，支持 @Agent 语法
user-invocable: true
disable-model-invocation: false
argument-hint: "[@Agent名称]"
---

# /agent - Agent 选择器

## 功能

列出可用的 Solar Agent，或激活指定 Agent。

## 使用方式

```
/agent           # 列出所有可用 Agent
/agent Researcher  # 激活 Researcher
@Researcher      # 快捷方式 (等同于 /agent Researcher)
```

## 可用 Agent 列表

当用户输入 `/agent` 或 `@` 时，显示：

```
═══════════════════════════════════════════════════
🌟 Solar Agent 列表
═══════════════════════════════════════════════════

📊 决策层 (Opus)
  @Researcher  - 技术调研、可行性分析
  @Architect   - 架构设计、技术评审
  @PM          - 产品验收、竞争力评估

⚡ 执行层 (Sonnet)
  @Coder       - 代码实现、重构
  @Tester      - 测试编写、执行
  @Reviewer    - 代码审查、安全检查
  @Secretary   - 记录整理、Agent评估

🔧 支撑层
  @Docs        - 文档生成 (Sonnet)
  @Ops         - 构建部署 (Sonnet)
  @Guard       - 规范检查 (Haiku)

═══════════════════════════════════════════════════
用法: @Agent名称 + 你的请求
示例: @Researcher 调研 SIMD 向量化优化技术
═══════════════════════════════════════════════════
```

## Agent 激活逻辑

当用户指定 Agent 时：

1. **验证 Agent 名称** - 检查是否在列表中
2. **加载 Agent 定义** - 读取 `agents/{name}.md`
3. **检测执行模式** - 根据 `delegation_mode` 决定执行方式：
   - `delegation_mode: mcp` → 自动执行 (调用 agent-executor.ts)
   - `delegation_mode: legacy` → 角色扮演模式
4. **执行并输出** - 标注 Agent 并展示结果

## 输出标记

激活 Agent 后，响应格式：

```
[@Researcher]
─────────────
{Agent 的响应内容}
```

## @ 语法识别规则

以下模式应被识别为 Agent 调用：

- `@Solar` - 使用完整 Solar 流程
- `@Researcher` - 单独调用 Researcher
- `@Architect` - 单独调用 Architect
- `@Coder` - 单独调用 Coder
- ... (所有 Agent)

## 自动执行机制 (MCP Delegation)

当 Agent 配置为 `delegation_mode: mcp` 时，自动执行多专家会审：

```bash
# 自动调用 agent-executor.ts
bun ~/.claude/core/agents/agent-executor.ts <AgentName> "<用户任务>"

# 示例: @Reporter 按大纲写第六章
# → bun agent-executor.ts Reporter "按大纲写第六章"
# → 自动并行调用 deepseek-v3 (creator) + gemini-2.5-pro (verifier)
# → 注入完整 D&D KNOBS 人格参数
# → 综合专家输出并验收
```

**执行流程：**
1. 解析 Agent YAML 定义 (delegation_mode, mcp_tool, default_models)
2. 为每个 model 注入 D&D KNOBS 人格 (通过 buildNiumaCall)
3. 并行调用多个专家 (通过 brain-router MCP)
4. 综合输出并验收 (基于 OUTPUT_SCHEMA)
5. 展示会审结果

**支持的 MCP Agents：**
- @Reporter (deepseek-v3 + gemini-2.5-pro)
- @PM (gemini-2.5-pro + deepseek-r1 + glm-5)
- @Ops (glm-5 + gemini-2.5-pro)
- @Guard (gemini-2.5-pro + deepseek-r1)

## 注意事项

- MCP Agents 会自动执行多专家会审，无需手动调用
- Legacy Agents 保持角色扮演模式
- 如需完整 Solar 流程，使用 `@Solar`
- Agent 名称不区分大小写
