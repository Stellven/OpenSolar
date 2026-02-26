#!/usr/bin/env bun
/**
 * 皮肤检测 Skill
 * 拍照 → AI视觉分析 → 四专家评审 → 综合报告
 */

import { exec } from "child_process";
import { promisify } from "util";
import { readFileSync, unlinkSync } from "fs";
import { join } from "path";

const execAsync = promisify(exec);

interface ExpertReview {
  expert: string;
  role: string;
  analysis: string;
}

interface SkinAnalysis {
  skinType: string;
  issues: string[];
  timestamp: string;
  photoPath: string;
}

interface ConsolidatedReport {
  consensus: string[];
  concerns: string[];
  medicalAdvice: string;
}

// 拍照
async function takePhoto(): Promise<string> {
  console.log("📸 准备拍照...");

  // 调用 selfie skill
  const { stdout } = await execAsync("bun ~/.claude/skills/selfie/selfie.ts --countdown 3");

  // 从输出中提取照片路径
  const match = stdout.match(/Saved to: (.+)/);
  if (!match) {
    throw new Error("拍照失败，未找到照片路径");
  }

  const photoPath = match[1].trim();
  console.log(`✅ 照片已保存: ${photoPath}`);

  return photoPath;
}

// 初步视觉分析 (Gemini 2.0 Flash)
async function initialAnalysis(photoPath: string, focus?: string): Promise<SkinAnalysis> {
  console.log("🔍 AI 视觉分析中...");

  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    console.warn("⚠️  GOOGLE_API_KEY 未设置，使用模拟数据");
    return {
      skinType: "混合性",
      issues: ["T区轻微出油", "脸颊少量色斑", "鼻翼周围毛孔粗大"],
      timestamp: new Date().toISOString(),
      photoPath
    };
  }

  // 读取图片并转为 base64
  const imageData = readFileSync(photoPath);
  const base64Image = imageData.toString('base64');
  const mimeType = photoPath.endsWith('.png') ? 'image/png' : 'image/jpeg';

  const prompt = focus
    ? `请分析这张皮肤照片，重点关注：${focus}。识别皮肤类型、主要问题、需要注意的地方。以JSON格式回复：{"skinType":"...", "issues":["..."]}`
    : `请分析这张皮肤照片，识别皮肤类型（油性/干性/混合性/中性）、主要问题（痘痘/斑点/细纹/毛孔等）、整体状况。以JSON格式回复：{"skinType":"...", "issues":["..."]}`;

  try {
    // 使用 v1beta + gemini-1.5-flash-latest
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contents: [{
            parts: [
              { text: prompt },
              { inline_data: { mime_type: mimeType, data: base64Image } }
            ]
          }]
        })
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Gemini API 错误详情: ${errorText}`);
      throw new Error(`Gemini API 错误: ${response.status}`);
    }

    const data = await response.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!text) {
      throw new Error("Gemini API 返回为空");
    }

    // 解析 JSON 响应
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[0]);
      const analysis: SkinAnalysis = {
        skinType: parsed.skinType || "未知",
        issues: parsed.issues || [],
        timestamp: new Date().toISOString(),
        photoPath
      };

      console.log(`✅ 初步分析完成: ${analysis.skinType}`);
      return analysis;
    }

    throw new Error("无法解析 Gemini 响应");

  } catch (error) {
    console.error("❌ Gemini 分析失败:", error);
    console.warn("⚠️  使用模拟数据");
    return {
      skinType: "混合性（模拟）",
      issues: ["T区轻微出油", "脸颊少量色斑", "鼻翼周围毛孔粗大"],
      timestamp: new Date().toISOString(),
      photoPath
    };
  }
}

// 调用单个专家模型
async function callExpert(
  name: string,
  model: string,
  system: string,
  context: string
): Promise<string> {
  if (model.startsWith("gemini")) {
    // Gemini API
    const apiKey = process.env.GOOGLE_API_KEY;
    if (!apiKey) throw new Error("GOOGLE_API_KEY 未设置");

    // 使用 v1beta + gemini-1.5-flash-latest
    const modelName = "gemini-1.5-flash-latest";

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_instruction: { parts: [{ text: system }] },
          contents: [{ parts: [{ text: context }] }]
        })
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Gemini API 错误详情 (${modelName}): ${errorText}`);
      throw new Error(`Gemini API 错误: ${response.status}`);
    }
    const data = await response.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text || "分析失败";

  } else if (model.startsWith("deepseek")) {
    // DeepSeek API
    const apiKey = process.env.DEEPSEEK_API_KEY;
    if (!apiKey) throw new Error("DEEPSEEK_API_KEY 未设置");

    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: "deepseek-chat",
        messages: [
          { role: "system", content: system },
          { role: "user", content: context }
        ],
        temperature: 0.7,
        max_tokens: 500
      })
    });

    if (!response.ok) throw new Error(`DeepSeek API 错误: ${response.status}`);
    const data = await response.json();
    return data.choices?.[0]?.message?.content || "分析失败";

  } else if (model.startsWith("glm")) {
    // GLM API
    const apiKey = process.env.ZHIPU_API_KEY;
    if (!apiKey) throw new Error("ZHIPU_API_KEY 未设置");

    const response = await fetch("https://open.bigmodel.cn/api/paas/v4/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: "glm-5",
        messages: [
          { role: "system", content: system },
          { role: "user", content: context }
        ],
        temperature: 0.7,
        max_tokens: 500
      })
    });

    if (!response.ok) throw new Error(`GLM API 错误: ${response.status}`);
    const data = await response.json();
    return data.choices?.[0]?.message?.content || "分析失败";
  }

  throw new Error(`未知模型: ${model}`);
}

