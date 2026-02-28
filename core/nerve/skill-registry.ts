#!/usr/bin/env bun
/**
 * Skill Registry - 技能注册表
 *
 * 功能：
 * 1. 统一管理所有 Solar 能力（Agent、Intent、Skill、Tool）
 * 2. 支持按触发词、类型、分类查询
 * 3. 动态加载 Agent 定义文件
 *
 * @created 2026-02-27
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

// ============================================================
// 类型定义
// ============================================================

export type SkillType = 'agent' | 'intent' | 'skill' | 'tool';
export type DelegationMode = 'mcp' | 'skill' | 'legacy' | 'internal';

export interface SkillDefinition {
  id: string;                    // 唯一标识，如 "agent.coder", "intent.plan_and_act"
  name: string;                  // 显示名称
  type: SkillType;               // 类型
  description: string;           // 功能描述
  triggers: string[];            // 触发词列表
  delegationMode: DelegationMode; // 执行模式
  defaultModels?: string[];      // 默认使用的模型
  tools?: string[];              // 允许使用的工具
  disallowedTools?: string[];    // 禁止使用的工具
  mappedSkill?: string;          // 映射的 Skill（用于 skill 模式）
  metadata: {
    priority: number;            // 优先级 (1-10，越高越优先)
    tags: string[];              // 标签
    category: string;            // 分类
  };
}

export interface AgentYAML {
  name: string;
  description: string;
  delegation_mode: 'mcp' | 'skill' | 'legacy';
  mcp_tool?: string;
  default_models?: string[];
  tools?: string;
  disallowedTools?: string;
  mapped_skill?: string;
  ontology?: string;
}

// ============================================================
// SkillRegistry 类
// ============================================================

export class SkillRegistry {
  private skills: Map<string, SkillDefinition> = new Map();
  private triggersIndex: Map<string, Set<string>> = new Map(); // 触发词 → 技能ID 集合

  /**
   * 注册技能
   */
  register(skill: SkillDefinition): void {
    this.skills.set(skill.id, skill);

    // 建立触发词索引
    for (const trigger of skill.triggers) {
      const lowerTrigger = trigger.toLowerCase();
      if (!this.triggersIndex.has(lowerTrigger)) {
        this.triggersIndex.set(lowerTrigger, new Set());
      }
      this.triggersIndex.get(lowerTrigger)!.add(skill.id);
    }
  }

  /**
   * 获取技能
   */
  get(id: string): SkillDefinition | undefined {
    return this.skills.get(id);
  }

  /**
   * 按触发词查找（模糊匹配）
   */
  findByTrigger(input: string): SkillDefinition[] {
    const lowerInput = input.toLowerCase();
    const matches: Array<{ skill: SkillDefinition; score: number }> = [];

    for (const skill of this.skills.values()) {
      for (const trigger of skill.triggers) {
        if (lowerInput.includes(trigger.toLowerCase())) {
          // 计算匹配分数：触发词长度越长，越具体
          const score = trigger.length + skill.metadata.priority;
          matches.push({ skill, score });
          break; // 每个 skill 只计一次
        }
      }
    }

    // 按分数排序
    matches.sort((a, b) => b.score - a.score);
    return matches.map(m => m.skill);
  }

  /**
   * 按类型查找
   */
  findByType(type: SkillType): SkillDefinition[] {
    return Array.from(this.skills.values()).filter(s => s.type === type);
  }

  /**
   * 按分类查找
   */
  findByCategory(category: string): SkillDefinition[] {
    return Array.from(this.skills.values()).filter(
      s => s.metadata.category === category
    );
  }

  /**
   * 按标签查找
   */
  findByTag(tag: string): SkillDefinition[] {
    return Array.from(this.skills.values()).filter(
      s => s.metadata.tags.includes(tag)
    );
  }

  /**
   * 列出所有技能
   */
  list(): SkillDefinition[] {
    return Array.from(this.skills.values());
  }

  /**
   * 获取统计信息
   */
  getStats(): { total: number; byType: Record<SkillType, number> } {
    const byType: Record<SkillType, number> = {
      agent: 0,
      intent: 0,
      skill: 0,
      tool: 0
    };

    for (const skill of this.skills.values()) {
      byType[skill.type]++;
    }

    return { total: this.skills.size, byType };
  }

  /**
   * 从 Agent 定义目录加载
   */
  loadFromAgentsDir(): void {
    const agentsDir = join(homedir(), '.claude', 'agents');

    if (!existsSync(agentsDir)) {
      console.warn(`[SkillRegistry] Agents directory not found: ${agentsDir}`);
      return;
    }

    const files = readdirSync(agentsDir).filter(f => f.endsWith('.md'));

    for (const file of files) {
      try {
        const agentYAML = this.parseAgentDefinition(join(agentsDir, file));
        const skill = this.convertAgentToSkill(agentYAML);
        this.register(skill);
      } catch (error) {
        // 静默跳过没有 YAML frontmatter 的文件
        if (!(error instanceof Error && error.message.includes('No YAML frontmatter'))) {
          console.warn(`[SkillRegistry] Failed to load ${file}:`, error);
        }
      }
    }
  }

  /**
   * 解析 Agent 定义文件
   */
  private parseAgentDefinition(filePath: string): AgentYAML {
    const content = readFileSync(filePath, 'utf-8');

    const yamlMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (!yamlMatch) {
      throw new Error(`No YAML frontmatter found in ${filePath}`);
    }

    const yamlText = yamlMatch[1];
    const config: Partial<AgentYAML> = {};

    const lines = yamlText.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.startsWith('name:')) {
        config.name = line.replace('name:', '').trim();
      } else if (line.startsWith('description:')) {
        config.description = line.replace('description:', '').trim();
      } else if (line.startsWith('delegation_mode:')) {
        config.delegation_mode = line.replace('delegation_mode:', '').trim() as 'mcp' | 'skill' | 'legacy';
      } else if (line.startsWith('mcp_tool:')) {
        config.mcp_tool = line.replace('mcp_tool:', '').trim();
      } else if (line.startsWith('default_models:')) {
        config.default_models = [];
        i++;
        while (i < lines.length && lines[i].match(/^\s+-/)) {
          const model = lines[i].replace(/^\s*-\s*/, '').split('#')[0].trim();
          if (model) config.default_models.push(model);
          i++;
        }
        i--;
      } else if (line.startsWith('tools:')) {
        config.tools = line.replace('tools:', '').trim();
      } else if (line.startsWith('disallowedTools:')) {
        config.disallowedTools = line.replace('disallowedTools:', '').trim();
      } else if (line.startsWith('mapped_skill:')) {
        config.mapped_skill = line.replace('mapped_skill:', '').trim();
      }
    }

    if (!config.name) {
      throw new Error(`Missing name in ${filePath}`);
    }

    return config as AgentYAML;
  }

  /**
   * 将 Agent 定义转换为 Skill
   */
  private convertAgentToSkill(agent: AgentYAML): SkillDefinition {
    const agentName = agent.name.toLowerCase();

    // 根据 Agent 类型设置触发词和分类
    const triggerMap: Record<string, { triggers: string[]; category: string }> = {
      coder: {
        triggers: ['编码', '实现', '写代码', '开发', '重构'],
        category: 'execution'
      },
      researcher: {
        triggers: ['调研', '研究', '分析', '对比', '查资料'],
        category: 'research'
      },
      architect: {
        triggers: ['架构', '设计', '技术方案', '系统设计'],
        category: 'design'
      },
      tester: {
        triggers: ['测试', '验证', '检查', '性能测试'],
        category: 'quality'
      },
      reviewer: {
        triggers: ['审查', 'code review', '安全检查'],
        category: 'quality'
      },
      docs: {
        triggers: ['文档', '写文档', '生成文档', 'readme'],
        category: 'documentation'
      },
      ops: {
        triggers: ['部署', '构建', '发布', '上线', 'ci/cd'],
        category: 'operations'
      },
      pm: {
        triggers: ['产品', '需求', '验收', '项目管理'],
        category: 'management'
      },
      guard: {
        triggers: ['检查', '规范', '代码规范', '完整性'],
        category: 'quality'
      },
      secretary: {
        triggers: ['记录', '整理', '备忘', '状态'],
        category: 'support'
      },
      reporter: {
        triggers: ['报告', '写报告', '生成报告'],
        category: 'documentation'
      },
      'benchmark-reporter': {
        triggers: ['性能报告', '测试报告', '基准测试'],
        category: 'quality'
      }
    };

    const triggerInfo = triggerMap[agentName] || {
      triggers: [agentName],
      category: 'general'
    };

    return {
      id: `agent.${agentName}`,
      name: agent.name,
      type: 'agent',
      description: agent.description || `${agent.name} Agent`,
      triggers: triggerInfo.triggers,
      delegationMode: agent.delegation_mode === 'skill' ? 'skill' :
                      agent.delegation_mode === 'mcp' ? 'mcp' : 'legacy',
      defaultModels: agent.default_models,
      tools: agent.tools?.split(',').map(t => t.trim()),
      disallowedTools: agent.disallowedTools?.split(',').map(t => t.trim()),
      mappedSkill: agent.mapped_skill,
      metadata: {
        priority: 7,
        tags: [agentName, triggerInfo.category],
        category: triggerInfo.category
      }
    };
  }
}

