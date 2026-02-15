#!/usr/bin/env swift
/**
 * YOLOv8 CoreML 推理脚本
 *
 * 用法: swift yolov8-inference.swift <图片路径> <模型路径>
 * 输出: JSON 格式的检测结果
 */

import Foundation
import CoreML
import CoreImage

// 命令行参数
guard CommandLine.arguments.count >= 3 else {
    print("{\"error\": \"用法: swift yolov8-inference.swift <图片路径> <模型路径>\"}")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let modelPath = CommandLine.arguments[2]

// YOLOv8 类别
let classNames = ["acne0_no_acne", "acne1_mild", "acne2_moderate", "acne3_severe"]
let severityMap = ["acne0_no_acne": "轻微", "acne1_mild": "轻微", "acne2_moderate": "中等", "acne3_severe": "严重"]

struct Detection: Codable {
    let `class`: String
    let confidence: Double
    let bbox: BBox
    let severity: String
}

struct BBox: Codable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

// 加载图片
let imageURL = URL(fileURLWithPath: imagePath)
guard let ciImage = CIImage(contentsOf: imageURL) else {
    print("{\"error\": \"无法加载图片: \(imagePath)\"}")
    exit(1)
}

let originalWidth = ciImage.extent.width
let originalHeight = ciImage.extent.height

// 加载模型
let modelURL = URL(fileURLWithPath: modelPath)

do {
    // 编译并加载模型
    let compiledModelURL = try MLModel.compileModel(at: modelURL)
    let model = try MLModel(contentsOf: compiledModelURL)

    // 调整图片大小到 640x640 (YOLOv8 输入尺寸)
    let targetSize = CGSize(width: 640, height: 640)
    let scaleX = targetSize.width / originalWidth
    let scaleY = targetSize.height / originalHeight

    let transform = CIFilter(name: "CILanczosScaleTransform")
    transform?.setValue(ciImage, forKey: kCIInputImageKey)
    transform?.setValue(NSNumber(value: Float(max(scaleX, scaleY))), forKey: kCIInputScaleKey)
    transform?.setValue(1.0, forKey: kCIInputAspectRatioKey)

    guard let resizedImage = transform?.outputImage else {
        print("{\"error\": \"图片缩放失败\"}")
        exit(1)
    }

    // 转换为 CVPixelBuffer
    let context = CIContext()
    var pixelBuffer: CVPixelBuffer?
    let attrs: [String: Any] = [
        kCVPixelBufferCGImageCompatibilityKey as String: true,
        kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
    ]

    CVPixelBufferCreate(
        kCFAllocatorDefault,
        Int(targetSize.width),
        Int(targetSize.height),
        kCVPixelFormatType_32ARGB,
        attrs as CFDictionary,
        &pixelBuffer
    )

    guard let buffer = pixelBuffer else {
        print("{\"error\": \"创建 PixelBuffer 失败\"}")
        exit(1)
    }

    context.render(resizedImage, to: buffer)

    // 创建模型输入
    let inputFeature = MLFeatureValue(pixelBuffer: buffer)
    let inputProvider = try MLDictionaryFeatureProvider(dictionary: ["image": inputFeature])

    // 执行推理
    let prediction = try model.prediction(from: inputProvider)

    // 解析 YOLOv8 输出
    // 尝试不同的输出名称
    var outputFeature: MLFeatureValue?
    for outputName in ["var_911", "var_909", "output", "output0"] {
        if let feature = prediction.featureValue(for: outputName) {
            outputFeature = feature
            break
        }
    }

    guard let output = outputFeature else {
        print("{\"error\": \"无法获取输出\"}")
        exit(1)
    }

    let multiArray = output.multiArrayValue!

    // 获取数据指针
    let outputPointer = UnsafePointer<Double>(OpaquePointer(multiArray.dataPointer))
    let numBoxes = 8400
    let numClasses = 4  // 我们的模型有4个类别

    var detections: [Detection] = []
    let confidenceThreshold = 0.3

    for i in 0..<numBoxes {
        // 找到最大类别置信度
        var maxClassConf = 0.0
        var maxClassIdx = 0

        for c in 0..<numClasses {
            let conf = outputPointer[(4 + c) * numBoxes + i]
            if conf > maxClassConf {
                maxClassConf = conf
                maxClassIdx = c
            }
        }

        // 过滤低置信度
        guard maxClassConf > confidenceThreshold else { continue }

        // 获取边界框 (中心点格式)
        let cx = outputPointer[0 * numBoxes + i]
        let cy = outputPointer[1 * numBoxes + i]
        let w = outputPointer[2 * numBoxes + i]
        let h = outputPointer[3 * numBoxes + i]

        // 转换到原图坐标
        let x = (cx - w / 2) / targetSize.width * originalWidth
        let y = (cy - h / 2) / targetSize.height * originalHeight
        let width = w / targetSize.width * originalWidth
        let height = h / targetSize.height * originalHeight

        let className = classNames[maxClassIdx]
        let severity = severityMap[className] ?? "轻微"

        let detection = Detection(
            class: className,
            confidence: min(1.0, maxClassConf),
            bbox: BBox(x: x, y: y, width: width, height: height),
            severity: severity
        )
        detections.append(detection)
    }

    // NMS (简化版 - 按置信度排序，保留前5个)
    detections.sort { $0.confidence > $1.confidence }
    detections = Array(detections.prefix(5))

    // 输出结果
    let result: [String: Any] = [
        "detections": detections.map { detection in
            return [
                "class": detection.class,
                "confidence": detection.confidence,
                "bbox": ["x": detection.bbox.x, "y": detection.bbox.y, "width": detection.bbox.width, "height": detection.bbox.height],
                "severity": detection.severity
            ]
        },
        "totalCount": detections.count,
        "severityScore": detections.isEmpty ? 0 : Int(detections.map { $0.confidence * 100 }.reduce(0, +) / Double(detections.count))
    ]

    if let jsonData = try? JSONSerialization.data(withJSONObject: result),
       let jsonString = String(data: jsonData, encoding: .utf8) {
        print(jsonString)
    }

} catch {
    print("{\"error\": \"推理失败: \(error.localizedDescription)\"}")
    exit(1)
}
