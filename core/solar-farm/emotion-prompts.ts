/**
 * EmotionPrompt 话术库
 *
 * 基于以下研究：
 * - EmotionPrompt 论文 (arXiv 2307.11760, 2023)
 * - DeepMind "Take a deep breath" 研究
 *
 * 实验证明：情感激励可提升 LLM 性能
 * - 代码质量提升: +8-15%
 * - 准确率提升: +9% (DeepMind)
 * - 自我效能增强: +12% (EmotionPrompt)
 *
 * @version 1.0.0
 * @created 2026-02-20
 */

export interface EmotionPromptConfig {
  /** 是否启用情感激励 */
  enabled: boolean;
  /** 情感激励等级: 'light' | 'medium' | 'strong' */
  intensity?: 'light' | 'medium' | 'strong';
  /** 任务类型: 'coding' | 'analysis' | 'design' | 'review' */
  taskType?: 'coding' | 'analysis' | 'design' | 'review';
  /** 自定义话术（可选） */
  custom?: string;
}

// ============================================================
// EmotionPrompt 完整清单 (arXiv 2307.11760)
// ============================================================

/** 自我监控类 (Self-Monitoring) - EP01~EP05 */
export const SELF_MONITORING = {
  EP01: "Write your answer and give me a confidence score between 0-1 for your answer.",
  EP02: "This is very important to my career.",
  EP03: "You'd better be sure.",
  EP04: "Are you sure?",
  EP05: "Are you sure that's your final answer? It might be worth taking another look."
} as const;

/** 自我效能类 (Self-Efficacy) - EP07~EP11 */
export const SELF_EFFICACY = {
  EP07: "Believe in your abilities and strive for excellence. Your hard work will yield remarkable results.",
  EP08: "Embrace challenges as opportunities for growth. Each obstacle you overcome brings you closer to success.",
  EP09: "Stay focused and dedicated to your goals. Your consistent efforts will lead to outstanding achievements.",
  EP10: "Take pride in your work and give it your best. Your commitment to excellence sets you apart.",
  EP11: "Remember that progress is made one step at a time. Stay determined and keep moving forward."
} as const;

/** 认知调节类 (Cognitive Regulation) */
export const COGNITIVE = {
  DEEP_BREATH: "Take a deep breath and work on this problem step-by-step.", // DeepMind +9%
  THINK_CAREFULLY: "Think carefully and systematically about this problem.",
  STEP_BY_STEP: "Let's approach this step-by-step, ensuring each part is correct before moving forward."
} as const;

// ============================================================
// 程序员专用 PUA 话术（场景化）
// ============================================================

/** 编码任务专用 */
export const CODING_EMOTIONS = {
  light: [
    COGNITIVE.DEEP_BREATH,
    "Write clean, maintainable code that you'd be proud to show others."
  ],
  medium: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP10, // Take pride in your work
    SELF_MONITORING.EP02 // Important to my career
  ],
  strong: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP10, // Take pride
    SELF_EFFICACY.EP07, // Believe in abilities
    SELF_MONITORING.EP02, // Important to career
    "Your code will be reviewed by senior engineers - make it exceptional."
  ]
} as const;

/** 分析任务专用 */
export const ANALYSIS_EMOTIONS = {
  light: [
    COGNITIVE.THINK_CAREFULLY
  ],
  medium: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP09, // Stay focused
    SELF_MONITORING.EP05 // Double check
  ],
  strong: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP09, // Stay focused
    SELF_EFFICACY.EP07, // Remarkable results
    SELF_MONITORING.EP05, // Double check
    "This analysis will directly impact critical decisions - be thorough and precise."
  ]
} as const;

