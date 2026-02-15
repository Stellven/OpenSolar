#!/usr/bin/env python3
"""
AI 美妆顾问 - 面部分析模块
使用 MediaPipe Face Mesh 进行面部特征检测
"""

import cv2
import mediapipe as mp
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import json
import sys

# MediaPipe 初始化
mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils


@dataclass
class FaceFeatures:
    """面部特征数据"""
    # 脸型
    face_shape: str  # round, square, oval, heart, oblong

    # 五官比例
    face_width_height_ratio: float  # 脸宽/脸高比
    jaw_width_ratio: float  # 下颌宽/颧宽比
    forehead_height_ratio: float  # 额头高/脸高比
    chin_length_ratio: float  # 下巴长/脸高比

    # 眼部
    eye_spacing_ratio: float  # 眼距/脸宽比
    eye_size: str  # small, medium, large
    eye_shape: str  # round, almond, hooded, upturned

    # 鼻部
    nose_length_ratio: float  # 鼻长/脸高比
    nose_width_ratio: float  # 鼻宽/脸宽比
    nose_shape: str  # straight, aquiline, button, wide

    # 唇部
    lip_thickness: str  # thin, medium, full
    lip_width_ratio: float  # 嘴宽/脸宽比

    # 肤色（简化）
    skin_tone: str  # fair, light, medium, tan, deep
    undertone: str  # warm, cool, neutral

    # 整体风格建议
    style_suggestions: list


