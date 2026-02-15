#!/usr/bin/env bun
/**
 * AI 美妆顾问 - 主入口
 *
 * 功能:
 * 1. 拍照/分析面部特征
 * 2. 结合当前流行趋势
 * 3. 生成个性化化妆建议
 */

import { exec } from "child_process";
import { promisify } from "util";
import { existsSync } from "fs";
import { readFileSync } from "fs";

const execAsync = promisify(exec);

// 当前流行趋势数据
const TREND_DATA = {
  // 2026年春夏流行色
  colors: {
    spring: ["珊瑚粉", "薄荷绿", "奶油黄", "薰衣草紫"],
    summer: ["西瓜红", "椰子白", "海蓝", "日落橙"],
    fall: ["焦糖棕", "酒红", "橄榄绿", "南瓜橘"],
    winter: ["浆果紫", "森林绿", "宝石蓝", "香槟金"]
  },

  // 当前热门妆容
  trending: [
    { name: "清透水光肌", desc: "韩系光泽感，重点在底妆透亮", difficulty: "简单" },
    { name: "泰式轻混血", desc: "野生眉+立体修容，高级感", difficulty: "中等" },
    { name: "千金玛利亚", desc: "精致贵气，红唇+猫眼线", difficulty: "高级" },
    { name: "纯欲白开水", desc: "伪素颜，重点是腮红位置", difficulty: "简单" },
    { name: "复古港风", desc: "90年代港星风，红唇+浓眉", difficulty: "中等" }
  ],

  // 节日妆容
  holidays: {
    "valentine": { name: "情人节", style: "甜美约会妆", colors: ["粉红", "玫瑰金", "蜜桃"] },
    "christmas": { name: "圣诞节", style: "派对闪亮妆", colors: ["红色", "金色", "绿色"] },
    "chinese_new_year": { name: "春节", style: "喜庆红妆", colors: ["正红", "金色", "橙红"] },
    "halloween": { name: "万圣节", style: "创意变装妆", colors: ["黑色", "橙色", "紫色"] },
    "mid_autumn": { name: "中秋节", style: "温婉古典妆", colors: ["月白", "桂金", "玉粉"] }
  }
};

// 获取当前季节
function getCurrentSeason(): string {
  const month = new Date().getMonth() + 1;
  if (month >= 3 && month <= 5) return "spring";
  if (month >= 6 && month <= 8) return "summer";
  if (month >= 9 && month <= 11) return "fall";
  return "winter";
}