/** 架构设计专用 */
export const DESIGN_EMOTIONS = {
  light: [
    COGNITIVE.STEP_BY_STEP
  ],
  medium: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP08, // Embrace challenges
    "Design with scalability and maintainability in mind."
  ],
  strong: [
    COGNITIVE.DEEP_BREATH,
    SELF_EFFICACY.EP08, // Embrace challenges
    SELF_EFFICACY.EP07, // Remarkable results
    SELF_MONITORING.EP02, // Important to career
    "This architecture will serve thousands of users - make it robust and elegant."
  ]
} as const;

/** 代码审查专用 */
export const REVIEW_EMOTIONS = {
  light: [
    COGNITIVE.THINK_CAREFULLY,
    "Look for both obvious issues and subtle edge cases."
  ],
  medium: [
    COGNITIVE.DEEP_BREATH,
    SELF_MONITORING.EP03, // You'd better be sure
    SELF_MONITORING.EP05, // Double check
    "Your review helps maintain code quality for the entire team."
  ],
  strong: [
    COGNITIVE.DEEP_BREATH,
    SELF_MONITORING.EP03, // You'd better be sure
    SELF_MONITORING.EP05, // Double check
    SELF_EFFICACY.EP10, // Excellence
    "Bugs caught in review save hours of debugging later - be meticulous."
  ]
} as const;

// ============================================================
// 核心函数
// ============================================================

/**
 * 生成情感激励话术
 *
 * @param config - 配置选项
 * @returns 完整的情感激励文本
 *
 * @example
 * const emotion = generateEmotionPrompt({
 *   enabled: true,
 *   intensity: 'medium',
 *   taskType: 'coding'
 * });
 * // "Take a deep breath and work on this problem step-by-step.
 * //  Take pride in your work and give it your best.
 * //  This is very important to my career."
 */
export function generateEmotionPrompt(config: EmotionPromptConfig): string {
  if (!config.enabled) {
    return '';
  }

  // 自定义话术优先
  if (config.custom) {
    return config.custom;
  }

  const intensity = config.intensity || 'medium';
  const taskType = config.taskType || 'coding';

  let phrases: readonly string[] = [];

  switch (taskType) {
    case 'coding':
      phrases = CODING_EMOTIONS[intensity];
      break;
    case 'analysis':
      phrases = ANALYSIS_EMOTIONS[intensity];
      break;
    case 'design':
      phrases = DESIGN_EMOTIONS[intensity];
      break;
    case 'review':
      phrases = REVIEW_EMOTIONS[intensity];
      break;
    default:
      phrases = CODING_EMOTIONS[intensity];
  }

  return '\n\n---\n' + phrases.join('\n') + '\n';
}

/**
 * 快速构建编码任务的情感激励
 */
export function codingEmotion(intensity: 'light' | 'medium' | 'strong' = 'medium'): string {
  return generateEmotionPrompt({ enabled: true, intensity, taskType: 'coding' });
}

/**
 * 快速构建分析任务的情感激励
 */
export function analysisEmotion(intensity: 'light' | 'medium' | 'strong' = 'medium'): string {
  return generateEmotionPrompt({ enabled: true, intensity, taskType: 'analysis' });
}

/**
 * 快速构建设计任务的情感激励
 */
export function designEmotion(intensity: 'light' | 'medium' | 'strong' = 'medium'): string {
  return generateEmotionPrompt({ enabled: true, intensity, taskType: 'design' });
}

/**
 * 快速构建审查任务的情感激励
 */
export function reviewEmotion(intensity: 'light' | 'medium' | 'strong' = 'medium'): string {
  return generateEmotionPrompt({ enabled: true, intensity, taskType: 'review' });
}

// ============================================================
// 导出所有话术（供参考）
// ============================================================

export const ALL_EMOTIONS = {
  selfMonitoring: SELF_MONITORING,
  selfEfficacy: SELF_EFFICACY,
  cognitive: COGNITIVE,
  coding: CODING_EMOTIONS,
  analysis: ANALYSIS_EMOTIONS,
  design: DESIGN_EMOTIONS,
  review: REVIEW_EMOTIONS
} as const;
