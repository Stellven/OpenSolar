---
name: selfie
description: 使用摄像头拍照 - 支持倒计时和自动保存
user-invocable: true
argument-hint: "[countdown] [filename]"
---

# /selfie - 摄像头拍照

使用 Mac 摄像头快速拍照。

## 用法

```bash
/selfie                    # 立即拍照，保存到桌面
/selfie 3                  # 3秒倒计时后拍照
/selfie 3 vacation.jpg     # 3秒倒计时，指定文件名
/selfie --open             # 拍照后自动打开预览
```

## 执行流程

### 1. 解析参数

```bash
# 默认值
COUNTDOWN=0
FILENAME="selfie_$(date +%Y%m%d_%H%M%S).jpg"
OUTPUT_DIR=~/Desktop
```

### 2. 倒计时提示

如果设置了倒计时：

```
┌─────────────────────────────────────────────────────────────┐
│                     📸 SELFIE                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                         3...                                │
│                                                             │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

### 3. 拍照

```bash
imagesnap -w 1.0 "$OUTPUT_DIR/$FILENAME"
```

参数说明：
- `-w 1.0`: 预热时间，让摄像头调整曝光

### 4. 输出结果

```
┌─────────────────────────────────────────────────────────────┐
│                     📸 SELFIE CAPTURED                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Status     SUCCESS ✓                                       │
│  File       ~/Desktop/selfie_20260130_225500.jpg            │
│  Size       1.2 MB                                          │
│                                                             │
└───────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─┘
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `countdown` | 倒计时秒数 | 0 (立即拍) |
| `filename` | 文件名 | selfie_时间戳.jpg |
| `--open` | 拍完自动打开 | false |
| `--dir <path>` | 保存目录 | ~/Desktop |

## 依赖

- **imagesnap**: `brew install imagesnap`
- **摄像头权限**: 系统偏好设置 → 隐私与安全性 → 摄像头

## 示例

```bash
# 快速自拍
/selfie

# 3秒准备时间
/selfie 3

# 保存到特定位置
/selfie 3 --dir ~/Pictures/Selfies

# 拍完自动打开
/selfie --open
```

## 高级用法

### 连拍模式

```bash
# 拍3张，每张间隔2秒
for i in {1..3}; do
  /selfie 0 "burst_$i.jpg"
  sleep 2
done
```

### 定时拍照

```bash
# 10秒后拍照
/selfie 10 meeting_photo.jpg
```

## 相关 Skill

- `/screen` - 截屏 (如果存在)
