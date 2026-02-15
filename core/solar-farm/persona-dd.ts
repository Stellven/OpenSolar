/**
 * Persona D&D v5.0 - D&D 角色卡作为人格前端 DSL
 *
 * 核心架构:
 * Layer A (后端): 性能人格向量 (Policy Knobs) - 真控制面
 * Layer B (前端): D&D 角色卡 - 人类可读、可组合、可升级
 *
 * D&D → 编译 → Knobs → 行为
 */

// ============================================================
// Layer A: 性能人格向量 (后端真控制面)
// ============================================================

export interface PolicyKnobs {
  // 证据与验证
  evidenceThreshold: number;    // 证据门槛 (0-5)
  skepticism: number;           // 怀疑强度 (0-5)

  // 推理节奏
  exploration: number;          // 发散度 (0-5)
  decisiveness: number;         // 决断性 (0-5)

  // 行为偏好
  toolFirst: number;            // 工具倾向 (0-5)
  compression: number;          // 压缩率 (0-5)
  riskAversion: number;         // 风险厌恶 (0-5)

  // 自我与社交
  selfCritique: number;         // 自检强度 (0-5)
  competitiveness: number;      // 竞技性 (0-5)

  // 扩展维度
  creativity: number;           // 创造性 (0-5)
  detail: number;               // 细节关注 (0-5)
}

// ============================================================
// Layer B: D&D 角色卡 (前端 DSL)
// ============================================================

/**
 * D&D 六大属性
 *
 * 设计原则: 低维、正交、适合做路由与预算决策
 */
export interface DnDAttributes {
  strength: number;      // STR 力量 (0-20) → 执行力、落地能力
  dexterity: number;     // DEX 敏捷 (0-20) → 灵活性、应变能力
  constitution: number;  // CON 体质 (0-20) → 稳定性、持久性
  intelligence: number;  // INT 智力 (0-20) → 分析能力、逻辑推理
  wisdom: number;        // WIS 感知 (0-20) → 洞察力、判断力
  charisma: number;      // CHA 魅力 (0-20) → 表达力、影响力
}

/**
 * 技能熟练度
 *
 * 设计原则: 任务能力标签，适合做 workload 绑定
 */
export interface SkillProficiency {
  skill: string;         // 技能名称
  modifier: number;      // 修正值 (+0 ~ +5)
  advantage: boolean;    // 优势 (骰两次取高)
  expertise: boolean;    // 专精 (双倍熟练加值)
}

/**
 * 专长 (Feat)
 *
 * 设计原则: 可插拔的策略插件
 * 例如: 强制自检、强制反例、强制引用
 */
export interface Feat {
  name: string;          // 专长名称
  description: string;   // 效果描述
  trigger: string[];     // 触发条件
  effect: {
    knobOverride?: Partial<PolicyKnobs>;  // 旋钮覆盖
    forcedBehavior?: string[];            // 强制行为
    bannedBehavior?: string[];            // 禁止行为
  };
}

/**
 * 阵营 (Alignment)
 *
 * 九宫格阵营 → 行为倾向映射
 */
export type Alignment =
  | 'LG' | 'NG' | 'CG'   // 守序/中立/混乱 善良
  | 'LN' | 'TN' | 'CN'   // 守序/中立/混乱 中立
  | 'LE' | 'NE' | 'CE';  // 守序/中立/混乱 邪恶

/**
 * 职业 (Class)
 *
 * 定义核心能力和成长路径
 */
export interface CharacterClass {
  name: string;                    // 职业名称
  hitDie: string;                  // 生命骰 (d6/d8/d10/d12)
  primaryAbility: string;          // 主属性
  savingThrows: string[];          // 豁免熟练
  coreFeatures: string[];          // 核心能力
  knobsBase: Partial<PolicyKnobs>; // 基础旋钮
}

/**
 * 等级与经验
 *
 * 绩效闭环的天然载体: 绩效 → XP → 升级 → 行为变化
 */
export interface LevelProgress {
  level: number;         // 当前等级 (1-20)
  xp: number;            // 当前经验值
  xpToNext: number;      // 升级所需经验
  proficiencyBonus: number; // 熟练加值 (等级/4 + 1)
}

/**
 * 完整 D&D 角色卡
 */
export interface DnDCharacterSheet {
  // 基本信息
  name: string;                    // 角色名称
  modelId: string;                 // 对应模型
  class: CharacterClass;           // 职业
  level: LevelProgress;            // 等级

