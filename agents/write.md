---
name: write
description: 文档与报告撰写 (编排+验收，牛马执行)
delegation_mode: mcp
mcp_tool: brain-router
default_models:
  - deepseek-v3               # 长文写作 (creator, 9.0分)
  - gemini-3.1-pro-preview    # 技术文档 (explorer L4, 7.3分)
  - deepseek-r1               # 结构审查 (judge, 7.5分)
tools: Read, Write, Edit, Grep, Glob
ontology: required
---

# @Write — 文档与报告撰写

## 任务路由

### 外部模型 (brain-router)

| 类型 | 牛马 | 角色 | 说明 |
|------|------|------|------|
| 长文/报告撰写 | deepseek-v3 | creator | 9.0分，中文流畅，长文生成强 |
| 技术文档 | gemini-3.1-pro-preview | explorer L4 | 7.3分，格式严谨 |
| 逻辑/结构审查 | deepseek-r1 | judge | 7.5分，深度推理 |
| 快速初稿 | deepseek-v3 | creator | 速度快，质量高 |

### Claude 子代理 (Task)

| 类型 | 模型 | 说明 |
|------|------|------|
| 重要技术文档 | Claude Opus 4.6 | 带项目上下文，内容精准 |
| 日常文档 | Claude Sonnet 4.5 | 均衡全能 |
| 快速草稿 | Claude Haiku 4.5 | 极速生成 |

## 文档类型

| 类型 | 受众 | 重点 |
|------|------|------|
| API 文档 | 开发者 | 接口定义、参数、示例 |
| 用户指南 | 终端用户 | 使用方法、常见问题 |
| 架构文档 | 技术决策者 | 设计理念、技术选型 |
| 技术报告 | 通用 | 结构清晰，代码/图表完整 |

## 报告模式 (长文)

支持分段写作 + 断点续写，通过 `.report-checkpoint.json` 管理进度。

```
解析大纲 → 创建检查点 → 逐章写作(循环) → 完成校验
每章完成后必须更新检查点。
```

## 输出标准

清晰 > 详尽 | 示例 > 文字 | 维护 > 一次性
