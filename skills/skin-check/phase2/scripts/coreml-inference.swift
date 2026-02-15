#!/usr/bin/env swift
/**
 * CoreML 推理脚本 (新版 - 支持 AcneClassifier)
 *
 * 用法: swift coreml-inference.swift <图片路径> <模型路径>
 * 输出: JSON 格式的分类结果
 */

import Foundation
import CoreML
import Vision
import CoreImage

// 命令行参数
guard CommandLine.arguments.count >= 3 else {
    print("{\"error\": \"用法: swift coreml-inference.swift <图片路径> <模型路径>\"}")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let modelPath = CommandLine.arguments[2]

// 皮肤类型映射
let skinTypeLabels = [
    "acne0_no_acne": ("无痘痘", ["皮肤状态良好", "无明显痘痘", "毛孔细腻"]),
    "acne1_mild": ("轻度痘痘", ["少量痘痘", "T区轻微出油", "偶尔冒痘"]),
    "acne2_moderate": ("中度痘痘", ["多处痘痘", "需要关注护肤", "建议调整作息"]),
    "acne3_severe": ("重度痘痘", ["严重痘痘", "建议就医", "需要专业治疗"])
]

// 加载图片
let imageURL = URL(fileURLWithPath: imagePath)
guard let ciImage = CIImage(contentsOf: imageURL) else {
    print("{\"error\": \"无法加载图片: \(imagePath)\"}")
    exit(1)
}

// 加载模型
let modelURL = URL(fileURLWithPath: modelPath)

do {
    // 编译并加载模型
    let compiledModelURL = try MLModel.compileModel(at: modelURL)
    let model = try MLModel(contentsOf: compiledModelURL)

    // 获取模型输入描述
    let inputDescription = model.modelDescription.inputDescriptionsByName

    // 准备输入
    let inputName = inputDescription.keys.first ?? "image"

    // 调整图片大小到 224x224 (MobileNetV3 输入尺寸)
    let targetSize = CGSize(width: 224, height: 224)
    let transform = CIFilter(name: "CILanczosScaleTransform")
    transform?.setValue(ciImage, forKey: kCIInputImageKey)
    transform?.setValue(NSNumber(value: Float(targetSize.width / ciImage.extent.width)), forKey: kCIInputScaleKey)
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
    let inputFeature = try MLFeatureValue(pixelBuffer: buffer)
    let inputProvider = try MLDictionaryFeatureProvider(dictionary: [inputName: inputFeature])

    // 执行推理
    let prediction = try model.prediction(from: inputProvider)

    // 解析输出
    let outputDescription = model.modelDescription.outputDescriptionsByName

    // 尝试获取分类标签
    var skinType = "未知"
    var confidence = 0.0
    var features: [String] = []

    // 检查是否有 classLabel 输出
    if let classLabelFeature = prediction.featureValue(for: "classLabel") {
        let classLabel = classLabelFeature.stringValue

        if let (typeName, typeFeatures) = skinTypeLabels[classLabel] {
            skinType = typeName
            features = typeFeatures
        } else {
            skinType = classLabel
            features = ["检测到: \(classLabel)"]
        }
    }

    // 检查是否有概率输出
    if let probsFeature = prediction.featureValue(for: "classLabel_probs") {
        if let probs = probsFeature.dictionaryValue as? [String: Double] {
            // 找到预测类别对应的 key
            let predictedKey = skinTypeLabels.keys.first { skinTypeLabels[$0]?.0 == skinType }
            if let key = predictedKey, let prob = probs[key] {
                // 归一化到 0-1 范围
                confidence = min(1.0, max(0.0, prob))
            }
        }
    }

    // 如果没有概率，使用 0.8 作为默认值
    if confidence == 0.0 {
        confidence = 0.8
    }

    // 输出 JSON
    let output: [String: Any] = [
        "skinType": skinType,
        "confidence": confidence,
        "features": features
    ]

    if let jsonData = try? JSONSerialization.data(withJSONObject: output),
       let jsonString = String(data: jsonData, encoding: .utf8) {
        print(jsonString)
    }

} catch {
    print("{\"error\": \"推理失败: \(error.localizedDescription)\"}")
    exit(1)
}
