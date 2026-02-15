# Skin Check Phase 2 - 本地模型实现

## 快速开始

### Phase 2.1: 本地分类器 ✅

```bash
# 1. 测试本地分类器 (使用已有图片)
bun skin-check-v2.ts --test=~/Desktop/selfie_xxx.jpg

# 2. 完整流程 (拍照 + 本地分析)
bun skin-check-v2.ts

# 3. 混合模式 (本地 + 远程专家)
bun skin-check-v2.ts --remote

# 4. 下载预训练模型 (可选，提升准确度)
./scripts/download-model.sh
```

## 当前状态

### ✅ 已实现
- [x] 本地分类器框架 (`local-classifier.ts`)
- [x] CoreML 推理脚本 (`coreml-inference.swift`)
- [x] 降级方案 (简化规则)
- [x] V2 主流程 (`skin-check-v2.ts`)
- [x] 模型下载脚本

### ⏳ 待实现
- [x] Phase 2.2: YOLOv8 病灶检测 ✅ (框架完成，需模型)
- [x] Phase 2.3: 历史记录与对比 ✅ (SQLite + 趋势分析)
- [ ] Phase 2.4: 专用模型训练 ⏸️ (挂起，等待部署到 Mac mini Pro 48G)
  - 数据集：DermNet (23K) / ISIC (50K)
  - 框架：CreateML (Apple 原生)
  - 预估时间：1-2.5 小时
  - 目标准确度：85-90%
  - **Backlog**: 已记录到 `bl_tasks` 表

## Phase 2.3: 历史记录

```bash
# 查看历史记录
bun phase2/history-tracker.ts list 10

# 趋势分析
bun phase2/history-tracker.ts trend 30d

# 对比两次检测
bun phase2/history-tracker.ts compare 1 2
```

## 性能对比

| 指标 | Phase 1 (纯API) | Phase 2.1 (本地) |
|------|----------------|-----------------|
| 延迟 | 3-5s | ~30ms (100x faster) |
| 成本 | $0.002/次 | $0 |
| 离线 | ❌ | ✅ |
| 准确度 | 80-90% (专家) | 60-70% (简化规则) |

## 训练路线图

### 选项 A: 预训练模型 (当前) ⭐
- 时间: 1-2 小时
- 准确度: 60-70%
- 成本: $0
- 适合: 快速验证

### 选项 B: 公开数据集训练
- 时间: 2-3 小时 (下载 + 训练)
- 准确度: 80-90%
- 数据集: DermNet (23,000 图), ISIC (50,000 图)
- 适合: 达到专家级准确度

### 选项 C: 自定义数据集
- 时间: 4-6 小时 (标注) + 2 小时 (训练)
- 准确度: 90%+
- 适合: 特定场景优化

## 下一步

1. **测试当前版本**: `bun skin-check-v2.ts`
2. **决定训练路线**: A/B/C
3. **Phase 2.2**: YOLOv8 病灶检测
4. **Phase 2.3**: 历史记录系统

## 技术栈

- **运行时**: Bun (TypeScript)
- **本地模型**: CoreML (MobileNetV3-Large)
- **推理**: Vision framework (Swift)
- **降级**: 简化规则
- **未来**: YOLOv8 (CoreML), SQLite (历史)
