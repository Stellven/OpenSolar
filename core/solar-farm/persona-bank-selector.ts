/**
 * PersonaSelector - 人格选择器
 *
 * 创意点：
 * 1. 引入"人格化学"概念 - 不同特质组合产生化学反应
 * 2. 使用"特质向量"进行多维匹配
 * 3. 实现"新手孵化器"机制，给新人格成长机会
 * 4. 加入"人格多样性指数"计算
 */

import { Database } from 'bun:sqlite';

// ==================== 类型定义 ====================

export type PhaseType = 'collect' | 'fill_gaps' | 'peer_review' | 'compose';

export interface BigFiveTraits {
  /** 开放性 (Openness) - 创新思维 */
  O: number;
  /** 尽责性 (Conscientiousness) - 严谨细致 */
  C: number;
  /** 外向性 (Extraversion) - 表达沟通 */
  E: number;
  /** 宜人性 (Agreeableness) - 合作协调 */
  A: number;
  /** 神经质 (Neuroticism) - 情绪稳定 */
  N: number;
}

export interface PersonaConfig {
  persona_id: string;
  model: string;
  role: string;
  big_five_json: string;
  behavioral_guidelines?: string;
  language_style?: string;
  created_at?: string;
  elo_rating?: number;
  total_matches?: number;
  win_rate?: number;
  avg_score?: number;
}

export interface PhaseTraitMapping {
  /** 主要特质权重 */
  primary: keyof BigFiveTraits;
  /** 次要特质权重 (避免单一维度选择) */
  secondary?: keyof BigFiveTraits;
  /** 特质组合描述 */
  chemistry: string;
}

// ==================== 核心类 ====================

export class PersonaSelector {
  private db: Database;

  /** 阶段-特质映射表 - 加入化学描述让选择更有趣 */
  private readonly PHASE_TRAIT_MAP: Record<PhaseType, PhaseTraitMapping> = {
    collect: {
      primary: 'O',
      secondary: 'E',  // 开放性需要外向性来传播想法
      chemistry: '创意扩散型 - 开放思维+表达力，让想法流动起来'
    },
    fill_gaps: {
      primary: 'C',
      secondary: 'A',  // 尽责性需要宜人性来协作补全
      chemistry: '细节工匠型 - 严谨细致+合作精神，完美补全每个细节'
    },
    peer_review: {
      primary: 'A',
      secondary: 'C',  // 宜人性需要尽责性来提供建设性反馈
      chemistry: '和谐评审型 - 客观公正+严谨态度，提供有价值的反馈'
    },
    compose: {
      primary: 'E',
      secondary: 'O',  // 外向性需要开放性来创造独特表达
      chemistry: '表达艺术家型 - 生动表达+创新思维，让内容活起来'
    }
  };

  /** 新手保护概率 */
  private readonly NEWBIE_PROBABILITY = 0.1;

  /** 最大同模型数量 (避免单一化) */
  private readonly MAX_SAME_MODEL = 2;

  constructor(dbPath: string = `${process.env.HOME}/.solar/solar.db`) {
    this.db = new Database(dbPath);
  }

  /**
   * 根据阶段选择最优人格配置
   *
   * 创新算法：多维特质匹配 + 化学组合优化
   *
   * @param phase 任务阶段
   * @param count 需要的人格数量
   * @returns 优化后的人格配置数组
   */
  async selectForPhase(phase: PhaseType, count: number): Promise<PersonaConfig[]> {
    console.log(`🎭 开始为阶段 "${phase}" 选择 ${count} 个人格...`);

    // 1. 获取所有可用人格
    const allPersonas = this.fetchAllPersonas();

    if (allPersonas.length === 0) {
      throw new Error('人格库为空，请先初始化人格配置');
    }

    // 2. 计算每个人格的阶段适配分数
    const scoredPersonas = this.scorePersonasForPhase(allPersonas, phase);

    // 3. 应用新手保护机制
    const withNewbieBoost = this.applyNewbieProtection(scoredPersonas);

    // 4. 多样性优化选择
    const selected = this.selectWithDiversity(withNewbieBoost, count);

    // 5. 输出选择报告
    this.printSelectionReport(selected, phase);

    return selected;
  }

