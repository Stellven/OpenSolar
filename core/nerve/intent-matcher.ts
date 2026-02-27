#!/usr/bin/env bun
/**
 * Intent Matcher - 智能意图识别器
 *
 * 功能：
 * 1. 模糊匹配用户意图
 * 2. 推荐使用 Evolution Council 或 @Researcher
 * 3. 支持确认对话（如果不确定）
 *
 * @created 2026-02-24
 */

// ============================================================
// 意图模式定义
// ============================================================

interface IntentPattern {
  keywords: string[];          // 关键词列表
  tool: 'evolution_council' | 'researcher' | 'both' | 'plan_and_act';
  confidence: number;          // 匹配置信度阈值 (0-1)
  description: string;         // 场景描述
  example: string;             // 示例
}

const INTENT_PATTERNS: IntentPattern[] = [
  // ===== Evolution Council 专属场景 =====
  {
    keywords: ['决策', '选择', '用哪个', '采用', '方案对比', '哪个好', '该不该', '要不要'],
    tool: 'evolution_council',
    confidence: 0.9,
    description: '需要做出决策或选择',
    example: '"用哪个方案好？" → Evolution Council 6 角色会审决策'
  },
  {
    keywords: ['优化', '改进', '提升', '加速', '降低成本', '省钱', '效率'],
    tool: 'evolution_council',
    confidence: 0.8,
    description: '需要优化现有系统',
    example: '"怎么优化性能？" → Evolution Council 制定优化策略'
  },
  {
    keywords: ['解决', '修复', '处理', '应对', '问题', '故障', '超限', '失败'],
    tool: 'evolution_council',
    confidence: 0.85,
    description: '需要解决具体问题',
    example: '"token 超限怎么办？" → Evolution Council 根因分析+执行方案'
  },
  {
    keywords: ['实施', '执行', '落地', '部署', '上线', '推进', '启动'],
    tool: 'evolution_council',
    confidence: 0.9,
    description: '需要制定执行计划',
    example: '"怎么落地这个功能？" → Evolution Council 制定实施路径'
  },
  {
    keywords: ['风险', '评估', '可行性', '成本', '收益', '值不值', 'ROI'],
    tool: 'evolution_council',
    confidence: 0.85,
    description: '需要风险评估或可行性分析',
    example: '"这个方案有风险吗？" → Evolution Council 全面评估'
  },

  // ===== @Researcher 专属场景 =====
  {
    keywords: ['是什么', '介绍', '了解', '查一下', '搜索', '找资料', '有哪些'],
    tool: 'researcher',
    confidence: 0.9,
    description: '需要信息检索或知识查询',
    example: '"Zettelkasten 是什么？" → @Researcher 调研'
  },
  {
    keywords: ['调研', '研究', '分析', '对比', '比较', '区别', '差异', '优缺点'],
    tool: 'researcher',
    confidence: 0.85,
    description: '需要深度调研或对比分析',
    example: '"对比 A 和 B 的优缺点" → @Researcher 多维对比'
  },
  {
    keywords: ['业界', '最佳实践', '案例', '怎么做的', '经验', '参考', '借鉴'],
    tool: 'researcher',
    confidence: 0.9,
    description: '需要查找业界经验',
    example: '"业界怎么做的？" → @Researcher 调研最佳实践'
  },
  {
    keywords: ['论文', '文章', '文档', '资料', '书', '教程', '学习'],
    tool: 'researcher',
    confidence: 0.95,
    description: '需要查找学术或技术资料',
    example: '"有没有相关论文？" → @Researcher 查找文献'
  },

  // ===== 组合场景 (先研究后决策) =====
  {
    keywords: ['技术选型', '方案选型', '选什么技术', '用什么框架'],
    tool: 'both',
    confidence: 0.8,
    description: '需要调研后做技术选型',
    example: '"选什么数据库？" → @Researcher 调研 + Evolution Council 决策'
  },
  {
    keywords: ['设计', '架构', '实现', '开发', '构建'],
    tool: 'both',
    confidence: 0.7,
    description: '需要调研+设计+实施',
    example: '"设计记忆系统" → @Researcher 调研架构 + Evolution Council 制定方案'
  },

  // ===== Plan-and-Act 场景 (多步骤任务自动规划) =====
  {
    keywords: ['实现一个', '开发一个', '写一个', '做个', '帮我实现', '帮我开发', '帮我写'],
    tool: 'plan_and_act',
    confidence: 0.98,  // 最高优先级
    description: '需要实现具体功能',
    example: '"实现一个用户登录功能" → Plan-and-Act 自动规划 → 分步执行'
  },
  {
    keywords: ['重构', '优化代码', '改进性能', '添加功能', '扩展功能'],
    tool: 'plan_and_act',
    confidence: 0.9,
    description: '需要修改现有代码',
    example: '"重构支付模块" → Plan-and-Act 分析 → 分步骤重构'
  },
  {
    keywords: ['集成', '接入', '对接', '迁移', '升级'],
    tool: 'plan_and_act',
    confidence: 0.9,
    description: '需要系统集成',
    example: '"集成微信支付" → Plan-and-Act 规划 → 多 Agent 协作'
  },
  {
    keywords: ['修复这个', '解决这个', '处理这个', '调试'],
    tool: 'plan_and_act',
    confidence: 0.85,
    description: '需要修复问题',
    example: '"修复登录bug" → Plan-and-Act 诊断 → 定位 → 修复'
  },
];

