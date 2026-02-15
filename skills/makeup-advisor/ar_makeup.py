#!/usr/bin/env python3
"""
AR 虚拟试妆 - 实时叠加妆容效果

功能:
1. 口红叠加
2. 眼影叠加
3. 腮红叠加
4. 美瞳效果

使用 MediaPipe Face Mesh 精确定位
"""

import cv2
import mediapipe as mp
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional
import sys


@dataclass
class MakeupStyle:
    """妆容风格"""
    name: str
    lipstick_color: Tuple[int, int, int]  # BGR
    lipstick_opacity: float
    eyeshadow_color: Tuple[int, int, int]
    eyeshadow_opacity: float
    blush_color: Tuple[int, int, int]
    blush_opacity: float
    highlight: bool = True


# 预设妆容风格
MAKEUP_STYLES = {
    "natural": MakeupStyle(
        name="裸妆",
        lipstick_color=(120, 150, 200),  # 嫩粉色
        lipstick_opacity=0.3,
        eyeshadow_color=(200, 180, 160),  # 浅棕
        eyeshadow_opacity=0.2,
        blush_color=(180, 160, 200),  # 淡粉
        blush_opacity=0.3
    ),
    "sweet": MakeupStyle(
        name="甜美妆",
        lipstick_color=(80, 120, 200),  # 粉红
        lipstick_opacity=0.6,
        eyeshadow_color=(180, 160, 220),  # 粉紫
        eyeshadow_opacity=0.4,
        blush_color=(150, 140, 200),  # 桃粉
        blush_opacity=0.5
    ),
    "cool": MakeupStyle(
        name="冷酷妆",
        lipstick_color=(50, 50, 150),  # 深红
        lipstick_opacity=0.7,
        eyeshadow_color=(100, 100, 100),  # 灰色
        eyeshadow_opacity=0.5,
        blush_color=(180, 170, 180),  # 裸色
        blush_opacity=0.3
    ),
    "party": MakeupStyle(
        name="派对妆",
        lipstick_color=(30, 30, 180),  # 正红
        lipstick_opacity=0.8,
        eyeshadow_color=(180, 100, 200),  # 金棕
        eyeshadow_opacity=0.6,
        blush_color=(160, 130, 190),  # 橘粉
        blush_opacity=0.6
    )
}


