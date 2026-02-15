# 报告工程化流水线 (Report Engineering Pipeline)

> 抗压缩长文报告生成模板，适用于 2-5 万字、数十篇论文的深度报告

## 设计理念

**核心问题**: 长报告生成最容易被上下文压缩"干碎"，丢失关键信息。

**解决方案**: 把"大脑"搬到文件系统，文件是唯一真相源。

```
┌─────────────────────────────────────────────────────────────────┐
│                    报告工程化流水线                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   STATE.md      ←── 态势板 (压缩后恢复起点)                     │
│       │                                                         │
│       ▼                                                         │
│   OUTLINE.md    ←── 大纲 = 编译目标                             │
│       │                                                         │
│       ▼                                                         │
│   SOURCES.md    ←── 文献总账 (所有引用)                         │
│       │                                                         │
│       ▼                                                         │
│   NOTES/*.md    ←── 单篇笔记 (结构化摘要)                       │
│       │                                                         │
│       ▼                                                         │
│   CLAIMS.md     ←── 主张-证据矩阵 (论证完整性)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 文件结构

```
REPORT/
├── README.md           # 本文件
├── STATE.md            # 报告态势板 (Topic/Thesis/Progress/Next)
├── OUTLINE.md          # 大纲 (每节的claim/sources/artifacts)
├── SOURCES.md          # 文献总账 (citation key/结论/可信度/thesis关系)
├── CLAIMS.md           # 主张-证据矩阵 (每个claim的支撑/反例)
└── NOTES/
    ├── _TEMPLATE.md    # 笔记模板
    ├── paper-001.md    # 单篇笔记
    └── paper-xxx.md    # ...
```

## 使用流程

### Phase 1: 初始化

```bash
# 复制模板到项目目录
cp -r ~/.claude/templates/REPORT ./REPORT-{topic}

# 填写 STATE.md
# - Topic / Audience / Scope
# - Thesis (核心论点)
```

### Phase 2: 文献收集

```bash
# 为每篇论文创建笔记
cp REPORT/NOTES/_TEMPLATE.md REPORT/NOTES/paper-001.md

# 填写笔记: Problem/Method/Results/Key Numbers/Weakness

# 更新 SOURCES.md: 添加文献条目
```

### Phase 3: 大纲定稿

```bash
# 编辑 OUTLINE.md
# 为每个小节定义:
#   - Claim (主张)
#   - Sources (引用文献)
#   - Artifacts (产出物)
#   - 依赖
```

### Phase 4: 证据映射

```bash
# 填写 CLAIMS.md
# 为每个 Claim 列出:
#   - 支持文献
#   - 反例文献
#   - 综合评估
```

### Phase 5: 写作执行

```bash
# 按 OUTLINE.md 顺序写作
# 每完成一节:
#   1. 更新 STATE.md Progress
#   2. git commit
```

## 检查点机制

**触发时机**:
- 完成一篇论文笔记
- 完成一个章节
- 感觉上下文快满时
- 主动说 "checkpoint" / "保存"

**检查点内容**:
1. 更新 STATE.md (Progress/Next Actions)
2. 确保所有 NOTES/*.md 已保存
3. `git commit -m "WIP: checkpoint"`

## 与 /insight 集成

小爱的 /insight skill 应该:

1. **初始化**: 创建 REPORT 目录，填写 STATE.md
2. **文献阶段**: 为每篇论文创建 NOTES/paper-xxx.md
3. **分析阶段**: 更新 CLAIMS.md
4. **写作阶段**: 按 OUTLINE.md 生成内容
5. **每阶段结束**: 更新 STATE.md，checkpoint

## 抗压缩原则

1. **STATE.md 是恢复起点** - 压缩后第一件事读 STATE.md
2. **NOTES 是知识沉淀** - 论文内容在 NOTES 里，不在对话里
3. **CLAIMS 是论证骨架** - 证据关系在文件里，不靠记忆
4. **频繁 checkpoint** - 每完成一步就保存

## 命令快捷方式

```bash
# 初始化新报告
/insight init <topic>

# 添加论文笔记
/insight add-paper <pdf-path>

# 更新进度
/insight checkpoint

# 生成章节
/insight write <chapter>

# 查看状态
/insight status
```

---

*Report Engineering Pipeline v1.0*
*建立于: 2026-02-12*
*来源: 抗失忆工作流*
