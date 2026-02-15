#!/usr/bin/env bun
/**
 * AI 美妆顾问 - 统一入口
 *
 * 功能:
 * 1. /makeup-advisor --trend         查看流行趋势
 * 2. /makeup-advisor photo.jpg       分析面部 + 建议
 * 3. /makeup-advisor photo.jpg --tutorial 生成教程
 * 4. /makeup-advisor photo.jpg --try sweet AR试妆
 */

import { exec } from "child_process";
import { promisify } from "util";
import { existsSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const execAsync = promisify(exec);

const HELP = `
💄 AI 美妆顾问

用法:
  /makeup-advisor --trend              查看流行趋势
  /makeup-advisor <照片>               分析面部特征
  /makeup-advisor <照片> --tutorial    生成化妆教程
  /makeup-advisor <照片> --try <风格>  AR虚拟试妆

风格选项:
  natural  - 裸妆
  sweet    - 甜美妆
  cool     - 冷酷妆
  party    - 派对妆

示例:
  /makeup-advisor --trend
  /makeup-advisor photo.jpg --tutorial
  /makeup-advisor photo.jpg --try sweet
`;

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    console.log(HELP);
    return;
  }

  const scriptDir = __dirname;

  // 解析参数
  let imagePath = "";
  let showTrend = false;
  let generateTutorial = false;
  let tryMakeup = "";
  let tutorialStyle = "日常妆";

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--trend" || arg === "-t") {
      showTrend = true;
    } else if (arg === "--tutorial") {
      generateTutorial = true;
      if (i + 1 < args.length && !args[i + 1].startsWith("-")) {
        tutorialStyle = args[++i];
      }
    } else if (arg === "--try") {
      tryMakeup = args[++i] || "natural";
    } else if (!arg.startsWith("-")) {
      imagePath = arg;
    }
  }

  // 1. 只看趋势
  if (showTrend && !imagePath) {
    await execAsync(`bun ${scriptDir}/makeup-advisor.ts --trend`);
    return;
  }

  // 2. 需要照片
  if (!imagePath) {
    console.log("📸 请提供照片路径");
    console.log(HELP);
    return;
  }

  imagePath = imagePath.replace(/^~/, process.env.HOME || "");

  if (!existsSync(imagePath)) {
    console.error(`❌ 照片不存在: ${imagePath}`);
    return;
  }

  // 3. 生成教程
  if (generateTutorial) {
    await execAsync(
      `bun ${scriptDir}/tutorial_generator.ts "${imagePath}" "${tutorialStyle}"`
    );
    return;
  }

  // 4. AR试妆
  if (tryMakeup) {
    const outputPath = join(tmpdir(), "makeup_result.jpg");
    console.log(`🎨 应用 ${tryMakeup} 妆容...`);

    try {
      await execAsync(
        `python3 ${scriptDir}/ar_makeup.py "${imagePath}" ${tryMakeup} "${outputPath}"`,
        { timeout: 30000 }
      );
      console.log(`✅ 试妆完成: ${outputPath}`);
      console.log("   用 'open " + outputPath + "' 查看");
    } catch (error: any) {
      console.log("❌ 试妆失败:", error.message);
    }
    return;
  }

  // 5. 默认：分析面部 + 建议
  await execAsync(`bun ${scriptDir}/makeup-advisor.ts "${imagePath}" --trend`);
}

main();