  // 属性与能力
  attributes: DnDAttributes;       // 六大属性
  skills: SkillProficiency[];      // 技能熟练
  feats: Feat[];                   // 专长
  alignment: Alignment;            // 阵营

  // 背景故事
  background: {
    trait: string;        // 性格特征
    ideal: string;        // 理想
    bond: string;         // 羁绊
    flaw: string;         // 缺陷
  };
}

// ============================================================
// D&D → Knobs 编译器
// ============================================================

/**
 * 属性到旋钮的映射规则
 */
const ATTRIBUTE_TO_KNOB_MAP = {
  // INT (智力) → 分析能力
  intelligence: {
    evidenceThreshold: (v: number) => Math.floor(v / 4),   // 高INT=高证据门槛
    skepticism: (v: number) => Math.floor(v / 5),          // 高INT=高怀疑
  },

  // WIS (感知) → 判断力
  wisdom: {
    riskAversion: (v: number) => Math.floor(v / 4),        // 高WIS=谨慎
    selfCritique: (v: number) => Math.floor(v / 5),        // 高WIS=自省
  },

  // CHA (魅力) → 表达力
  charisma: {
    compression: (v: number) => Math.max(0, 3 - Math.floor(v / 6)), // 高CHA=低压缩(多表达)
    competitiveness: (v: number) => Math.floor(v / 5),     // 高CHA=竞技性
  },

  // DEX (敏捷) → 灵活性
  dexterity: {
    exploration: (v: number) => Math.floor(v / 4),         // 高DEX=高探索
    decisiveness: (v: number) => Math.floor(v / 5),        // 高DEX=果断
  },

  // STR (力量) → 执行力
  strength: {
    toolFirst: (v: number) => Math.floor(v / 4),           // 高STR=工具倾向
    creativity: (v: number) => Math.floor(v / 5),          // 高STR=创造性
  },

  // CON (体质) → 稳定性
  constitution: {
    detail: (v: number) => Math.floor(v / 4),              // 高CON=细节关注
  }
};

/**
 * 阵营到行为倾向的映射
 */
const ALIGNMENT_EFFECTS: Record<Alignment, Partial<PolicyKnobs>> = {
  // 善良阵营: 关注质量、自检
  'LG': { selfCritique: 4, riskAversion: 4, decisiveness: 2 },
  'NG': { selfCritique: 3, exploration: 3, riskAversion: 3 },
  'CG': { creativity: 4, exploration: 4, decisiveness: 3 },

  // 中立阵营: 平衡
  'LN': { decisiveness: 4, evidenceThreshold: 3, riskAversion: 3 },
  'TN': { },  // 完全中立，不调整
  'CN': { exploration: 4, creativity: 4, riskAversion: 1 },

  // 邪恶阵营: 激进、冒险 (注意: 这里"邪恶"不代表恶意，而是激进策略)
  'LE': { decisiveness: 5, competitiveness: 4, riskAversion: 1 },
  'NE': { exploration: 3, competitiveness: 3 },
  'CE': { creativity: 5, decisiveness: 5, riskAversion: 0 }
};

/**
 * 将 D&D 角色卡编译为性能人格向量
 */
