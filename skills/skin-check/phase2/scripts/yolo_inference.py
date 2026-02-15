#!/usr/bin/env python3
"""
YOLOv8 皮肤病灶检测推理脚本

用法: python3 yolo_inference.py <图片路径> [模型路径]
输出: JSON 格式的检测结果
"""

import sys
import json
from pathlib import Path

# 加载 YOLOv8
try:
    from ultralytics import YOLO
except ImportError:
    print(json.dumps({"error": "ultralytics 未安装"}))
    sys.exit(1)

from PIL import Image
import numpy as np

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "用法: python3 yolo_inference.py <图片路径>"}))
        sys.exit(1)

    image_path = sys.argv[1]
    model_path = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).parent.parent / "models" / "acne_yolov8" / "weights" / "best.pt"
    )

    # 检查图片是否存在
    if not Path(image_path).exists():
        print(json.dumps({"error": f"图片不存在: {image_path}"}))
        sys.exit(1)

    try:
        # 加载模型
        model = YOLO(model_path)

        # 推理
        results = model(image_path, verbose=False)

        # 类别映射
        class_names = ["acne0_no_acne", "acne1_mild", "acne2_moderate", "acne3_severe"]
        severity_map = {
            "acne0_no_acne": "轻微",
            "acne1_mild": "轻微",
            "acne2_moderate": "中等",
            "acne3_severe": "严重"
        }

        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for i in range(len(boxes)):
                box = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                cls = int(boxes.cls[i].cpu().numpy())

                class_name = class_names[cls] if cls < len(class_names) else f"class_{cls}"
                severity = severity_map.get(class_name, "轻微")

                detections.append({
                    "class": class_name,
                    "confidence": round(conf, 3),
                    "bbox": {
                        "x": float(box[0]),
                        "y": float(box[1]),
                        "width": float(box[2] - box[0]),
                        "height": float(box[3] - box[1])
                    },
                    "severity": severity
                })

        # 计算严重程度分数
        if detections:
            avg_conf = sum(d["confidence"] for d in detections) / len(detections)
            severity_score = int(avg_conf * 100)
        else:
            severity_score = 0

        result = {
            "detections": detections,
            "totalCount": len(detections),
            "severityScore": severity_score
        }

        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
