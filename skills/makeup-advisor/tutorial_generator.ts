#!/usr/bin/env bun
/**
 * 美妆教程生成器
 *
 * 使用多模态大模型分析面部照片，生成个性化化妆教程
 */

import { exec } from "child_process";
import { promisify } from "util";
import { readFileSync, existsSync } from "fs";
import { basename } from "path";

const execAsync = promisify(exec);

interface TutorialStep {
  step: number;
  title: string;
  description: string;
  products: string[];
  tips: string[];
  duration: string; // 预计时间
}

interface MakeupTutorial {
  title: string;
  difficulty: "简单" | "中等" | "高级";
  totalTime: string;
  skin_prep: string[];
  steps: TutorialStep[];
  products_needed: {
    category: string;
    items: string[];
  }[];
  common_mistakes: string[];
  pro_tips: string[];
}

// 生成教程（使用多模态模型）
export async function generateTutorial(
  imagePath: string,
  style: string = "日常妆",
  options: {
    occasion?: string;
    difficulty?: "简单" | "中等" | "高级";
    skinConcerns?: string[];
  } = {}
): Promise<MakeupTutorial | null> {
  console.log(`🎨 生成 "${style}" 化妆教程...`);

  // 1. 先分析面部特征
  const faceAnalysis = await analyzeFace(imagePath);
  if (!faceAnalysis) {
    console.log("❌ 面部分析失败");
    return null;
  }

  // 2. 基于特征生成教程
  const tutorial = buildTutorial(faceAnalysis, style, options);

  return tutorial;
}

// 面部分析
async function analyzeFace(imagePath: string): Promise<any> {
  try {
    const { stdout } = await execAsync(
      `python3 ${__dirname}/face_analyzer.py "${imagePath}"`,
      { timeout: 30000 }
    );
    return JSON.parse(stdout);
  } catch (error) {
    return null;
  }
}

// 构建教程
function buildTutorial(
  faceAnalysis: any,
  style: string,
  options: {
    occasion?: string;
    difficulty?: "简单" | "中等" | "高级";
    skinConcerns?: string[];
  }
): MakeupTutorial {
  const { face_shape, skin, eyes, lips } = faceAnalysis;
  const difficulty = options.difficulty || "中等";

  // 基于脸型和风格选择教程模板
  const tutorialTemplates: Record<string, Partial<MakeupTutorial>> = {
    "日常妆": {
      title: "清新日常通勤妆",
      difficulty: "简单",
      totalTime: "10分钟",
      skin_prep: [
        "洁面后使用爽肤水",
        "涂抹精华和面霜",
        "防晒隔离不能少"
      ]
    },
    "约会妆": {
      title: "甜美约会心动妆",
      difficulty: "中等",
      totalTime: "20分钟",
      skin_prep: [
        "面膜补水，肌肤水润",
        "妆前乳提亮肤色",
        "眼部遮瑕，消除疲惫感"
      ]
    },
    "派对妆": {
      title: "闪亮派对女王妆",
      difficulty: "高级",
      totalTime: "30分钟",
      skin_prep: [
        "深层清洁，去除角质",
        "高保湿面膜打底",
        "妆前乳+遮瑕膏组合"
      ]
    }
  };

  const template = tutorialTemplates[style] || tutorialTemplates["日常妆"];

  // 生成步骤（基于面部特征个性化）
  const steps = generateSteps(faceAnalysis, difficulty);

  // 生成产品清单
  const products = generateProductsList(faceAnalysis, style);

  // 生成常见错误和技巧
  const mistakes = generateCommonMistakes(faceAnalysis);
  const tips = generateProTips(faceAnalysis, style);

  return {
    title: template.title || style,
    difficulty: template.difficulty as "简单" | "中等" | "高级",
    totalTime: template.totalTime || "15分钟",
    skin_prep: template.skin_prep || [],
    steps,
    products_needed: products,
    common_mistakes: mistakes,
    pro_tips: tips
  };
}

// 生成化妆步骤
function generateSteps(face: any, difficulty: string): TutorialStep[] {
  const steps: TutorialStep[] = [];
  const { face_shape, eyes, lips, skin } = face;

  // 步骤1: 底妆
  steps.push({
    step: 1,
    title: "底妆",
    description: `${face_shape === "round" ? "圆脸需要在脸颊两侧打阴影" : face_shape === "square" ? "方脸要弱化下颌线条" : "均匀肤色即可"}`,
    products: ["粉底液", "遮瑕膏", "定妆粉"],
    tips: [
      skin?.tone === "fair" ? "选择最白或次白色号" : "选择自然色号",
      "少量多次，薄涂更自然"
    ],
    duration: "3分钟"
  });

  // 步骤2: 眉毛
  steps.push({
    step: 2,
    title: "眉毛",
    description: `根据${face_shape}脸型调整眉形`,
    products: ["眉笔", "眉粉", "染眉膏"],
    tips: [
      face_shape === "round" ? "眉峰略高，拉长脸型" : "",
      face_shape === "long" ? "眉毛可以画平一点" : "",
      "眉头虚，眉尾实"
    ].filter(Boolean),
    duration: "2分钟"
  });

  // 步骤3: 眼妆
  steps.push({
    step: 3,
    title: "眼妆",
    description: `${eyes?.size === "small" ? "小眼可以晕染深色眼影放大" : eyes?.size === "large" ? "大眼适合珠光提亮" : "标准眼型，百搭眼妆"}`,
    products: ["眼影盘", "眼线笔", "睫毛膏"],
    tips: [
      "眼影由浅到深晕染",
      "眼线贴着睫毛根部画",
      difficulty !== "简单" ? "下眼睑也要晕染" : ""
    ].filter(Boolean),
    duration: "5分钟"
  });

  // 步骤4: 腮红
  steps.push({
    step: 4,
    title: "腮红",
    description: `提升气色，修饰脸型`,
    products: ["腮红", "腮红刷"],
    tips: [
      face_shape === "round" ? "腮红斜向上扫，拉长脸型" : "",
      face_shape === "long" ? "腮红横向扫，缩短脸型" : "",
      skin?.undertone === "warm" ? "选择珊瑚色、橘色系" : "",
      skin?.undertone === "cool" ? "选择粉色、莓果色系" : ""
    ].filter(Boolean),
    duration: "1分钟"
  });

  // 步骤5: 唇妆
  steps.push({
    step: 5,
    title: "唇妆",
    description: `${lips?.thickness === "thin" ? "薄唇可以用唇线笔勾勒出唇形" : lips?.thickness === "full" ? "厚唇适合哑光深色" : "标准唇型，各种唇妆都适合"}`,
    products: ["唇膏", "唇线笔", "唇蜜"],
    tips: [
      "先涂唇膏再叠加唇蜜",
      "唇峰要画清晰"
    ],
    duration: "1分钟"
  });

  // 高级难度增加修容步骤
  if (difficulty === "高级" || difficulty === "中等") {
    steps.splice(4, 0, {
      step: 4,
      title: "修容高光",
      description: "立体轮廓，精致妆容",
      products: ["修容粉", "高光", "修容刷"],
      tips: [
        "修容：颧骨下方、下颌线、发际线",
        "高光：T区、颧骨高点、下巴",
        "少量多次，晕染自然"
      ],
      duration: "3分钟"
    });

    // 重新编号
    steps.forEach((s, i) => s.step = i + 1);
  }

  return steps;
}