class FaceAnalyzer:
    """面部分析器"""

    def __init__(self):
        self.face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            min_detection_confidence=0.5
        )
        self.face_detection = mp_face_detection.FaceDetection(
            min_detection_confidence=0.5
        )

    def analyze(self, image_path: str) -> Optional[FaceFeatures]:
        """分析面部特征"""
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

        # 计算面部特征
        features = self._calculate_features(points, image, w, h)

        return features

    def _calculate_features(self, points, image, img_w, img_h) -> FaceFeatures:
        """计算面部特征"""

        # MediaPipe Face Mesh 关键点索引
        # https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png

        # 脸部轮廓点
        # 脸颊左侧: 234, 脸颊右侧: 454
        # 额头顶: 10, 下巴: 152
        # 左眼外角: 33, 右眼外角: 263
        # 左眼内角: 133, 右眼内角: 362
        # 鼻尖: 1, 鼻梁: 6
        # 左嘴角: 61, 右嘴角: 291
        # 上唇中: 13, 下唇中: 14

        # 1. 脸型分析
        face_width = self._distance(points[234], points[454])  # 脸宽
        forehead_width = self._distance(points[103], points[332])  # 额头宽
        jaw_width = self._distance(points[58], points[288])  # 下颌宽
        face_height = self._distance(points[10], points[152])  # 脸高

        # 脸宽高比
        width_height_ratio = face_width / face_height if face_height > 0 else 0

        # 下颌/颧宽比
        jaw_ratio = jaw_width / face_width if face_width > 0 else 0

        # 额头高/脸高比
        forehead_y = points[10][1]
        brow_y = (points[66][1] + points[296][1]) / 2  # 眉毛位置
        forehead_height = brow_y - forehead_y
        forehead_ratio = forehead_height / face_height if face_height > 0 else 0

        # 下巴长/脸高比
        chin_y = points[152][1]
        lip_y = (points[13][1] + points[14][1]) / 2
        chin_length = chin_y - lip_y
        chin_ratio = chin_length / face_height if face_height > 0 else 0

        # 判断脸型
        face_shape = self._determine_face_shape(
            width_height_ratio, jaw_ratio, forehead_ratio, chin_ratio
        )

        # 2. 眼部分析
        left_eye_outer = points[33]
        left_eye_inner = points[133]
        right_eye_inner = points[362]
        right_eye_outer = points[263]

        # 眼距
        eye_distance = self._distance(left_eye_inner, right_eye_inner)
        eye_spacing_ratio = eye_distance / face_width if face_width > 0 else 0

        # 眼睛大小
        left_eye_width = self._distance(left_eye_outer, left_eye_inner)
        right_eye_width = self._distance(right_eye_inner, right_eye_outer)
        avg_eye_width = (left_eye_width + right_eye_width) / 2
        eye_size = self._determine_eye_size(avg_eye_width, face_width)

        # 眼型（简化）
        eye_shape = "almond"  # 默认杏眼，实际需要更复杂的分析

        # 3. 鼻部分析
        nose_tip = points[1]
        nose_bridge = points[6]
        nose_left = points[98]
        nose_right = points[327]

        nose_length = abs(nose_bridge[1] - nose_tip[1])
        nose_width = self._distance(nose_left, nose_right)

        nose_length_ratio = nose_length / face_height if face_height > 0 else 0
        nose_width_ratio = nose_width / face_width if face_width > 0 else 0
        nose_shape = self._determine_nose_shape(nose_width_ratio)

        # 4. 唇部分析
        left_mouth = points[61]
        right_mouth = points[291]
        upper_lip = points[13]
        lower_lip = points[14]

        mouth_width = self._distance(left_mouth, right_mouth)
        lip_width_ratio = mouth_width / face_width if face_width > 0 else 0

        # 唇厚（简化）
        lip_height = abs(upper_lip[1] - lower_lip[1])
        lip_thickness = self._determine_lip_thickness(lip_height, mouth_width)

        # 5. 肤色分析
        skin_tone, undertone = self._analyze_skin_tone(image, points, img_w, img_h)

        # 6. 生成风格建议
        style_suggestions = self._generate_style_suggestions(
            face_shape, eye_size, lip_thickness, skin_tone, undertone
        )

        return FaceFeatures(
            face_shape=face_shape,
            face_width_height_ratio=round(width_height_ratio, 3),
            jaw_width_ratio=round(jaw_ratio, 3),
            forehead_height_ratio=round(forehead_ratio, 3),
            chin_length_ratio=round(chin_ratio, 3),
            eye_spacing_ratio=round(eye_spacing_ratio, 3),
            eye_size=eye_size,
            eye_shape=eye_shape,
            nose_length_ratio=round(nose_length_ratio, 3),
            nose_width_ratio=round(nose_width_ratio, 3),
            nose_shape=nose_shape,
            lip_thickness=lip_thickness,
            lip_width_ratio=round(lip_width_ratio, 3),
            skin_tone=skin_tone,
            undertone=undertone,
            style_suggestions=style_suggestions
        )

    def _distance(self, p1, p2) -> float:
        """计算两点距离"""
        return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def _determine_face_shape(self, w_h_ratio, jaw_ratio, forehead_ratio, chin_ratio) -> str:
        """判断脸型"""
        # 鹅蛋脸: 宽高比约0.75，下颌略窄
        if 0.7 < w_h_ratio < 0.8 and jaw_ratio < 0.85:
            return "oval"

        # 圆脸: 宽高比接近1
        if w_h_ratio > 0.85:
            return "round"

        # 方脸: 下颌宽，棱角分明
        if jaw_ratio > 0.9:
            return "square"

        # 心形脸: 额头宽，下巴尖
        if forehead_ratio > 0.25 and chin_ratio < 0.15:
            return "heart"

        # 长脸: 宽高比小
        if w_h_ratio < 0.65:
            return "oblong"

        return "oval"  # 默认

    def _determine_eye_size(self, eye_width, face_width) -> str:
        """判断眼睛大小"""
        ratio = eye_width / face_width if face_width > 0 else 0
        if ratio < 0.15:
            return "small"
        elif ratio > 0.22:
            return "large"
        return "medium"

    def _determine_nose_shape(self, nose_width_ratio) -> str:
        """判断鼻型"""
        if nose_width_ratio < 0.2:
            return "button"
        elif nose_width_ratio > 0.3:
            return "wide"
        return "straight"

    def _determine_lip_thickness(self, lip_height, mouth_width) -> str:
        """判断唇厚"""
        if mouth_width == 0:
            return "medium"
        ratio = lip_height / mouth_width
        if ratio < 0.15:
            return "thin"
        elif ratio > 0.3:
            return "full"
        return "medium"

    def _analyze_skin_tone(self, image, points, w, h) -> Tuple[str, str]:
        """分析肤色"""
        # 取脸颊区域的平均颜色
        # 脸颊大约在点 50 和 280 附近
        try:
            # 左脸颊区域
            left_cheek = points[50]
            # 右脸颊区域
            right_cheek = points[280]

            # 取样区域
            sample_points = [
                (left_cheek[0], left_cheek[1]),
                (right_cheek[0], right_cheek[1]),
                (points[10][0], points[10][1] + 50),  # 额头
            ]

            colors = []
            for x, y in sample_points:
                if 0 <= x < w and 0 <= y < h:
                    # 取周围 5x5 的平均色
                    x1, y1 = max(0, x-2), max(0, y-2)
                    x2, y2 = min(w, x+3), min(h, y+3)
                    region = image[y1:y2, x1:x2]
                    avg_color = np.mean(region, axis=(0, 1))
                    colors.append(avg_color)

            if colors:
                avg_bgr = np.mean(colors, axis=0)
                # 转换为 RGB
                avg_rgb = avg_bgr[::-1]
                r, g, b = avg_rgb

                # 简化的肤色分类
                brightness = (r + g + b) / 3

                if brightness > 180:
                    skin_tone = "fair"
                elif brightness > 150:
                    skin_tone = "light"
                elif brightness > 120:
                    skin_tone = "medium"
                elif brightness > 90:
                    skin_tone = "tan"
                else:
                    skin_tone = "deep"

                # 冷暖色调（简化）
                if r > b + 10:
                    undertone = "warm"
                elif b > r + 10:
                    undertone = "cool"
                else:
                    undertone = "neutral"

                return skin_tone, undertone
        except Exception:
            pass

        return "light", "neutral"

    def _generate_style_suggestions(self, face_shape, eye_size, lip_thickness,
                                     skin_tone, undertone) -> list:
        """生成风格建议"""
        suggestions = []

        # 根据脸型建议
        face_shape_tips = {
            "oval": "鹅蛋脸是标准脸型，适合各种妆容风格",
            "round": "圆脸建议强调轮廓修容，拉长视觉效果",
            "square": "方脸建议柔和棱角，用腮红柔化下颌线",
            "heart": "心形脸建议平衡额头和下巴，弱化颧骨",
            "oblong": "长脸建议横向晕染眼影，缩短面部比例"
        }
        suggestions.append(f"📐 脸型: {face_shape_tips.get(face_shape, '')}")

        # 根据眼型建议
        eye_tips = {
            "small": "小眼可以用深色眼影晕染，眼线略粗，强调眼神",
            "medium": "标准眼型，适合日常清新妆容",
            "large": "大眼是优势，可以用珠光提亮，显得更有神"
        }
        suggestions.append(f"👁️ 眼妆: {eye_tips.get(eye_size, '')}")

        # 根据唇型建议
        lip_tips = {
            "thin": "薄唇可以用唇线笔勾勒出唇形，选择浅色或珠光",
            "medium": "标准唇型，各种唇妆都适合",
            "full": "厚唇是性感优势，可以用哑光深色突出立体感"
        }
        suggestions.append(f"💄 唇妆: {lip_tips.get(lip_thickness, '')}")

        # 根据肤色建议
        skin_tips = {
            "fair": "白皙肤色适合冷粉色系，避免过于浓重的颜色",
            "light": "浅肤色适合珊瑚色、蜜桃色等暖调",
            "medium": "中等肤色适合大地色、橘棕色系",
            "tan": "小麦肤色适合金棕色、砖红色系",
            "deep": "深肤色适合浆果色、深红、金色系"
        }
        suggestions.append(f"🎨 配色: {skin_tips.get(skin_tone, '')}")

        # 根据冷暖调建议
        undertone_tips = {
            "warm": "暖皮适合珊瑚色、橘色、金色，避免冷粉色",
            "cool": "冷皮适合粉色、莓果色、银色，避免橘色",
            "neutral": "中性皮百搭，可以尝试各种色调"
        }
        suggestions.append(f"✨ 色调: {undertone_tips.get(undertone, '')}")

        return suggestions

    def to_json(self, features: FaceFeatures) -> str:
        """转换为 JSON"""
        return json.dumps({
            "face_shape": features.face_shape,
            "proportions": {
                "face_width_height_ratio": features.face_width_height_ratio,
                "jaw_width_ratio": features.jaw_width_ratio,
                "forehead_height_ratio": features.forehead_height_ratio,
                "chin_length_ratio": features.chin_length_ratio
            },
            "eyes": {
                "spacing_ratio": features.eye_spacing_ratio,
                "size": features.eye_size,
                "shape": features.eye_shape
            },
            "nose": {
                "length_ratio": features.nose_length_ratio,
                "width_ratio": features.nose_width_ratio,
                "shape": features.nose_shape
            },
            "lips": {
                "thickness": features.lip_thickness,
                "width_ratio": features.lip_width_ratio
            },
            "skin": {
                "tone": features.skin_tone,
                "undertone": features.undertone
            },
            "style_suggestions": features.style_suggestions
        }, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("用法: python face_analyzer.py <图片路径>")
        sys.exit(1)

    image_path = sys.argv[1]
    analyzer = FaceAnalyzer()

    features = analyzer.analyze(image_path)

    if features:
        # 只输出纯 JSON，便于程序解析
        print(analyzer.to_json(features))
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