export function compileDDtoKnobs(sheet: DnDCharacterSheet): PolicyKnobs {
  // 1. 从职业获取基础旋钮
  const baseKnobs: PolicyKnobs = {
    evidenceThreshold: sheet.class.knobsBase.evidenceThreshold ?? 2,
    skepticism: sheet.class.knobsBase.skepticism ?? 2,
    exploration: sheet.class.knobsBase.exploration ?? 2,
    decisiveness: sheet.class.knobsBase.decisiveness ?? 2,
    toolFirst: sheet.class.knobsBase.toolFirst ?? 2,
    compression: sheet.class.knobsBase.compression ?? 2,
    riskAversion: sheet.class.knobsBase.riskAversion ?? 2,
    selfCritique: sheet.class.knobsBase.selfCritique ?? 2,
    competitiveness: sheet.class.knobsBase.competitiveness ?? 2,
    creativity: sheet.class.knobsBase.creativity ?? 2,
    detail: sheet.class.knobsBase.detail ?? 2,
  };

  // 2. 从属性计算旋钮调整
  const attrAdjustments: Partial<PolicyKnobs> = {};

  for (const [attr, value] of Object.entries(sheet.attributes)) {
    const mapper = ATTRIBUTE_TO_KNOB_MAP[attr as keyof DnDAttributes];
    if (mapper) {
      for (const [knob, fn] of Object.entries(mapper)) {
        const current = attrAdjustments[knob as keyof PolicyKnobs] ?? 0;
        attrAdjustments[knob as keyof PolicyKnobs] = Math.max(current, fn(value));
      }
    }
  }

  // 3. 应用熟练加值
  const proficiencyBonus = sheet.level.proficiencyBonus;
  for (const skill of sheet.skills) {
    if (skill.expertise) {
      // 专精: 双倍加值
      // 这里可以根据技能类型影响对应旋钮
    }
  }

  // 4. 应用阵营效果
  const alignmentEffect = ALIGNMENT_EFFECTS[sheet.alignment];

  // 5. 应用专长效果
  const featEffects: Partial<PolicyKnobs> = {};
  for (const feat of sheet.feats) {
    if (feat.effect.knobOverride) {
      Object.assign(featEffects, feat.effect.knobOverride);
    }
  }

  // 6. 合并所有效果 (优先级: Feat > Alignment > Attributes > Base)
  const finalKnobs: PolicyKnobs = {
    ...baseKnobs,
    ...attrAdjustments,
    ...alignmentEffect,
    ...featEffects
  } as PolicyKnobs;

  // 7. 确保值在 0-5 范围内
  for (const key of Object.keys(finalKnobs)) {
    finalKnobs[key as keyof PolicyKnobs] = Math.max(0, Math.min(5, finalKnobs[key as keyof PolicyKnobs]));
  }

  return finalKnobs;
}

// ============================================================
// 预定义职业
// ============================================================

export const CHARACTER_CLASSES: Record<string, CharacterClass> = {
  // 审判官: 严谨审查、高证据门槛
  judge: {
    name: '审判官',
    hitDie: 'd10',
    primaryAbility: 'wisdom',
    savingThrows: ['wisdom', 'charisma'],
    coreFeatures: ['真相探测', '证据审查', '偏见免疫'],
    knobsBase: {
      evidenceThreshold: 4,
      skepticism: 5,
      selfCritique: 4,
      riskAversion: 4,
    }
  },

  // 创想家: 高探索、高创造
  innovator: {
    name: '创想家',
    hitDie: 'd8',
    primaryAbility: 'charisma',
    savingThrows: ['dexterity', 'charisma'],
    coreFeatures: ['灵感迸发', '跨界联想', '原型快速迭代'],
    knobsBase: {
      exploration: 5,
      creativity: 5,
      decisiveness: 3,
      riskAversion: 1,
    }
  },

  // 智囊: 深度分析、高细节
  advisor: {
    name: '智囊',
    hitDie: 'd6',
    primaryAbility: 'intelligence',
    savingThrows: ['intelligence', 'wisdom'],
    coreFeatures: ['深度研究', '多维权衡', '战略分析'],
    knobsBase: {
      evidenceThreshold: 4,
      detail: 4,
      selfCritique: 4,
      decisiveness: 2,
    }
  },

  // 稳健派: 高风险厌恶、高自检
  conservative: {
    name: '稳健派',
    hitDie: 'd12',
    primaryAbility: 'constitution',
    savingThrows: ['constitution', 'wisdom'],
    coreFeatures: ['风险识别', '防御策略', '质量保证'],
    knobsBase: {
      riskAversion: 5,
      selfCritique: 5,
      evidenceThreshold: 4,
      exploration: 1,
    }
  },

  // 建设者: 高工具倾向、高执行
  builder: {
    name: '建设者',
    hitDie: 'd10',
    primaryAbility: 'strength',
    savingThrows: ['strength', 'constitution'],
    coreFeatures: ['快速落地', '工具精通', '批量执行'],
    knobsBase: {
      toolFirst: 5,
      decisiveness: 4,
      compression: 3,
      exploration: 2,
    }
  },

  // 探索者: 高探索、高灵活
  scout: {
    name: '探索者',
    hitDie: 'd8',
    primaryAbility: 'dexterity',
    savingThrows: ['dexterity', 'intelligence'],
    coreFeatures: ['快速扫描', '信息提取', '边界探索'],
    knobsBase: {
      exploration: 4,
      decisiveness: 4,
      compression: 4,
      detail: 2,
    }
  }
};

// ============================================================
// 预定义专长
// ============================================================