// ============================================================
// 全局实例
// ============================================================

export const skillRegistry = new SkillRegistry();

// ============================================================
// 预置 Intent 技能
// ============================================================

const BUILTIN_INTENTS: SkillDefinition[] = [
  {
    id: 'intent.plan_and_act',
    name: 'Plan-and-Act',
    type: 'intent',
    description: '多步骤任务自动规划与执行',
    triggers: ['实现一个', '开发一个', '写一个', '做个', '帮我实现', '帮我开发', '重构', '集成', '修复这个', '调试'],
    delegationMode: 'internal',
    defaultModels: ['glm-5', 'gemini-2.5-pro'],
    metadata: {
      priority: 9,
      tags: ['planning', 'execution', 'multi-step'],
      category: 'execution'
    }
  },
  {
    id: 'intent.researcher',
    name: 'Researcher',
    type: 'intent',
    description: '深度调研与分析',
    triggers: ['调研', '研究', '分析', '对比', '是什么', '有哪些', '最佳实践'],
    delegationMode: 'skill',
    mappedSkill: '/insight',
    metadata: {
      priority: 8,
      tags: ['research', 'analysis'],
      category: 'research'
    }
  },
  {
    id: 'intent.evolution_council',
    name: 'Evolution Council',
    type: 'intent',
    description: '6角色会审决策',
    triggers: ['决策', '选择', '用哪个', '该不该', '要不要', '方案对比', '哪个好'],
    delegationMode: 'mcp',
    defaultModels: ['gemini-2.5-pro', 'deepseek-r1', 'glm-5'],
    metadata: {
      priority: 8,
      tags: ['decision', 'strategy'],
      category: 'decision'
    }
  },
  {
    id: 'intent.both',
    name: 'Research + Decision',
    type: 'intent',
    description: '先调研后决策',
    triggers: ['技术选型', '方案选型', '选什么技术', '设计', '架构', '实现'],
    delegationMode: 'internal',
    metadata: {
      priority: 7,
      tags: ['research', 'decision'],
      category: 'hybrid'
    }
  }
];