// 获取临近节日
function getUpcomingHoliday(): { key: string; name: string; days: number } | null {
  const now = new Date();
  const year = now.getFullYear();

  const holidays = [
    { key: "valentine", date: new Date(year, 1, 14), name: "情人节" },
    { key: "chinese_new_year", date: new Date(year, 0, 29), name: "春节" }, // 2026春节
    { key: "mid_autumn", date: new Date(year, 9, 6), name: "中秋节" }, // 2026中秋
    { key: "halloween", date: new Date(year, 9, 31), name: "万圣节" },
    { key: "christmas", date: new Date(year, 11, 25), name: "圣诞节" }
  ];

  for (const h of holidays) {
    const diff = Math.ceil((h.date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (diff >= 0 && diff <= 30) {
      return { key: h.key, name: h.name, days: diff };
    }
  }
  return null;
}

// 面部分析
async function analyzeFace(imagePath: string): Promise<any> {
  console.log("🔍 分析面部特征...");

  try {
    const { stdout } = await execAsync(
      `python3 ${__dirname}/face_analyzer.py "${imagePath}"`,
      { timeout: 30000 }
    );

    return JSON.parse(stdout);
  } catch (error: any) {
    if (error.message?.includes("未检测到人脸")) {
      console.log("❌ 未检测到人脸，请确保照片中有清晰的正面人脸");
    } else {
      console.error("❌ 分析失败:", error.message);
    }
    return null;
  }
}

// 生成妆容建议
async function generateMakeupAdvice(
  faceAnalysis: any,
  options: { trend?: boolean; holiday?: string }
): Promise<string> {
  const season = getCurrentSeason();
  const upcomingHoliday = getUpcomingHoliday();
  const holiday = options.holiday || upcomingHoliday?.key;

  let advice = "💄 AI美妆顾问建议\n";
  advice += "═".repeat(40) + "\n\n";

  // 1. 面部分析结果
  if (faceAnalysis) {
    advice += "【面部特征】\n";
    advice += `脸型: ${faceAnalysis.face_shape}\n`;
    advice += `眼型: ${faceAnalysis.eyes?.size} ${faceAnalysis.eyes?.shape}\n`;
    advice += `唇型: ${faceAnalysis.lips?.thickness}\n`;
    advice += `肤色: ${faceAnalysis.skin?.tone} (${faceAnalysis.skin?.undertone}调)\n\n`;

    // 基础建议
    advice += "【基础建议】\n";
    for (const tip of (faceAnalysis.style_suggestions || [])) {
      advice += `${tip}\n`;
    }
    advice += "\n";
  }

  // 2. 流行趋势
  if (options.trend) {
    advice += "【当前流行】\n";
    advice += `季节流行色: ${TREND_DATA.colors[season].join("、")}\n`;
    advice += `\n热门妆容:\n`;
    for (const t of TREND_DATA.trending.slice(0, 3)) {
      advice += `  • ${t.name}: ${t.desc} (${t.difficulty})\n`;
    }
    advice += "\n";
  }

  // 3. 节日妆容
  if (holiday && TREND_DATA.holidays[holiday as keyof typeof TREND_DATA.holidays]) {
    const h = TREND_DATA.holidays[holiday as keyof typeof TREND_DATA.holidays];
    advice += `【${h.name}妆容】\n`;
    advice += `推荐风格: ${h.style}\n`;
    advice += `主题色彩: ${h.colors.join("、")}\n\n`;
  }

  // 4. 个性化推荐（如果有面部分析）
  if (faceAnalysis) {
    advice += "【个性化推荐】\n";

    // 根据脸型推荐妆容
    const faceShape = faceAnalysis.face_shape;
    const shapeMakeup: Record<string, string> = {
      "oval": "鹅蛋脸百搭，可尝试清透水光肌或千金玛利亚妆",
      "round": "圆脸适合泰式轻混血，用修容增加立体感",
      "square": "方脸推荐纯欲白开水，用腮红柔化下颌",
      "heart": "心形脸适合复古港风，强调眉眼平衡",
      "oblong": "长脸适合横向晕染的眼妆，缩短面部比例"
    };
    advice += `✨ 推荐妆容: ${shapeMakeup[faceShape] || "根据个人喜好选择"}\n`;

    // 根据肤色推荐
    const skinTone = faceAnalysis.skin?.tone;
    const undertone = faceAnalysis.skin?.undertone;

    const colorRec: Record<string, string> = {
      "fair": "白皮可选珊瑚粉、蜜桃色系",
      "light": "浅皮适合玫瑰金、豆沙色",
      "medium": "中皮推荐大地色、橘棕色",
      "tan": "小麦皮适合砖红、金棕色",
      "deep": "深皮推荐浆果色、深红、金色"
    };
    advice += `🎨 推荐色彩: ${colorRec[skinTone] || "百搭色系"}\n`;

    // 冷暖调建议
    const undertoneRec: Record<string, string> = {
      "warm": "暖皮首选橘色系、珊瑚色、金色",
      "cool": "冷皮首选粉色系、莓果色、银色",
      "neutral": "中性皮百搭，各种色系都能驾驭"
    };
    advice += `💫 色调选择: ${undertoneRec[undertone] || "百搭"}\n`;
  }

  advice += "\n" + "─".repeat(40) + "\n";
  advice += "💡 小贴士: 妆容是个人风格的体现，以上建议仅供参考\n";
  advice += "   最重要的是选择让自己自信的造型！";

  return advice;
}

// 主函数
async function main() {
  const args = process.argv.slice(2);

  // 解析参数
  let imagePath = "";
  let showTrend = false;
  let holidayTheme = "";

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--trend" || args[i] === "-t") {
      showTrend = true;
    } else if (args[i] === "--holiday" || args[i] === "-h") {
      holidayTheme = args[++i] || "";
    } else if (!args[i].startsWith("-")) {
      imagePath = args[i];
    }
  }

  // 如果没有图片路径，只显示趋势
  if (!imagePath) {
    if (showTrend || holidayTheme) {
      // 只看趋势，不需要图片
      const advice = await generateMakeupAdvice(null, {
        trend: showTrend,
        holiday: holidayTheme
      });
      console.log(advice);
      return;
    }

    console.log("📸 请提供照片路径，或使用 /selfie 拍照");
    console.log("");
    console.log("用法:");
    console.log("  bun makeup-advisor.ts <图片路径>");
    console.log("  bun makeup-advisor.ts <图片路径> --trend");
    console.log("  bun makeup-advisor.ts --trend  # 只看趋势");
    process.exit(1);
  }

  // 展开路径
  imagePath = imagePath.replace(/^~/, process.env.HOME || "");

  if (!existsSync(imagePath)) {
    console.error(`❌ 图片不存在: ${imagePath}`);
    process.exit(1);
  }

  // 分析面部
  const faceAnalysis = await analyzeFace(imagePath);

  // 生成建议
  const advice = await generateMakeupAdvice(faceAnalysis, {
    trend: showTrend,
    holiday: holidayTheme
  });

  console.log("\n" + advice);
}

main();