class ARMakeup:
    """AR 虚拟试妆"""

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            min_detection_confidence=0.5
        )

        # 嘴唇关键点索引
        self.LIPS_UPPER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
        self.LIPS_LOWER = [146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
        self.LIPS_OUTER = self.LIPS_UPPER + self.LIPS_LOWER

        # 左眼关键点
        self.LEFT_EYE = [33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7]
        # 右眼关键点
        self.RIGHT_EYE = [362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382]

        # 脸颊区域（左）
        self.LEFT_CHEEK = [50, 101, 118, 119, 120, 121, 187, 207, 206]
        # 脸颊区域（右）
        self.RIGHT_CHEEK = [280, 330, 347, 348, 349, 350, 416, 436, 435]

    def apply_makeup(self, image_path: str, style_name: str = "natural") -> Optional[np.ndarray]:
        """应用妆容"""
        style = MAKEUP_STYLES.get(style_name, MAKEUP_STYLES["natural"])

        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ 无法读取图片: {image_path}")
            return None

        # 转换为 RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]

        # 检测面部关键点
        results = self.face_mesh.process(image_rgb)

        if not results.multi_face_landmarks:
            print("❌ 未检测到人脸")
            return None

        landmarks = results.multi_face_landmarks[0]

        # 提取关键点坐标
        points = []
        for landmark in landmarks.landmark:
            points.append((int(landmark.x * w), int(landmark.y * h)))

        # 复制图片用于编辑
        result = image.copy()

        # 应用各部分妆容
        result = self._apply_lipstick(result, points, style)
        result = self._apply_eyeshadow(result, points, style)
        result = self._apply_blush(result, points, style)

        if style.highlight:
            result = self._apply_highlight(result, points)

        return result

    def _apply_lipstick(self, image: np.ndarray, points: list, style: MakeupStyle) -> np.ndarray:
        """应用口红"""
        # 获取嘴唇轮廓点
        lips_points = [points[i] for i in self.LIPS_OUTER]

        # 创建嘴唇遮罩
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        pts = np.array(lips_points, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)

        # 应用颜色
        color_layer = np.zeros_like(image)
        color_layer[:] = style.lipstick_color

        # 混合
        result = image.copy()
        mask_bool = mask > 0
        result[mask_bool] = cv2.addWeighted(
            image, 1 - style.lipstick_opacity,
            color_layer, style.lipstick_opacity,
            0
        )[mask_bool]

        return result

    def _apply_eyeshadow(self, image: np.ndarray, points: list, style: MakeupStyle) -> np.ndarray:
        """应用眼影"""
        result = image.copy()

        for eye_indices in [self.LEFT_EYE, self.RIGHT_EYE]:
            # 获取眼睛上方的区域
            eye_points = [points[i] for i in eye_indices]

            # 计算眼睛中心
            center_x = sum(p[0] for p in eye_points) // len(eye_points)
            center_y = sum(p[1] for p in eye_points) // len(eye_points)

            # 创建眼影区域（眼睛上方椭圆形）
            mask = np.zeros(image.shape[:2], dtype=np.uint8)

            # 眼影范围
            eye_width = max(p[0] for p in eye_points) - min(p[0] for p in eye_points)
            eye_height = max(p[1] for p in eye_points) - min(p[1] for p in eye_points)

            # 椭圆中心在眼睛上方
            ellipse_center = (center_x, center_y - int(eye_height * 0.5))
            axes = (int(eye_width * 0.8), int(eye_height * 1.2))

            cv2.ellipse(mask, ellipse_center, axes, 0, 0, 360, 255, -1)

            # 高斯模糊让边缘更自然
            mask = cv2.GaussianBlur(mask, (21, 21), 0)

            # 应用颜色
            color_layer = np.zeros_like(image)
            color_layer[:] = style.eyeshadow_color

            # 混合
            mask_float = mask.astype(float) / 255 * style.eyeshadow_opacity
            for c in range(3):
                result[:, :, c] = (
                    result[:, :, c] * (1 - mask_float) +
                    color_layer[:, :, c] * mask_float
                )

        return result

    def _apply_blush(self, image: np.ndarray, points: list, style: MakeupStyle) -> np.ndarray:
        """应用腮红"""
        result = image.copy()

        # 左右脸颊
        for cheek_indices in [self.LEFT_CHEEK, self.RIGHT_CHEEK]:
            cheek_points = [points[i] for i in cheek_indices]

            # 计算脸颊中心
            center_x = sum(p[0] for p in cheek_points) // len(cheek_points)
            center_y = sum(p[1] for p in cheek_points) // len(cheek_points)

            # 创建腮红遮罩
            mask = np.zeros(image.shape[:2], dtype=np.uint8)

            # 腮红范围（圆形，稍大）
            radius = 40  # 可调整

            cv2.circle(mask, (center_x, center_y), radius, 255, -1)

            # 高斯模糊
            mask = cv2.GaussianBlur(mask, (31, 31), 0)

            # 应用颜色
            color_layer = np.zeros_like(image)
            color_layer[:] = style.blush_color

            # 混合
            mask_float = mask.astype(float) / 255 * style.blush_opacity
            for c in range(3):
                result[:, :, c] = (
                    result[:, :, c] * (1 - mask_float) +
                    color_layer[:, :, c] * mask_float
                )

        return result

    def _apply_highlight(self, image: np.ndarray, points: list) -> np.ndarray:
        """应用高光"""
        result = image.copy()

        # 高光区域：T区、颧骨、下巴
        highlight_points = [
            # 鼻梁
            [6, 197, 195, 5],
            # 颧骨
            [50, 101, 280, 330]
        ]

        # 简化：在鼻梁加高光
        nose_bridge = [points[6], points[197]]
        center_x = (nose_bridge[0][0] + nose_bridge[1][0]) // 2
        center_y = (nose_bridge[0][1] + nose_bridge[1][1]) // 2

        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.line(mask, nose_bridge[0], nose_bridge[1], 255, 8)
        mask = cv2.GaussianBlur(mask, (15, 15), 0)

        # 提亮
        mask_float = mask.astype(float) / 255 * 0.3
        for c in range(3):
            result[:, :, c] = np.clip(
                result[:, :, c] + mask_float * 50,
                0, 255
            )

        return result


def main():
    if len(sys.argv) < 3:
        print("用法: python ar_makeup.py <图片路径> <风格>")
        print("风格: natural | sweet | cool | party")
        print("\n示例:")
        print("  python ar_makeup.py photo.jpg sweet")
        print("  python ar_makeup.py photo.jpg party output.jpg")
        sys.exit(1)

    image_path = sys.argv[1]
    style_name = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else "makeup_result.jpg"

    print(f"🎨 应用 {style_name} 妆容...")

    ar_makeup = ARMakeup()
    result = ar_makeup.apply_makeup(image_path, style_name)

    if result is not None:
        cv2.imwrite(output_path, result)
        print(f"✅ 妆容已应用，保存到: {output_path}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