  /**
   * 从数据库获取所有人格配置
   *
   * 创意点：同时获取ELO排名和使用统计，实现智能加权
   */
  private fetchAllPersonas(): PersonaConfig[] {
    const query = `
      SELECT
        c.persona_id,
        c.model,
        c.role,
        c.big_five_json,
        c.behavioral_guidelines,
        c.language_style,
        c.created_at,
        COALESCE(e.elo_rating, 1500.0) as elo_rating,
        COALESCE(e.total_matches, 0) as total_matches,
        COALESCE(e.win_rate, 0.0) as win_rate,
        COALESCE(e.avg_score, 0.0) as avg_score
      FROM sys_persona_configs c
      LEFT JOIN sys_persona_elo e ON c.persona_id = e.persona_id
      WHERE c.status = 'active'
      ORDER BY e.elo_rating DESC
    `;

    return this.db.query(query).all() as PersonaConfig[];
  }

  /**
   * 解析BigFive JSON数据
   *
   * 创意点：加入数据验证和默认值处理
   */
  private parseBigFiveJson(jsonStr: string): BigFiveTraits {
    try {
      const data = JSON.parse(jsonStr);

      // 验证并确保所有特质都有值
      const traits: BigFiveTraits = {
        O: this.normalizeTrait(data.O),
        C: this.normalizeTrait(data.C),
        E: this.normalizeTrait(data.E),
        A: this.normalizeTrait(data.A),
        N: this.normalizeTrait(data.N)
      };

      return traits;
    } catch (error) {
      console.warn(`⚠️ 解析BigFive JSON失败，使用默认值: ${error}`);

      // 返回平衡的默认值
      return { O: 0.5, C: 0.5, E: 0.5, A: 0.5, N: 0.5 };
    }
  }

  /**
   * 标准化特质值到0-1范围
   */
  private normalizeTrait(value: any): number {
    const num = Number(value);
    if (isNaN(num)) return 0.5;
    return Math.max(0, Math.min(1, num));
  }

  /**
   * 计算人格的阶段适配分数
   *
   * 创新算法：特质向量点积 + ELO加权 + 使用频率衰减
   *
   * @param personas 所有人格
   * @param phase 当前阶段
   * @returns 带分数的人格数组
   */
  private scorePersonasForPhase(
    personas: PersonaConfig[],
    phase: PhaseType
  ): Array<PersonaConfig & { score: number; traitDetails: string }> {
    const mapping = this.PHASE_TRAIT_MAP[phase];

    return personas.map(persona => {
      const bigFive = this.parseBigFiveJson(persona.big_five_json);

      // 1. 主要特质分数 (60%)
      const primaryScore = bigFive[mapping.primary] * 0.6;

      // 2. 次要特质分数 (30%)
      const secondaryScore = mapping.secondary
        ? bigFive[mapping.secondary] * 0.3
        : 0;

      // 3. ELO标准化分数 (10%) - 将ELO转换为0-1范围
      const eloScore = this.normalizeElo(persona.elo_rating || 1500) * 0.1;

      // 4. 使用频率衰减 - 避免过度使用同一人格
      const usageDecay = Math.exp(-(persona.total_matches || 0) * 0.1);

      // 5. 计算最终分数
      const rawScore = (primaryScore + secondaryScore + eloScore) * usageDecay;

      // 6. 生成特质详情描述
      const traitDetails = this.generateTraitDescription(bigFive, mapping);

      return {
        ...persona,
        score: rawScore,
        traitDetails
      };
    }).sort((a, b) => b.score - a.score); // 降序排序
  }

  /**
   * 标准化ELO分数到0-1范围
   *
   * 创意点：使用sigmoid函数，让中等ELO也有机会
   */
  private normalizeElo(elo: number): number {
    // ELO通常范围：1000-2000，使用sigmoid标准化
    const normalized = (elo - 1000) / 1000; // 转换到0-1
    return 1 / (1 + Math.exp(-5 * (normalized - 0.5))); // sigmoid函数
  }

  /**
   * 生成特质描述
   *
   * 创意点：为每个人格生成独特的化学描述
   */
  private generateTraitDescription(
    bigFive: BigFiveTraits,
    mapping: PhaseTraitMapping
  ): string {
    const primary = bigFive[mapping.primary];
    const secondary = mapping.secondary ? bigFive[mapping.secondary] : null;

    let description = `${mapping.chemistry}\n`;
    description += `主要特质(${mapping.primary}): ${(primary * 100).toFixed(0)}%`;

    if (secondary !== null && mapping.secondary) {
      description += ` | 次要特质(${mapping.secondary}): ${(bigFive[mapping.secondary] * 100).toFixed(0)}%`;
    }

    // 添加人格特色标签
    const tags = this.generatePersonaTags(bigFive);
    description += `\n人格标签: ${tags.join(', ')}`;

    return description;
  }