// 专家评审 (并行调用四个模型)
async function expertReview(analysis: SkinAnalysis): Promise<ExpertReview[]> {
  console.log("👥 专家评审中（并行）...");

  const context = `
皮肤检测照片分析结果：
- 皮肤类型: ${analysis.skinType}
- 主要问题: ${analysis.issues.join(", ")}

请从你的专业角度给出：
1. 问题分析
2. 护理建议
3. 是否需要就医

回复简洁明了，2-3句话。
`;

  const experts = [
    {
      name: "稳健派",
      model: "gemini-2.5-pro",
      role: "严谨医学分析",
      system: "你是稳健派，一个严谨务实的皮肤科专家。从医学角度分析皮肤问题。"
    },
    {
      name: "审判官",
      model: "deepseek-r1",
      role: "深度推理",
      system: "你是审判官，擅长深度推理。从生活习惯、作息等多角度分析皮肤问题的根源。"
    },
    {
      name: "智囊",
      model: "glm-5",
      role: "生活建议",
      system: "你是智囊，中文友好的护肤顾问。给出实用的日常护理建议和产品推荐。"
    },
    {
      name: "探索派",
      model: "gemini-3-pro-preview",
      role: "综合评估",
      system: "你是探索派，擅长权衡和综合评估。给出平衡的整体建议。"
    }
  ];

  // 并行调用所有专家
  const reviews = await Promise.all(
    experts.map(async (expert) => {
      try {
        const analysis = await callExpert(expert.name, expert.model, expert.system, context);
        return {
          expert: expert.name,
          role: expert.role,
          analysis
        };
      } catch (error: any) {
        console.error(`${expert.name} 分析失败:`, error.message);

        // API key 缺失时使用模拟回复
        if (error.message.includes("未设置")) {
          const mockReplies: Record<string, string> = {
            "稳健派": "建议增加清洁频率，使用温和型洁面产品。色斑可能需要专业美白治疗。毛孔问题可通过定期去角质改善。",
            "审判官": "皮肤出油和毛孔粗大可能与作息、饮食相关。建议规律作息、多喝水、减少油炸食品摄入。压力也会影响皮肤状态。",
            "智囊": "推荐使用含烟酰胺成分的精华液淡化色斑，水杨酸产品收缩毛孔。日常注意防晒（SPF30+），选择清爽型乳液。",
            "探索派": "整体状况良好，属于常见的混合性皮肤。注意T区和U区分区护理，保持清洁和保湿平衡。无需过度担心，坚持日常护理即可。"
          };
          return {
            expert: expert.name,
            role: expert.role,
            analysis: mockReplies[expert.name] + " （模拟）"
          };
        }

        return {
          expert: expert.name,
          role: expert.role,
          analysis: "分析失败，请重试"
        };
      }
    })
  );

  console.log(`✅ 专家评审完成（${reviews.length}/4）`);

  return reviews;
}