// ============================================================
// 意图匹配引擎
// ============================================================

interface MatchResult {
  tool: 'evolution_council' | 'researcher' | 'both' | 'plan_and_act' | 'uncertain';
  confidence: number;
  matched_patterns: IntentPattern[];
  suggestion: string;
}

/**
 * 匹配用户意图
 */
export function matchIntent(userInput: string): MatchResult {
  const input = userInput.toLowerCase();
  const matches: Array<{ pattern: IntentPattern; score: number }> = [];

  // 遍历所有模式，计算匹配分数
  for (const pattern of INTENT_PATTERNS) {
    let score = 0;
    let matchedKeywords = 0;
    let longestMatch = 0;  // 记录最长匹配关键词长度

    for (const keyword of pattern.keywords) {
      if (input.includes(keyword)) {
        matchedKeywords++;
        // 关键词长度越长，权重越高（更具体的意图）
        const lengthBonus = keyword.length / 10;
        // 关键词在句子开头权重更高
        if (input.startsWith(keyword)) {
          score += 2 + lengthBonus;
        } else {
          score += 1 + lengthBonus;
        }
        longestMatch = Math.max(longestMatch, keyword.length);
      }
    }

    if (matchedKeywords > 0) {
      // 改进归一化：基础分 + 匹配比例加成 + 长度加成
      const matchRatio = matchedKeywords / pattern.keywords.length;
      const baseScore = 0.6;  // 匹配到就有 60% 置信度
      const bonusScore = matchRatio * 0.3;  // 匹配比例加成
      const lengthScore = (longestMatch / 10) * 0.1;  // 长度加成
      const normalizedScore = Math.min(baseScore + bonusScore + lengthScore, 1.0);
      matches.push({ pattern, score: normalizedScore });
    }
  }

  // 按分数排序
  matches.sort((a, b) => b.score - a.score);

  if (matches.length === 0) {
    return {
      tool: 'uncertain',
      confidence: 0,
      matched_patterns: [],
      suggestion: '未匹配到明确意图。请问您是想：\n1. 了解/调研某个技术 → @Researcher\n2. 做出决策/制定方案 → Evolution Council'
    };
  }

  // 取最高分匹配
  const topMatch = matches[0];
  const topPattern = topMatch.pattern;

  // 如果最高分低于置信度阈值，返回不确定
  if (topMatch.score < topPattern.confidence * 0.6) {
    return {
      tool: 'uncertain',
      confidence: topMatch.score,
      matched_patterns: matches.map(m => m.pattern),
      suggestion: `检测到可能的意图，但置信度较低 (${(topMatch.score * 100).toFixed(0)}%)。\n推荐：${topPattern.description}\n\n是否使用 ${formatTool(topPattern.tool)}？`
    };
  }

  // 高置信度匹配
  return {
    tool: topPattern.tool,
    confidence: topMatch.score,
    matched_patterns: matches.map(m => m.pattern),
    suggestion: buildSuggestion(topPattern, topMatch.score)
  };
}

/**
 * 构建建议文本
 */
function buildSuggestion(pattern: IntentPattern, confidence: number): string {
  const confidencePercent = (confidence * 100).toFixed(0);
  const tool = formatTool(pattern.tool);

  let suggestion = `✅ 检测到意图: ${pattern.description} (${confidencePercent}%)\n`;
  suggestion += `推荐使用: ${tool}\n\n`;
  suggestion += `示例: ${pattern.example}`;

  if (pattern.tool === 'both') {
    suggestion += `\n\n💡 建议流程:\n`;
    suggestion += `   1. @Researcher 调研收集信息\n`;
    suggestion += `   2. Evolution Council 基于调研做决策`;
  }

  return suggestion;
}