// ============================================================
// 初始化函数
// ============================================================

let initialized = false;

export function initSkillRegistry(): void {
  if (initialized) return;

  // 1. 加载预置 Intent
  for (const intent of BUILTIN_INTENTS) {
    skillRegistry.register(intent);
  }

  // 2. 从 Agent 目录加载
  skillRegistry.loadFromAgentsDir();

  initialized = true;
  console.log(`[SkillRegistry] Initialized with ${skillRegistry.list().length} skills`);
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  // 初始化
  initSkillRegistry();

  if (command === 'list') {
    const skills = skillRegistry.list();
    console.log(`\n📋 已注册技能 (${skills.length} 个):\n`);

    const byType: Record<string, SkillDefinition[]> = {};
    for (const skill of skills) {
      if (!byType[skill.type]) byType[skill.type] = [];
      byType[skill.type].push(skill);
    }

    for (const [type, typeSkills] of Object.entries(byType)) {
      console.log(`\n[${type.toUpperCase()}]`);
      for (const skill of typeSkills) {
        console.log(`  ${skill.id.padEnd(25)} ${skill.name}`);
        console.log(`    ${skill.description}`);
        console.log(`    触发词: ${skill.triggers.slice(0, 3).join(', ')}...`);
      }
    }

  } else if (command === 'search') {
    const keyword = args.slice(1).join(' ');
    if (!keyword) {
      console.error('用法: bun skill-registry.ts search <关键词>');
      process.exit(1);
    }

    const matches = skillRegistry.findByTrigger(keyword);
    console.log(`\n🔍 搜索 "${keyword}" (${matches.length} 个结果):\n`);

    for (const skill of matches) {
      console.log(`  ${skill.id.padEnd(25)} ${skill.name}`);
      console.log(`    类型: ${skill.type} | 优先级: ${skill.metadata.priority}`);
      console.log(`    分类: ${skill.metadata.category}`);
      console.log();
    }

  } else if (command === 'stats') {
    const stats = skillRegistry.getStats();
    console.log('\n📊 技能统计:\n');
    console.log(`  总数: ${stats.total}`);
    for (const [type, count] of Object.entries(stats.byType)) {
      if (count > 0) {
        console.log(`  ${type}: ${count}`);
      }
    }

  } else if (command === 'get') {
    const id = args[1];
    if (!id) {
      console.error('用法: bun skill-registry.ts get <skill-id>');
      process.exit(1);
    }

    const skill = skillRegistry.get(id);
    if (!skill) {
      console.error(`未找到技能: ${id}`);
      process.exit(1);
    }

    console.log(`\n📌 ${skill.name} (${skill.id})\n`);
    console.log(`  描述: ${skill.description}`);
    console.log(`  类型: ${skill.type}`);
    console.log(`  执行模式: ${skill.delegationMode}`);
    console.log(`  触发词: ${skill.triggers.join(', ')}`);
    if (skill.defaultModels) {
      console.log(`  模型: ${skill.defaultModels.join(', ')}`);
    }
    console.log(`  优先级: ${skill.metadata.priority}`);
    console.log(`  分类: ${skill.metadata.category}`);
    console.log(`  标签: ${skill.metadata.tags.join(', ')}`);

  } else {
    console.log(`
Skill Registry - 技能注册表

用法:
  bun skill-registry.ts list              # 列出所有技能
  bun skill-registry.ts search <关键词>   # 搜索技能
  bun skill-registry.ts get <skill-id>    # 查看技能详情
  bun skill-registry.ts stats             # 统计信息

示例:
  bun skill-registry.ts search "实现登录"
  bun skill-registry.ts get agent.coder
`);
  }
}
