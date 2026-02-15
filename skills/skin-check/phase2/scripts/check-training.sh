#!/bin/bash
# 检查训练进度

MODEL_DIR=~/Solar/Skin-check/models/skin7_v2

echo "=== 训练状态检查 ==="
echo ""

# 检查进程
PROCESS=$(ps aux | grep "train_7class_v2" | grep -v grep)
if [ -n "$PROCESS" ]; then
    echo "✅ 训练进行中"
    echo "$PROCESS"
else
    echo "⏹️ 训练已结束或未启动"
fi

echo ""
echo "=== 文件状态 ==="

# 检查模型文件
if [ -f "$MODEL_DIR/best_model.pth" ]; then
    SIZE=$(ls -lh "$MODEL_DIR/best_model.pth" | awk '{print $5}')
    echo "✅ best_model.pth: $SIZE"
else
    echo "❌ best_model.pth: 未生成"
fi

# 检查 CoreML
if [ -d "$MODEL_DIR/Skin7V2Classifier.mlpackage" ]; then
    echo "✅ Skin7V2Classifier.mlpackage: 已导出"
else
    echo "⏳ Skin7V2Classifier.mlpackage: 待导出"
fi

# 检查模型信息
if [ -f "$MODEL_DIR/model_info.json" ]; then
    echo ""
    echo "=== 模型信息 ==="
    cat "$MODEL_DIR/model_info.json" | python3 -m json.tool 2>/dev/null || cat "$MODEL_DIR/model_info.json"
fi

# 检查训练历史
if [ -f "$MODEL_DIR/training_history.json" ]; then
    echo ""
    echo "=== 训练进度 ==="
    python3 -c "
import json
with open('$MODEL_DIR/training_history.json') as f:
    h = json.load(f)
    if h['val_acc']:
        best_acc = max(h['val_acc'])
        best_epoch = h['val_acc'].index(best_acc) + 1
        print(f'已完成 {len(h[\"val_acc\"])} 轮')
        print(f'最佳准确率: {best_acc:.2f}% (Epoch {best_epoch})')
        print(f'最新准确率: {h[\"val_acc\"][-1]:.2f}%')
"
fi