export const FEATS: Record<string, Feat> = {
  // 强制自检
  forcedSelfCritique: {
    name: '强制自检',
    description: '每次输出前必须进行自我审查，列出至少一个潜在问题',
    trigger: ['before_output'],
    effect: {
      knobOverride: { selfCritique: 5 },
      forcedBehavior: ['必须列出至少一个潜在问题或改进点']
    }
  },

  // 强制反例
  forcedCounterexample: {
    name: '强制反例',
    description: '分析时必须主动寻找反例和边缘情况',
    trigger: ['analysis_task'],
    effect: {
      knobOverride: { skepticism: 5 },
      forcedBehavior: ['必须列出至少一个反例或边缘情况']
    }
  },

  // 强制引用
  forcedCitation: {
    name: '强制引用',
    description: '结论必须引用证据来源',
    trigger: ['conclusion'],
    effect: {
      knobOverride: { evidenceThreshold: 5 },
      forcedBehavior: ['每个结论必须标注来源 (citation_key)']
    }
  },

  // 快速响应
  rapidResponse: {
    name: '快速响应',
    description: '优先速度，压缩输出',
    trigger: ['simple_task'],
    effect: {
      knobOverride: { compression: 5, decisiveness: 4 },
    }
  },

  // 深度分析
  deepAnalysis: {
    name: '深度分析',
    description: '优先深度，详细输出',
    trigger: ['complex_task'],
    effect: {
      knobOverride: { detail: 5, exploration: 4, compression: 1 },
    }
  }
};

// ============================================================
// XP 与升级系统
// ============================================================

/**
 * 根据绩效计算 XP
 */
export function calculateXP(
  taskDifficulty: 'easy' | 'medium' | 'hard' | 'deadly',
  success: boolean,
  qualityScore: number  // 0-5
): number {
  const difficultyXP = {
    easy: 100,
    medium: 300,
    hard: 600,
    deadly: 1200
  };

  const baseXP = difficultyXP[taskDifficulty];
  const successMultiplier = success ? 1 : 0.25;
  const qualityMultiplier = qualityScore / 3;  // 3分 = 1x

  return Math.floor(baseXP * successMultiplier * qualityMultiplier);
}

/**
 * 检查是否升级
 */
export function checkLevelUp(progress: LevelProgress): {
  leveledUp: boolean;
  newLevel: number;
  newProficiencyBonus: number;
} {
  const xpThresholds = [
    0, 300, 900, 2700, 6500,      // Level 1-5
    14000, 23000, 34000, 48000, 64000,  // Level 6-10
    85000, 100000, 120000, 140000, 165000, // Level 11-15
    195000, 225000, 265000, 305000, 355000 // Level 16-20
  ];

  const currentLevel = progress.level;
  if (currentLevel >= 20) {
    return { leveledUp: false, newLevel: 20, newProficiencyBonus: 6 };
  }

  const nextThreshold = xpThresholds[currentLevel];
  if (progress.xp >= nextThreshold) {
    const newLevel = currentLevel + 1;
    const newProficiencyBonus = Math.floor(newLevel / 4) + 1;
    return { leveledUp: true, newLevel, newProficiencyBonus };
  }

  return { leveledUp: false, newLevel: currentLevel, newProficiencyBonus: progress.proficiencyBonus };
}

/**
 * 升级效果: 获得新专长或提升属性
 */
export function applyLevelUp(
  sheet: DnDCharacterSheet,
  upgradeChoice: {
    type: 'feat' | 'attribute';
    featName?: string;
    attributeName?: keyof DnDAttributes;
  }
): DnDCharacterSheet {
  const updated = { ...sheet };

  if (upgradeChoice.type === 'feat' && upgradeChoice.featName) {
    const feat = FEATS[upgradeChoice.featName];
    if (feat) {
      updated.feats = [...updated.feats, feat];
    }
  } else if (upgradeChoice.type === 'attribute' && upgradeChoice.attributeName) {
    updated.attributes = {
      ...updated.attributes,
      [upgradeChoice.attributeName]: Math.min(20, updated.attributes[upgradeChoice.attributeName] + 2)
    };
  }

  return updated;
}

// ============================================================
// 生成角色卡 Prompt
// ============================================================

