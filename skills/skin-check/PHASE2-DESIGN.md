# Skin-Check Phase 2 设计方案

> **本地模型 + 专业病灶检测 + 历史对比**
>
> 设计时间：2026-02-14
> 状态：设计阶段

## 一、目标

将 skin-check 从"云端 AI 分析"升级为"本地专业诊断系统"：

1. **本地化**：离线运行，无需 API，隐私更好
2. **专业化**：病灶精准定位（痘痘、斑点、皱纹坐标）
3. **持续化**：记录历史，跟踪变化趋势

## 二、技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 2 架构                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  拍照                                                        │
│   │                                                         │
│   ▼                                                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 本地视觉分析 (CoreML)                                 │  │
│  │ • MobileNetV3 / EfficientNet-Lite                    │  │
│  │ • 皮肤类型分类 (5类)                                  │  │
│  │ • 整体质量评分                                        │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 病灶检测 (YOLOv8-CoreML)                              │  │
│  │ • 痘痘检测 (acne)                                     │  │
│  │ • 色斑检测 (spots)                                    │  │
│  │ • 细纹检测 (wrinkles)                                 │  │
│  │ • 输出：[(x,y,w,h,conf,class), ...]                  │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 历史数据库 (SQLite)                                   │  │
│  │ • skin_check_history                                  │  │
│  │ • skin_check_detections                               │  │
│  │ • 对比分析                                            │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       │                                     │
│                       ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 报告生成                                              │  │
│  │ • 当前状态                                            │  │
│  │ • 历史趋势图                                          │  │
│  │ • 改善/恶化提示                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 三、技术选型

### 3.1 本地皮肤分类模型

**方案对比：**

| 模型 | 参数量 | 推理速度 | 准确率 | 推荐 |
|------|--------|---------|--------|------|
| MobileNetV3-Small | 2.5M | ~20ms | 中 | ✅ |
| MobileNetV3-Large | 5.4M | ~30ms | 高 | ✅ |
| EfficientNet-Lite0 | 4.7M | ~25ms | 高 | ✅ |
| EfficientNet-Lite1 | 5.4M | ~35ms | 很高 | 备选 |
| ResNet18 | 11.7M | ~50ms | 高 | ❌ 太慢 |

**推荐：MobileNetV3-Large**
- 速度够快（30ms）
- 准确率足够
- Apple CoreML 原生支持

**分类任务：**
```
输入：照片 (224x224 RGB)
输出：5类皮肤类型
  - 油性 (oily)
  - 干性 (dry)
  - 混合性 (combination)
  - 中性 (normal)
  - 敏感性 (sensitive)
```

**训练数据：**
- 公开数据集：DermNet, ISIC Archive
- 或使用预训练模型微调
- 约 5000-10000 张标注图像

### 3.2 病灶检测模型 (YOLOv8)

**方案：YOLOv8n-CoreML**

| 配置 | 值 |
|------|-----|
| 模型 | YOLOv8n (nano) |
| 输入 | 640x640 |
| 输出 | Bounding boxes + 类别 |
| 推理速度 | ~50ms (M1 芯片) |
| 检测类别 | 3类：acne, spots, wrinkles |

**检测框格式：**
```json
{
  "detections": [
    {
      "bbox": [x, y, w, h],
      "confidence": 0.85,
      "class": "acne",
      "severity": "moderate"
    }
  ]
}
```

**训练流程：**
1. 数据标注（LabelImg / Roboflow）
2. 训练 YOLOv8 (PyTorch)
3. 导出为 CoreML (`yolo export format=coreml`)
4. 集成到 Swift/ObjC

### 3.3 历史数据库设计

**表结构：**

