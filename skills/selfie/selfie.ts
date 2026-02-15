#!/usr/bin/env bun
/**
 * Selfie Skill - 摄像头拍照
 * 使用 imagesnap 拍照并保存
 */

import { exec } from "child_process";
import { promisify } from "util";
import { existsSync, statSync } from "fs";
import { resolve } from "path";

const execAsync = promisify(exec);

interface SelfieOptions {
  countdown?: number;
  filename?: string;
  outputDir?: string;
  open?: boolean;
}

async function sleep(seconds: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, seconds * 1000));
}

async function takeSelfie(options: SelfieOptions = {}): Promise<string> {
  const countdown = options.countdown ?? 0;
  const filename = options.filename ?? `selfie_${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`;
  const outputDir = options.outputDir ?? process.env.HOME + "/Desktop";
  const outputPath = resolve(outputDir, filename);

  // 倒计时
  if (countdown > 0) {
    console.log(`📸 准备拍照，倒计时 ${countdown} 秒...`);
    for (let i = countdown; i > 0; i--) {
      console.log(`   ${i}...`);
      await sleep(1);
    }
  }

  // 拍照
  console.log("📷 拍照中...");

  try {
    // 使用 imagesnap，-w 1.0 让摄像头预热
    await execAsync(`imagesnap -w 1.0 "${outputPath}"`);

    // 验证文件存在
    if (!existsSync(outputPath)) {
      throw new Error("照片文件未生成");
    }

    const stats = statSync(outputPath);
    const sizeMB = (stats.size / 1024 / 1024).toFixed(2);

    console.log(`✅ 照片已保存`);
    console.log(`   Saved to: ${outputPath}`);
    console.log(`   Size: ${sizeMB} MB`);

    // 如果指定了 --open，自动打开
    if (options.open) {
      await execAsync(`open "${outputPath}"`);
    }

    return outputPath;
  } catch (error: any) {
    if (error.message.includes("imagesnap: command not found")) {
      throw new Error("imagesnap 未安装。请运行: brew install imagesnap");
    }
    throw error;
  }
}

// 解析命令行参数
function parseArgs(): SelfieOptions {
  const args = process.argv.slice(2);
  const options: SelfieOptions = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === "--countdown" && args[i + 1]) {
      options.countdown = parseInt(args[i + 1], 10);
      i++;
    } else if (arg === "--filename" && args[i + 1]) {
      options.filename = args[i + 1];
      i++;
    } else if (arg === "--dir" && args[i + 1]) {
      options.outputDir = args[i + 1];
      i++;
    } else if (arg === "--open") {
      options.open = true;
    } else if (!arg.startsWith("--")) {
      // 第一个非选项参数作为 countdown
      if (options.countdown === undefined && !isNaN(parseInt(arg, 10))) {
        options.countdown = parseInt(arg, 10);
      } else if (options.filename === undefined) {
        options.filename = arg;
      }
    }
  }

  return options;
}

// 主函数
async function main() {
  try {
    const options = parseArgs();
    const photoPath = await takeSelfie(options);
    process.exit(0);
  } catch (error: any) {
    console.error(`❌ 拍照失败: ${error.message}`);
    process.exit(1);
  }
}

main();