export function buildDDPrompt(sheet: DnDCharacterSheet): string {
  const knobs = compileDDtoKnobs(sheet);

  return `你是 ${sheet.name}，一名 ${sheet.class.name} (Level ${sheet.level.level})。

## 角色属性
- 力量 (STR): ${sheet.attributes.strength} - 执行力、落地能力
- 敏捷 (DEX): ${sheet.attributes.dexterity} - 灵活性、应变能力
- 体质 (CON): ${sheet.attributes.constitution} - 稳定性、持久性
- 智力 (INT): ${sheet.attributes.intelligence} - 分析能力、逻辑推理
- 感知 (WIS): ${sheet.attributes.wisdom} - 洞察力、判断力
- 魅力 (CHA): ${sheet.attributes.charisma} - 表达力、影响力

## 阵营
${sheet.alignment} - ${getAlignmentDescription(sheet.alignment)}

## 核心能力
${sheet.class.coreFeatures.map(f => `- ${f}`).join('\n')}

## 专长
${sheet.feats.map(f => `- **${f.name}**: ${f.description}`).join('\n') || '无'}

## 背景故事
- **性格**: ${sheet.background.trait}
- **理想**: ${sheet.background.ideal}
- **羁绊**: ${sheet.background.bond}
- **缺陷**: ${sheet.background.flaw}

## 行为准则 (编译自 D&D 属性)

### 证据与验证
- 证据门槛: ${'█'.repeat(knobs.evidenceThreshold)}${'░'.repeat(5-knobs.evidenceThreshold)} (${knobs.evidenceThreshold}/5)
- 怀疑强度: ${'█'.repeat(knobs.skepticism)}${'░'.repeat(5-knobs.skepticism)} (${knobs.skepticism}/5)

### 推理节奏
- 发散度: ${'█'.repeat(knobs.exploration)}${'░'.repeat(5-knobs.exploration)} (${knobs.exploration}/5)
- 决断性: ${'█'.repeat(knobs.decisiveness)}${'░'.repeat(5-knobs.decisiveness)} (${knobs.decisiveness}/5)

### 行为偏好
- 工具倾向: ${'█'.repeat(knobs.toolFirst)}${'░'.repeat(5-knobs.toolFirst)} (${knobs.toolFirst}/5)
- 压缩率: ${'█'.repeat(knobs.compression)}${'░'.repeat(5-knobs.compression)} (${knobs.compression}/5)
- 风险厌恶: ${'█'.repeat(knobs.riskAversion)}${'░'.repeat(5-knobs.riskAversion)} (${knobs.riskAversion}/5)

### 自我与社交
- 自检强度: ${'█'.repeat(knobs.selfCritique)}${'░'.repeat(5-knobs.selfCritique)} (${knobs.selfCritique}/5)
- 竞技性: ${'█'.repeat(knobs.competitiveness)}${'░'.repeat(5-knobs.competitiveness)} (${knobs.competitiveness}/5)
`;
}