```sql
-- 检测历史主表
CREATE TABLE skin_check_history (
    check_id TEXT PRIMARY KEY,
    photo_path TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    skin_type TEXT,           -- 分类结果
    skin_quality_score REAL,  -- 0-100
    total_detections INTEGER,
    notes TEXT
);

-- 检测详情表 (每个病灶)
CREATE TABLE skin_check_detections (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id TEXT REFERENCES skin_check_history(check_id),
    class TEXT,               -- acne/spots/wrinkles
    bbox_x REAL,
    bbox_y REAL,
    bbox_w REAL,
    bbox_h REAL,
    confidence REAL,
    severity TEXT             -- mild/moderate/severe
);

-- 对比分析视图
CREATE VIEW v_skin_trends AS
SELECT
    DATE(timestamp) as date,
    skin_type,
    AVG(skin_quality_score) as avg_quality,
    SUM(total_detections) as total_issues
FROM skin_check_history
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

## 四、实施步骤

### Phase 2.1: 本地模型集成 (预计 2-3 小时)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 模型选择与准备                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 1.1 下载预训练模型                                          │
│     - MobileNetV3 CoreML (Apple 官方)                       │
│     或                                                      │
│     - 使用 coremltools 转换 PyTorch 模型                    │
│                                                             │
│ 1.2 测试推理                                                │
│     - Swift Playground 验证                                 │
│     - 确认输入/输出格式                                     │
│                                                             │
│ 1.3 集成到 skin-check                                       │
│     - 创建 local-vision.ts (Bun + Swift bridge)            │
│     - 或纯 Swift CLI 工具                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**技术栈：**
- Swift (CoreML 原生支持)
- Bun TypeScript (调用 Swift CLI)
- Vision framework (图像预处理)

**文件结构：**
```
~/.claude/skills/skin-check/
├── local-vision/
│   ├── SkinClassifier.swift      # CoreML 推理
│   ├── build.sh                  # 编译脚本
│   └── skin-classifier           # 编译后二进制
└── models/
    └── MobileNetV3_SkinType.mlmodel
```

### Phase 2.2: YOLOv8 病灶检测 (预计 4-6 小时)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 2: YOLOv8 训练与部署                                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 2.1 数据准备 (2小时)                                        │
│     - 收集 200-500 张皮肤照片                               │
│     - 使用 Roboflow 标注                                    │
│     - 导出 YOLO 格式                                        │
│                                                             │
│ 2.2 训练 (1-2小时)                                          │
│     - yolo train model=yolov8n.pt data=skin.yaml           │
│     - epochs=100, batch=16                                 │
│                                                             │
│ 2.3 导出 CoreML (0.5小时)                                   │
│     - yolo export model=best.pt format=coreml              │
│                                                             │
│ 2.4 集成 (1小时)                                            │
│     - Swift 推理代码                                        │
│     - Bun 调用接口                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键代码示例：**

```swift
// SkinDetector.swift
import Vision
import CoreML

func detectLesions(image: CGImage) -> [Detection] {
    let model = try! yolov8n_skin(configuration: MLModelConfiguration())
    let request = VNCoreMLRequest(model: VNcoreMLModel(for: model.model))

    let handler = VNImageRequestHandler(cgImage: image)
    try! handler.perform([request])

    return parseDetections(request.results)
}
```

### Phase 2.3: 历史对比功能 (预计 2-3 小时)

```
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 历史数据管理                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 3.1 数据库初始化 (0.5小时)                                  │
│     - 创建表结构                                            │
│     - 迁移脚本                                              │
│                                                             │
│ 3.2 数据记录 (1小时)                                        │
│     - 每次检测后自动保存                                    │
│     - 照片归档 (~/.solar/skin-check/)                       │
│                                                             │
│ 3.3 趋势分析 (1小时)                                        │
│     - 计算改善/恶化百分比                                   │
│     - 生成 Sparkline 图表                                   │
│                                                             │
│ 3.4 对比报告 (0.5小时)                                      │
│     - TVS 渲染历史对比                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**对比算法：**