  /**
   * 生成人格标签
   *
   * 创意点：根据特质组合生成有趣的人格标签
   */
  private generatePersonaTags(traits: BigFiveTraits): string[] {
    const tags: string[] = [];

    if (traits.O > 0.7) tags.push('💡创意先锋');
    if (traits.C > 0.7) tags.push('🔍细节控');
    if (traits.E > 0.7) tags.push('🎤表达大师');
    if (traits.A > 0.7) tags.push('🤝合作达人');
    if (traits.N < 0.3) tags.push('🧘‍♂️情绪稳定');

    // 特殊组合标签
    if (traits.O > 0.7 && traits.E > 0.7) tags.push('✨创意传播者');
    if (traits.C > 0.7 && traits.A > 0.7) tags.push('🏆完美协作者');

    return tags.length > 0 ? tags : ['🎯均衡型'];
  }

  /**
   * 应用新手保护机制
   *
   * 创意点：给新人机会，但不是完全随机
   */
  private applyNewbieProtection(
    scoredPersonas: Array<PersonaConfig & { score: number }>
  ): Array<PersonaConfig & { score: number }> {
    // 找出使用次数少于5次的新手
    const newbies = scoredPersonas.filter(p => (p.total_matches || 0) < 5);

    if (newbies.length === 0) return scoredPersonas;

    // 10%概率提升新手排名
    if (Math.random() < this.NEWBIE_PROBABILITY) {
      console.log(`🎉 触发新手保护！给 ${newbies.length} 个新人机会`);

      return scoredPersonas.map(persona => {
        const matches = persona.total_matches || 0;
        if (matches < 5) {
          // 给新手一个分数加成，但不超过顶级选手
          const boost = 0.3 * (1 - matches / 5); // 使用越少加成越多
          return {
            ...persona,
            score: persona.score * (1 + boost)
          };
        }
        return persona;
      }).sort((a, b) => b.score - a.score);
    }

    return scoredPersonas;
  }

  /**
   * 多样性优化选择
   *
   * 创新算法：平衡分数、模型多样性和特质分布
   */
  private selectWithDiversity(
    scoredPersonas: Array<PersonaConfig & { score: number }>,
    count: number
  ): PersonaConfig[] {
    const selected: PersonaConfig[] = [];
    const modelCount: Record<string, number> = {};

    for (const persona of scoredPersonas) {
      // 检查模型多样性
      const currentModelCount = modelCount[persona.model] || 0;
      if (currentModelCount >= this.MAX_SAME_MODEL) {
        continue; // 跳过，这个模型已经选够了
      }

      selected.push(persona);
      modelCount[persona.model] = currentModelCount + 1;

      if (selected.length >= count) {
        break;
      }
    }

    // 如果因为多样性限制没选够，补足数量
    if (selected.length < count) {
      const remaining = scoredPersonas
        .filter(p => !selected.includes(p))
        .slice(0, count - selected.length);

      selected.push(...remaining);
    }

    return selected;
  }

  /**
   * 打印选择报告
   *
   * 创意点：生成有趣的执行报告，让选择过程透明
   */
  private printSelectionReport(selected: PersonaConfig[], phase: PhaseType): void {
    const mapping = this.PHASE_TRAIT_MAP[phase];

    console.log('\n🎪 ====== 人格选择报告 ======');
    console.log(`阶段: ${phase} - ${mapping.chemistry}`);
    console.log('选中的特工阵容:');

    selected.forEach((persona, index) => {
      const bigFive = this.parseBigFiveJson(persona.big_five_json);
      const primaryTrait = bigFive[mapping.primary];
      const starRating = '⭐'.repeat(Math.ceil(primaryTrait * 5));

      console.log(`\n${index + 1}. ${persona.role} (${persona.persona_id})`);
      console.log(`   ${starRating} ${(primaryTrait * 100).toFixed(0)}% ${mapping.primary}特质`);
      console.log(`   📊 ELO: ${persona.elo_rating} | 对局: ${persona.total_matches}`);
      console.log(`   🤖 模型: ${persona.model}`);
    });

    // 计算团队多样性指数
    const models = new Set(selected.map(p => p.model));
    const diversityIndex = (models.size / selected.length).toFixed(2);
    console.log(`\n📈 团队多样性指数: ${diversityIndex} (${models.size}/${selected.length}种模型)`);
    console.log('================================\n');
  }
}