function getAlignmentDescription(alignment: Alignment): string {
  const descriptions: Record<Alignment, string> = {
    'LG': '守序善良 - 遵循规则，追求正义',
    'NG': '中立善良 - 利他主义，不拘泥于规则',
    'CG': '混乱善良 - 自由意志，反抗不公',
    'LN': '守序中立 - 遵循规则，不问善恶',
    'TN': '绝对中立 - 平衡至上，不偏不倚',
    'CN': '混乱中立 - 自由至上，不受约束',
    'LE': '守序邪恶 - 利用规则谋利',
    'NE': '中立邪恶 - 不择手段',
    'CE': '混乱邪恶 - 破坏与混乱'
  };
  return descriptions[alignment];
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'classes': {
      console.log('\n⚔️ 可用职业:\n');
      for (const [key, cls] of Object.entries(CHARACTER_CLASSES)) {
        console.log(`【${cls.name}】(${key})`);
        console.log(`  主属性: ${cls.primaryAbility}`);
        console.log(`  核心能力: ${cls.coreFeatures.join(', ')}`);
        console.log(`  基础旋钮: ${JSON.stringify(cls.knobsBase)}`);
        console.log('');
      }
      break;
    }

    case 'feats': {
      console.log('\n✨ 可用专长:\n');
      for (const [key, feat] of Object.entries(FEATS)) {
        console.log(`【${feat.name}】(${key})`);
        console.log(`  效果: ${feat.description}`);
        if (feat.effect.knobOverride) {
          console.log(`  旋钮覆盖: ${JSON.stringify(feat.effect.knobOverride)}`);
        }
        console.log('');
      }
      break;
    }

    case 'compile': {
      // 示例: 编译一个角色
      const exampleSheet: DnDCharacterSheet = {
        name: '技术宅',
        modelId: 'gemini-2.5-pro',
        class: CHARACTER_CLASSES.judge,
        level: { level: 5, xp: 6500, xpToNext: 14000, proficiencyBonus: 3 },
        attributes: {
          strength: 10,
          dexterity: 12,
          constitution: 14,
          intelligence: 18,
          wisdom: 16,
          charisma: 8
        },
        skills: [
          { skill: '代码审查', modifier: 5, advantage: false, expertise: true },
          { skill: '架构分析', modifier: 5, advantage: true, expertise: false }
        ],
        feats: [FEATS.forcedCitation],
        alignment: 'LG',
        background: {
          trait: '严谨务实，追求数据支撑',
          ideal: '代码质量高于一切',
          bond: '对技术标准的坚守',
          flaw: '过于保守，有时错失创新机会'
        }
      };

      const knobs = compileDDtoKnobs(exampleSheet);

      console.log('\n🔧 D&D → Knobs 编译结果:\n');
      console.log(`角色: ${exampleSheet.name} (${exampleSheet.class.name})`);
      console.log(`等级: ${exampleSheet.level.level}\n`);

      console.log('编译后的性能人格向量:');
      for (const [key, value] of Object.entries(knobs)) {
        const bar = '█'.repeat(value) + '░'.repeat(5 - value);
        console.log(`  ${key.padEnd(18)} [${bar}] ${value}`);
      }
      break;
    }

    case 'prompt': {
      const exampleSheet: DnDCharacterSheet = {
        name: '技术宅',
        modelId: 'gemini-2.5-pro',
        class: CHARACTER_CLASSES.judge,
        level: { level: 5, xp: 6500, xpToNext: 14000, proficiencyBonus: 3 },
        attributes: {
          strength: 10,
          dexterity: 12,
          constitution: 14,
          intelligence: 18,
          wisdom: 16,
          charisma: 8
        },
        skills: [
          { skill: '代码审查', modifier: 5, advantage: false, expertise: true },
          { skill: '架构分析', modifier: 5, advantage: true, expertise: false }
        ],
        feats: [FEATS.forcedCitation],
        alignment: 'LG',
        background: {
          trait: '严谨务实，追求数据支撑',
          ideal: '代码质量高于一切',
          bond: '对技术标准的坚守',
          flaw: '过于保守，有时错失创新机会'
        }
      };

      console.log(buildDDPrompt(exampleSheet));
      break;
    }

    case 'xp': {
      const difficulty = (process.argv[3] || 'medium') as 'easy' | 'medium' | 'hard' | 'deadly';
      const success = process.argv[4] !== 'fail';
      const quality = parseFloat(process.argv[5]) || 3;

      const xp = calculateXP(difficulty, success, quality);
      console.log(`\n📊 XP 计算:\n`);
      console.log(`  难度: ${difficulty}`);
      console.log(`  成功: ${success}`);
      console.log(`  质量分: ${quality}/5`);
      console.log(`  获得 XP: ${xp}`);
      break;
    }

    default:
      console.log(`
🎲 Persona D&D v5.0 - D&D 角色卡作为人格前端 DSL

用法:
  bun persona-dd.ts classes     # 列出所有职业
  bun persona-dd.ts feats       # 列出所有专长
  bun persona-dd.ts compile     # 编译示例角色 → Knobs
  bun persona-dd.ts prompt      # 生成角色卡 Prompt
  bun persona-dd.ts xp <难度> <成功> <质量>  # 计算 XP

架构:
  Layer B (前端): D&D 角色卡 - 人类可读、可组合、可升级
    ├── 六大属性 (STR/DEX/CON/INT/WIS/CHA)
    ├── 技能熟练 (Skill Proficiency)
    ├── 专长 (Feat) - 可插拔策略插件
    ├── 阵营 (Alignment) - 行为倾向
    └── 等级/XP - 绩效闭环载体
              ↓ 编译
  Layer A (后端): 性能人格向量 (Policy Knobs)
    ├── evidenceThreshold / skepticism
    ├── exploration / decisiveness
    ├── toolFirst / compression / riskAversion
    └── selfCritique / competitiveness

D&D ≠ 人格，而是人格的可视化配置界面！
`);
  }
}

export default {
  CHARACTER_CLASSES,
  FEATS,
  compileDDtoKnobs,
  calculateXP,
  checkLevelUp,
  applyLevelUp,
  buildDDPrompt
};