// 生成产品清单
function generateProductsList(face: any, style: string): MakeupTutorial["products_needed"] {
  return [
    {
      category: "底妆",
      items: ["粉底液/气垫", "遮瑕膏", "定妆粉/喷雾"]
    },
    {
      category: "眉毛",
      items: ["眉笔/眉粉", "染眉膏"]
    },
    {
      category: "眼妆",
      items: ["大地色眼影盘", "眼线笔", "睫毛膏"]
    },
    {
      category: "腮红修容",
      items: ["腮红", "修容粉", "高光"]
    },
    {
      category: "唇妆",
      items: ["唇膏/唇釉", "唇线笔"]
    },
    {
      category: "工具",
      items: ["美妆蛋", "眼影刷套装", "腮红刷"]
    }
  ];
}

// 生成常见错误
function generateCommonMistakes(face: any): string[] {
  const mistakes = [
    "底妆太厚，显得假面",
    "眉毛画太粗，显凶",
    "眼影晕染不均匀，有边界线",
    "腮红位置不对，显老"
  ];

  if (face?.face_shape === "round") {
    mistakes.push("圆脸修容不够，显得更圆");
  }
  if (face?.face_shape === "long") {
    mistakes.push("长脸腮红太低，拉长脸部");
  }

  return mistakes;
}

// 生成专业技巧
function generateProTips(face: any, style: string): string[] {
  return [
    "妆前敷面膜，底妆更服帖",
    "用美妆蛋轻拍，不要来回蹭",
    "眼影先打底色，再叠加深色",
    "口红纸巾抿一下再涂第二层，更持久",
    "定妆喷雾Z字形喷，更均匀"
  ];
}

// 格式化输出
export function formatTutorial(tutorial: MakeupTutorial): string {
  let output = `💄 ${tutorial.title}\n`;
  output += `═`.repeat(40) + `\n\n`;
  output += `⏱️ 预计时间: ${tutorial.totalTime}\n`;
  output += `📊 难度: ${tutorial.difficulty}\n\n`;

  output += `【妆前准备】\n`;
  for (const prep of tutorial.skin_prep) {
    output += `  • ${prep}\n`;
  }
  output += `\n`;

  output += `【化妆步骤】\n`;
  for (const step of tutorial.steps) {
    output += `\n${step.step}. ${step.title} (${step.duration})\n`;
    output += `   ${step.description}\n`;
    output += `   产品: ${step.products.join("、")}\n`;
    if (step.tips.length > 0) {
      output += `   💡 ${step.tips.join("；")}\n`;
    }
  }

  output += `\n【产品清单】\n`;
  for (const cat of tutorial.products_needed) {
    output += `  ${cat.category}: ${cat.items.join("、")}\n`;
  }

  output += `\n【常见错误】\n`;
  for (const mistake of tutorial.common_mistakes) {
    output += `  ❌ ${mistake}\n`;
  }

  output += `\n【专业技巧】\n`;
  for (const tip of tutorial.pro_tips) {
    output += `  ✨ ${tip}\n`;
  }

  output += `\n` + `─`.repeat(40) + `\n`;
  output += `祝你化出美美的妆容！💕\n`;

  return output;
}

// CLI
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log("用法: bun tutorial_generator.ts <图片路径> [风格]");
    console.log("风格: 日常妆 | 约会妆 | 派对妆");
    console.log("\n示例:");
    console.log("  bun tutorial_generator.ts photo.jpg 日常妆");
    console.log("  bun tutorial_generator.ts photo.jpg 约会妆");
    process.exit(1);
  }

  const imagePath = args[0].replace(/^~/, process.env.HOME || "");
  const style = args[1] || "日常妆";

  if (!existsSync(imagePath)) {
    console.error(`❌ 图片不存在: ${imagePath}`);
    process.exit(1);
  }

  const tutorial = await generateTutorial(imagePath, style);

  if (tutorial) {
    console.log(formatTutorial(tutorial));
  } else {
    console.log("❌ 教程生成失败");
    process.exit(1);
  }
}

if (import.meta.main) {
  main();
}