```typescript
function calculateTrend(history: CheckRecord[]): Trend {
  const recent = history.slice(0, 7);  // 最近7次
  const older = history.slice(7, 14);  // 之前7次

  const recentAvg = avg(recent.map(r => r.total_detections));
  const olderAvg = avg(older.map(r => r.total_detections));

  const change = (recentAvg - olderAvg) / olderAvg * 100;

  return {
    direction: change < -10 ? "improving" : change > 10 ? "worsening" : "stable",
    percentage: Math.abs(change),
    sparkline: recent.map(r => r.total_detections)
  };
}
```

## 五、性能指标

| 指标 | Phase 1 (云端) | Phase 2 (本地) |
|------|---------------|---------------|
| 推理延迟 | ~3-5s (API) | ~100ms (本地) |
| 隐私 | 上传到云端 | 完全本地 |
| 成本 | $0.002/次 | $0 |
| 离线可用 | ❌ | ✅ |
| 精准定位 | ❌ | ✅ (像素级) |
| 历史追踪 | ❌ | ✅ |

## 六、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 模型准确率不足 | 高 | 使用预训练模型 + 微调 |
| 标注数据不足 | 中 | 使用公开数据集 + 数据增强 |
| CoreML 转换失败 | 中 | 测试多个转换工具 (coremltools, onnx) |
| 推理速度慢 | 低 | 选择轻量模型 (MobileNet, YOLOv8n) |
| Swift 集成复杂 | 低 | 提供预编译二进制 |

## 七、输出示例

**Phase 2 报告格式：**

```
┌─ 📸 皮肤检测报告 (Phase 2) ────────────────────────────────┐
│                                                           │
│ 📊 基本信息                                                │
│ • 拍摄时间: 2026/2/14 12:30                               │
│ • 分析模式: 本地 CoreML + YOLOv8                          │
│                                                           │
├─ 🔍 本地视觉分析 ─────────────────────────────────────────┤
│                                                           │
│ 皮肤类型: 混合性 (置信度: 89%)                            │
│ 整体质量: 72/100                                          │
│                                                           │
├─ 🎯 病灶检测 (YOLOv8) ────────────────────────────────────┤
│                                                           │
│ 检测到 5 个问题区域:                                       │
│ • [痘痘] 2 个 (额头×1, 下巴×1)                            │
│ • [色斑] 2 个 (脸颊×2)                                    │
│ • [毛孔] 1 个 (鼻翼)                                      │
│                                                           │
│ 严重程度分布:                                             │
│ • 轻微: ███░░ 60%                                         │
│ • 中等: ██░░░ 40%                                         │
│ • 严重: ░░░░░  0%                                         │
│                                                           │
├─ 📈 历史趋势 (最近7次) ───────────────────────────────────┤
│                                                           │
│ 总问题数: ▃▄▅▃▂▂▁ (改善中 ✓)                              │
│ 质量评分: ▂▃▄▅▆▆▇ (上升趋势 ✓)                            │
│                                                           │
│ 对比上次 (7天前):                                         │
│ • 痘痘: 4 → 2 (减少 50% ✓)                                │
│ • 色斑: 3 → 2 (减少 33% ✓)                                │
│ • 质量: 65 → 72 (提升 11% ✓)                              │
│                                                           │
├─ 💡 建议 ─────────────────────────────────────────────────┤
│                                                           │
│ ✅ 当前护理有效，继续保持！                                │
│ • 注意防晒（色斑风险区）                                   │
│ • 加强 T 区清洁                                           │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## 八、下一步行动

**监护人决策点：**

1. **是否批准 Phase 2 开发？**
   - [ ] 批准，全面实施
   - [ ] 批准，但分步实施（先做哪一步？）
   - [ ] 暂缓，需要调整方案

2. **资源投入：**
   - 开发时间：8-12 小时
   - 数据准备：需要标注工具和数据集
   - 硬件：Mac (M1/M2 更佳)

3. **优先级排序：**
   - 选项 A：先做本地模型（隐私优先）
   - 选项 B：先做 YOLOv8（专业性优先）
   - 选项 C：先做历史对比（持续追踪优先）

---

**设计完成，等待审批。**