// 整合报告
function consolidateReport(analysis: SkinAnalysis, reviews: ExpertReview[]): ConsolidatedReport {
  // 提取一致性建议（简化版：关键词匹配）
  const keywords = ["清洁", "防晒", "保湿", "作息", "饮食"];
  const consensus: string[] = [];

  keywords.forEach(keyword => {
    const count = reviews.filter(r => r.analysis.includes(keyword)).length;
    if (count >= 3) { // 至少3位专家提到
      consensus.push(`${keyword}（${count}位专家提到）`);
    }
  });

  // 提取需要关注的问题
  const concerns: string[] = [];
  if (analysis.issues.includes("色斑")) {
    const mentionCount = reviews.filter(r => r.analysis.includes("色斑") || r.analysis.includes("美白")).length;
    if (mentionCount >= 2) {
      concerns.push(`色斑问题（${mentionCount}位专家提到）- 建议使用美白精华`);
    }
  }

  // 就医建议
  const needDoctor = reviews.some(r =>
    r.analysis.includes("就医") ||
    r.analysis.includes("医生") ||
    r.analysis.includes("专业治疗")
  );

  const medicalAdvice = needDoctor
    ? "建议咨询专业皮肤科医生"
    : "当前无严重问题，不需要就医";

  return { consensus, concerns, medicalAdvice };
}

// 输出报告
function printReport(
  analysis: SkinAnalysis,
  reviews: ExpertReview[],
  report: ConsolidatedReport
) {
  const timestamp = new Date(analysis.timestamp).toLocaleString('zh-CN');

  console.log(`
┌─ 📸 皮肤检测报告 ─────────────────────────────────┐
│                                                   │
│ 📊 基本信息                                        │
│ • 拍摄时间: ${timestamp}                           │
│ • 分析模型: Gemini 2.0 Flash + 4专家              │
│                                                   │
├─ 🔍 AI 初步分析 ──────────────────────────────────┤
│                                                   │
│ 皮肤类型: ${analysis.skinType}                     │
│ 主要问题:                                         │
${analysis.issues.map(issue => `│ • ${issue}`).join('\n')}
│                                                   │
├─ 👥 专家评审 ─────────────────────────────────────┤
│                                                   │
${reviews.map(r => `│ ${getExpertEmoji(r.expert)} ${r.expert} (${r.role}):\n│ ${r.analysis}\n│`).join('\n')}
├─ 💡 综合建议 ─────────────────────────────────────┤
│                                                   │
│ ✅ 一致性建议:                                     │
${report.consensus.length > 0
  ? report.consensus.map(c => `│ • ${c}`).join('\n')
  : '│ • 专家意见略有分歧，建议综合参考'}
│                                                   │
${report.concerns.length > 0
  ? `│ ⚠️  需要关注:\n${report.concerns.map(c => `│ • ${c}`).join('\n')}\n│\n`
  : ''}│ 🏥 就医建议:                                       │
│ • ${report.medicalAdvice}                         │
│                                                   │
└───────────────────────────────────────────────────┘

⚠️  免责声明: 此检测仅供参考，不能替代专业医疗诊断
  `);
}

function getExpertEmoji(expertName: string): string {
  const emojiMap: Record<string, string> = {
    "稳健派": "🔬",
    "审判官": "🐪",
    "智囊": "🐴",
    "探索派": "🦄"
  };
  return emojiMap[expertName] || "👤";
}

// 主函数
async function main() {
  const args = process.argv.slice(2);
  const focus = args[0]; // 可选：关注点（痘痘/斑点/整体等）

  console.log("🚀 启动皮肤检测...\n");

  try {
    // 1. 拍照
    const photoPath = await takePhoto();

    // 2. 初步分析
    const analysis = await initialAnalysis(photoPath, focus);

    // 3. 专家评审
    const reviews = await expertReview(analysis);

    // 4. 整合报告
    const report = consolidateReport(analysis, reviews);

    // 5. 输出报告
    printReport(analysis, reviews, report);

    // 清理临时文件（可选）
    // unlinkSync(photoPath);

  } catch (error) {
    console.error("❌ 检测失败:", error);
    process.exit(1);
  }
}

main();
