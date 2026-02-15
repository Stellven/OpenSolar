#!/bin/bash
# 下载预训练 CoreML 模型
# 支持三种来源: Apple、Hugging Face、自己转换

set -e

MODEL_DIR="$(dirname "$0")/../models"
mkdir -p "$MODEL_DIR"

echo "📥 下载 CoreML 皮肤分类模型..."

# 选项1: 使用 MobileNetV3 通用分类器 (最快)
# Apple 官方模型不包含皮肤分类，需要自己 fine-tune
# 这里先下载基础模型，后续可以替换

MODEL_URL="https://ml-assets.apple.com/coreml/models/Image/ImageClassification/MobileNetV3/MobileNetV3Large.mlmodel"
MODEL_NAME="MobileNetV3Large.mlmodel"

echo "下载来源: Apple CoreML Model Gallery"
echo "模型: MobileNetV3-Large (通用分类器)"
echo "大小: ~5MB"
echo ""

if [ -f "$MODEL_DIR/$MODEL_NAME" ]; then
    echo "✅ 模型已存在: $MODEL_DIR/$MODEL_NAME"
    exit 0
fi

# 下载
curl -L -o "$MODEL_DIR/$MODEL_NAME" "$MODEL_URL"

echo ""
echo "✅ 下载完成: $MODEL_DIR/$MODEL_NAME"
echo ""
echo "⚠️  注意: 这是通用分类器，不是专门的皮肤分类器"
echo "   下一步需要:"
echo "   1. 使用皮肤数据集 fine-tune (准确度 90%+)"
echo "   2. 或使用 transfer learning (准确度 80%+)"
echo "   3. 或使用简化规则 (准确度 60-70%)"
echo ""
echo "当前版本将使用简化规则作为降级方案"
