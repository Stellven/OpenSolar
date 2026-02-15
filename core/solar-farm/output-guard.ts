/**
 * Solar Farm - 输出门卫 (Output Guard)
 *
 * 自动检测+修正机制：输出前自动过一遍人格检测，低分就自动修
 *
 * @version 1.0.0
 * @created 2026-02-07
 * @authors Solar + 监护人智慧
 */

import { detectPersonaConcentration, getPersonaLevel } from './persona-detector';
import { executePersonaRefactoring, quickFix } from './persona-refractor';
import { refineTone } from './tone-refiner';

// ============================================================
// 配置
// ============================================================

/** 门卫配置 */
export interface GuardConfig {
  /** 自动修正阈值，低于此分数自动修正 */
  autoFixThreshold: number;
  /** 警告阈值，低于此分数输出警告 */
  warnThreshold: number;
  /** 是否启用自动修正 */
  autoFix: boolean;
  /** 是否输出诊断信息 */
  verbose: boolean;
}

const DEFAULT_CONFIG: GuardConfig = {
  autoFixThreshold: 40,   // 低于40分自动修
  warnThreshold: 60,      // 低于60分警告
  autoFix: true,
  verbose: false
};

// ============================================================
// 门卫结果
// ============================================================

export interface GuardResult {
  original: string;
  output: string;
  score: number;
  level: string;
  wasFixed: boolean;
  fixMethod: 'none' | 'tone-refine' | 'micro-inject' | 'manual-needed';
  warning?: string;
}

// ============================================================
// 核心门卫函数
// ============================================================

/**
 * 输出门卫 - 检测并自动修正冷冰冰的输出
 *
 * @param text 准备输出的文本
 * @param config 门卫配置
 * @returns 修正后的结果
 */
export function guard(text: string, config: Partial<GuardConfig> = {}): GuardResult {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  // 1. 检测人格浓度
  const detection = detectPersonaConcentration(text);
  const score = detection.personaScore;
  const level = getPersonaLevel(text);

  let output = text;
  let wasFixed = false;
  let fixMethod: GuardResult['fixMethod'] = 'none';
  let warning: string | undefined;

  // 2. 根据分数决定动作
  if (score < cfg.autoFixThreshold && cfg.autoFix) {
    // 严重出戏，需要修正

    // 先尝试 tone-refine（轻量级）
    const toneFixed = refineTone(text, { intensity: 'medium' });
    const toneScore = detectPersonaConcentration(toneFixed).personaScore;

    if (toneScore >= cfg.warnThreshold) {
      // tone-refine 够用了
      output = toneFixed;
      wasFixed = true;
      fixMethod = 'tone-refine';
    } else {
      // tone-refine 不够，试试 micro-inject
      const microFixed = quickFix(toneFixed);
      const microScore = detectPersonaConcentration(microFixed).personaScore;

      if (microScore >= cfg.autoFixThreshold) {
        output = microFixed;
        wasFixed = true;
        fixMethod = 'micro-inject';
      } else {
        // 自动修正不够，需要人工/LLM 介入
        output = microFixed; // 先用能修的
        wasFixed = true;
        fixMethod = 'manual-needed';
        warning = `⚠️ 人格浓度仍然较低(${microScore}分)，建议手动调整或用 LLM 重写`;
      }
    }
  } else if (score < cfg.warnThreshold) {
    // 轻度出戏，输出警告但不强制修正
    warning = `💡 人格浓度偏低(${score}分)，可以更有温度一点哦～`;
  }

  // 3. 输出诊断信息
  if (cfg.verbose) {
    console.error(`[OutputGuard] 原始分数: ${score}, 修正: ${wasFixed ? fixMethod : '无'}`);
  }

  return {
    original: text,
    output,
    score,
    level,
    wasFixed,
    fixMethod,
    warning
  };
}

/**
 * 快速门卫 - 简化版，直接返回修正后的文本
 */
export function quickGuard(text: string): string {
  return guard(text).output;
}

/**
 * 检查门卫 - 只检测不修正，返回是否需要修正
 */
export function checkGuard(text: string): { needsFix: boolean; score: number; level: string } {
  const detection = detectPersonaConcentration(text);
  return {
    needsFix: detection.personaScore < DEFAULT_CONFIG.autoFixThreshold,
    score: detection.personaScore,
    level: getPersonaLevel(text)
  };
}

// ============================================================
// 批量处理
// ============================================================

/**
 * 批量门卫 - 处理多段文本
 */
export function guardBatch(texts: string[], config: Partial<GuardConfig> = {}): GuardResult[] {
  return texts.map(text => guard(text, config));
}

// ============================================================
// 统计
// ============================================================

let guardStats = {
  totalChecks: 0,
  totalFixes: 0,
  fixMethods: {
    'tone-refine': 0,
    'micro-inject': 0,
    'manual-needed': 0
  }
};

/**
 * 带统计的门卫
 */
export function guardWithStats(text: string, config: Partial<GuardConfig> = {}): GuardResult {
  const result = guard(text, config);

  guardStats.totalChecks++;
  if (result.wasFixed) {
    guardStats.totalFixes++;
    if (result.fixMethod !== 'none') {
      guardStats.fixMethods[result.fixMethod]++;
    }
  }

  return result;
}

/**
 * 获取门卫统计
 */
export function getGuardStats() {
  return {
    ...guardStats,
    fixRate: guardStats.totalChecks > 0
      ? (guardStats.totalFixes / guardStats.totalChecks * 100).toFixed(1) + '%'
      : '0%'
  };
}

/**
 * 重置统计
 */
export function resetGuardStats() {
  guardStats = {
    totalChecks: 0,
    totalFixes: 0,
    fixMethods: {
      'tone-refine': 0,
      'micro-inject': 0,
      'manual-needed': 0
    }
  };
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const text = process.argv.slice(2).join(' ') || '完成！数据已更新。';

  console.log('\n🚨 输出门卫测试\n');
  console.log(`输入: "${text}"\n`);

  const result = guard(text, { verbose: true });

  console.log(`\n检测结果:`);
  console.log(`  原始分数: ${result.score}`);
  console.log(`  人格等级: ${result.level}`);
  console.log(`  是否修正: ${result.wasFixed ? '✓ 是' : '✗ 否'}`);
  console.log(`  修正方法: ${result.fixMethod}`);

  if (result.warning) {
    console.log(`\n${result.warning}`);
  }

  if (result.wasFixed) {
    console.log(`\n修正前: "${result.original}"`);
    console.log(`修正后: "${result.output}"`);

    // 验证修正效果
    const afterScore = detectPersonaConcentration(result.output).personaScore;
    console.log(`\n修正后分数: ${afterScore} (提升 ${afterScore - result.score} 分)`);
  }
}

export default {
  guard,
  quickGuard,
  checkGuard,
  guardBatch,
  guardWithStats,
  getGuardStats,
  resetGuardStats
};
