# Solar 持久记忆

## 强制规则 (监护人明确要求)

### TVS 智能模式 (2026-02-27)
- **规则**: 智能切换，场景决定渲染方式
- **ASCII**: 横幅、流程图、复杂艺术图形
- **TVS VDL**: 数据展示、状态报告、表格、卡片、进度条
- **知识固化**: 每次渲染输出必须存入知识库 (sys_favorites / cortex_sources)
- **位置**: ~/.claude/core/tvs/TVS_DESIGN.md

### 输出即固化 (2026-02-27)
- **铁律**: 每次分析/总结/设计/评审完成后，必须存入知识库
- **触发**: 分析报告、设计方案、评审结论、技术调研、规则定义、经验教训
- **存储**: sys_favorites (重要性≥7) 或 cortex_sources
- **规则文件**: ~/.claude/rules/output-persist.md
- **原因**: 对话是缓存，输出不能只留在对话里

## 常用命令

### TVS 渲染
```typescript
// VDL 组件
card("TITLE", [sections])
kv([{key, value}])
table(headers, rows)
sparkline(data, label)
progress(value, max)
```

### 风格切换
```bash
/theme              # 当前风格
/theme list         # 所有风格
/theme <name>       # 切换风格
```
