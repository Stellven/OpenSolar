/**
 * MEMRL Intent Hash Generator
 *
 * Phase 2 核心组件
 * 职责: 从用户输入生成稳定的 intent_hash
 *
 * 与 Agentic Q-Learner 的 hash 算法保持一致
 */

interface IntentComponents {
  verbs: string[];     // 动词 (构建/测试/分析...)
  objects: string[];   // 对象 (代码/数据/文档...)
  constraints: string[]; // 约束 (性能/格式/数量...)
}

// 动词映射表 (中文 → 英文标准)
const VERB_MAP: Record<string, string> = {
  '构建': 'build',
  '编译': 'build',
  '开发': 'develop',
  '实现': 'implement',
  '写': 'write',
  '创建': 'create',
  '测试': 'test',
  '验证': 'verify',
  '检查': 'check',
  '分析': 'analyze',
  '优化': 'optimize',
  '改进': 'improve',
  '修复': 'fix',
  '删除': 'delete',
  '更新': 'update',
  '读取': 'read',
  '查询': 'query',
  '搜索': 'search',
  '发送': 'send',
  '部署': 'deploy',
  '运行': 'run',
  '执行': 'execute'
};

// 对象映射表
const OBJECT_MAP: Record<string, string> = {
  '项目': 'project',
  '代码': 'code',
  '文件': 'file',
  '数据': 'data',
  '文档': 'doc',
  '测试': 'test',
  '邮件': 'email',
  '任务': 'task',
  '配置': 'config',
  '日志': 'log',
  '系统': 'system',
  '接口': 'api',
  '数据库': 'db',
  '缓存': 'cache',
  '队列': 'queue'
};

// 约束关键词
const CONSTRAINT_KEYWORDS = [
  '性能', '速度', '内存', 'cpu', '并发',
  '安全', '加密', '认证',
  '格式', 'json', 'xml', 'yaml',
  '数量', 'top', 'limit', 'all', '全部'
];

export class IntentHashGenerator {
  /**
   * 从用户输入生成 intent_hash
   *
   * 算法: 提取关键词 → 排序 → hash
   */
  generate(input: string): string {
    const components = this.extractComponents(input);
    const keywords = this.normalizeComponents(components);

    if (keywords.length === 0) {
      // 回退: 使用 Agentic Q-Learner 的算法
      return this.fallbackHash(input);
    }

    // 排序确保稳定性
    keywords.sort();

    // 生成 hash
    const keyString = keywords.join('_');
    let hash = 0;
    for (let i = 0; i < keyString.length; i++) {
      const char = keyString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }

    return `intent_${Math.abs(hash).toString(16)}`;
  }

  /**
   * 提取意图组件
   */
  extractComponents(input: string): IntentComponents {
    const lowerInput = input.toLowerCase();

    // 提取动词
    const verbs: string[] = [];
    for (const [cn, en] of Object.entries(VERB_MAP)) {
      if (input.includes(cn) || lowerInput.includes(en)) {
        verbs.push(en);
      }
    }

    // 提取对象
    const objects: string[] = [];
    for (const [cn, en] of Object.entries(OBJECT_MAP)) {
      if (input.includes(cn) || lowerInput.includes(en)) {
        objects.push(en);
      }
    }

    // 提取约束
    const constraints: string[] = [];
    for (const kw of CONSTRAINT_KEYWORDS) {
      if (lowerInput.includes(kw)) {
        constraints.push(kw);
      }
    }

    return { verbs, objects, constraints };
  }

  /**
   * 标准化组件为关键词
   */
  private normalizeComponents(components: IntentComponents): string[] {
    const keywords: string[] = [];

    // 只取第一个动词 (主要动作)
    if (components.verbs.length > 0) {
      keywords.push(components.verbs[0]);
    }

    // 取前两个对象
    keywords.push(...components.objects.slice(0, 2));

    // 取第一个约束
    if (components.constraints.length > 0) {
      keywords.push(components.constraints[0]);
    }

    return keywords;
  }

  /**
   * 回退 hash (与 Agentic Q-Learner 一致)
   */
  private fallbackHash(input: string): string {
    const keywords = input.toLowerCase()
      .replace(/[^\w\s]/g, ' ')
      .split(/\s+/)
      .filter(w => w.length > 2)
      .slice(0, 5)
      .sort()
      .join('_');

    let hash = 0;
    for (let i = 0; i < keywords.length; i++) {
      const char = keywords.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }

    return `intent_${Math.abs(hash).toString(16)}`;
  }

  /**
   * 提取关键词 (用于显示)
   */
  extractKeywords(input: string): string[] {
    const components = this.extractComponents(input);
    return this.normalizeComponents(components);
  }

  /**
   * 计算两个 hash 的相似度
   *
   * 基于前缀匹配
   */
  similarity(hash1: string, hash2: string): number {
    if (hash1 === hash2) return 1.0;

    // 提取数字部分
    const num1 = hash1.replace('intent_', '');
    const num2 = hash2.replace('intent_', '');

    // 前缀匹配
    const minLen = Math.min(num1.length, num2.length);
    let matchCount = 0;
    for (let i = 0; i < minLen; i++) {
      if (num1[i] === num2[i]) {
        matchCount++;
      }
    }

    return matchCount / Math.max(num1.length, num2.length);
  }

  /**
   * 从多个输入生成统一的 hash
   */
  generateFromMultiple(inputs: string[]): string {
    const allKeywords = new Set<string>();

    for (const input of inputs) {
      const keywords = this.extractKeywords(input);
      keywords.forEach(k => allKeywords.add(k));
    }

    const sortedKeywords = Array.from(allKeywords).sort();
    const keyString = sortedKeywords.join('_');

    let hash = 0;
    for (let i = 0; i < keyString.length; i++) {
      const char = keyString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }

    return `intent_${Math.abs(hash).toString(16)}`;
  }
}

// CLI 入口
if (import.meta.main) {
  const generator = new IntentHashGenerator();

  const command = process.argv[2] || 'test';
  const input = process.argv.slice(3).join(' ') || '构建项目';

  if (command === 'test') {
    console.log('🧪 Intent Hash Generator 测试\n');

    const testCases = [
      '构建项目',
      '测试代码',
      '分析性能',
      '优化查询速度',
      '修复登录bug',
      'search for email',
      'deploy to production'
    ];

    for (const test of testCases) {
      const hash = generator.generate(test);
      const keywords = generator.extractKeywords(test);
      console.log(`"${test}"`);
      console.log(`  → hash: ${hash}`);
      console.log(`  → keywords: ${keywords.join(', ')}`);
      console.log();
    }
  }

  if (command === 'hash') {
    const hash = generator.generate(input);
    const keywords = generator.extractKeywords(input);
    console.log(`输入: "${input}"`);
    console.log(`Hash: ${hash}`);
    console.log(`关键词: ${keywords.join(', ')}`);
  }

  if (command === 'similarity') {
    const hash1 = process.argv[3] || 'intent_abc';
    const hash2 = process.argv[4] || 'intent_abd';
    const sim = generator.similarity(hash1, hash2);
    console.log(`相似度: ${sim.toFixed(2)}`);
  }
}