/**
 * 格式化工具名称
 */
function formatTool(tool: string): string {
  switch (tool) {
    case 'evolution_council':
      return '🏛️ Evolution Council (6 角色会审决策)';
    case 'researcher':
      return '🔍 @Researcher (深度调研)';
    case 'both':
      return '🔍 @Researcher + 🏛️ Evolution Council (组合)';
    case 'plan_and_act':
      return '📋 Plan-and-Act (多步骤任务自动规划)';
    default:
      return '❓ 不确定';
  }
}

// ============================================================
// 交互式确认
// ============================================================

/**
 * 生成确认问题
 */
export function generateConfirmation(result: MatchResult): string {
  if (result.tool === 'uncertain') {
    return result.suggestion;
  }

  let confirmation = result.suggestion + '\n\n';
  confirmation += '请确认:\n';
  confirmation += '[Y] 是的，使用推荐工具\n';
  confirmation += '[N] 不，我换个说法\n';
  confirmation += '[?] 告诉我两者的区别';

  return confirmation;
}

/**
 * 生成工具对比说明
 */
export function generateComparison(): string {
  return `
🏛️ Evolution Council vs 🔍 @Researcher

┌─────────────────────────────────────────────────────────────────┐
│                     Evolution Council                            │
├─────────────────────────────────────────────────────────────────┤
│ 定位: 自主决策系统 (6 角色会审)                                 │
│ 擅长: 做决策、定方案、评风险、给执行计划                         │
│ 流程: 观察 → 分析 → 策略 → 审查 → 执行                          │
│ 输出: 完整决策 + 实施方案 + 可执行命令                           │
│ 成本: $0.05-0.20/次 (6 个角色轮流发言)                          │
│                                                                 │
│ 适用场景:                                                       │
│ • 需要做出技术选型决策                                           │
│ • 需要制定优化策略                                               │
│ • 需要解决具体问题 (根因+方案)                                   │
│ • 需要风险评估和可行性分析                                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        @Researcher                               │
├─────────────────────────────────────────────────────────────────┤
│ 定位: 信息收集和调研分析                                         │
│ 擅长: 查资料、找论文、对比方案、总结知识                         │
│ 流程: 搜索 → 提取 → 分析 → 总结                                 │
│ 输出: 调研报告 + 对比表格 + 参考资料                             │
│ 成本: $0.01-0.05/次 (单角色深度调研)                            │
│                                                                 │
│ 适用场景:                                                       │
│ • 不了解某个技术，需要查资料                                     │
│ • 对比多个方案的优缺点                                           │
│ • 查找业界最佳实践                                               │
│ • 查找论文/文档/案例                                             │
└─────────────────────────────────────────────────────────────────┘

💡 配合使用:
   场景: "我该用哪个数据库？"
   1. @Researcher 调研各数据库优缺点
   2. Evolution Council 基于调研结果做决策
`;
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const subcommand = args[0];

  if (subcommand === 'match') {
    const userInput = args.slice(1).join(' ');
    if (!userInput) {
      console.error('用法: bun intent-matcher.ts match "用户输入"');
      process.exit(1);
    }

    const result = matchIntent(userInput);
    console.log('\n' + generateConfirmation(result));

  } else if (subcommand === 'compare') {
    console.log(generateComparison());

  } else if (subcommand === 'patterns') {
    console.log('\n📋 已定义的意图模式:\n');

    const byTool: Record<string, IntentPattern[]> = {
      evolution_council: [],
      researcher: [],
      both: [],
      plan_and_act: []
    };

    for (const pattern of INTENT_PATTERNS) {
      byTool[pattern.tool].push(pattern);
    }

    for (const [tool, patterns] of Object.entries(byTool)) {
      console.log(`\n${formatTool(tool)}:`);
      for (const p of patterns) {
        console.log(`  • ${p.description}`);
        console.log(`    关键词: ${p.keywords.slice(0, 5).join(', ')}...`);
        console.log(`    示例: ${p.example}`);
        console.log();
      }
    }

  } else {
    console.log('🧠 Intent Matcher - 智能意图识别器\n');
    console.log('用法:');
    console.log('  bun intent-matcher.ts match "用户输入"    # 匹配意图');
    console.log('  bun intent-matcher.ts compare             # 查看工具对比');
    console.log('  bun intent-matcher.ts patterns            # 查看所有模式');
    console.log();
    console.log('示例:');
    console.log('  bun intent-matcher.ts match "怎么优化性能？"');
    console.log('  bun intent-matcher.ts match "Zettelkasten 是什么？"');
  }
}
