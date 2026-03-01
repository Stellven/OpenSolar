#!/usr/bin/env bun
/**
 * Skill Orchestrator - DAG 编排器（标准版）
 *
 * 功能：
 * 1. 依赖检测 - 从 SKILL.md 读取 dependencies 字段
 * 2. 拓扑排序 - 按依赖关系排序执行顺序
 * 3. 并行执行 - 无依赖的技能并行执行
 * 4. Brain Router 集成 - 调用多模型执行
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { parse as parseYaml } from 'yaml';

// ============ 类型定义 ============

type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';

interface SkillNode {
  name: string;
  dependencies: string[];
  status: NodeStatus;
  result?: any;
  error?: string;
}

interface ExecutionPhase {
  phase: number;
  nodes: string[];
  mode: 'parallel' | 'sequential';
}

interface OrchestratorConfig {
  skillsDir?: string;
  maxConcurrent?: number;
  onProgress?: (phase: number, node: string, status: NodeStatus) => void;
  executeFn?: (skillName: string) => Promise<any>;
}

interface ExecutionResult {
  success: boolean;
  phases: ExecutionPhase[];
  nodes: Map<string, SkillNode>;
  totalDuration: number;
}

// ============ DAG 编排器 ============

export class SkillOrchestrator {
  private skillsDir: string;
  private maxConcurrent: number;
  private onProgress?: (phase: number, node: string, status: NodeStatus) => void;
  private executeFn: (skillName: string) => Promise<any>;

  private nodes: Map<string, SkillNode> = new Map();
  private adjacency: Map<string, Set<string>> = new Map(); // node -> dependents
  private reverseAdj: Map<string, Set<string>> = new Map(); // node -> dependencies

  constructor(config: OrchestratorConfig = {}) {
    this.skillsDir = config.skillsDir || join(process.env.HOME!, '.claude/skills');
    this.maxConcurrent = config.maxConcurrent || 5;
    this.onProgress = config.onProgress;
    this.executeFn = config.executeFn || this.defaultExecute.bind(this);
  }

  /**
   * 默认执行函数（打印日志）
   */
  private async defaultExecute(skillName: string): Promise<any> {
    console.log(`  ⚡ 执行技能: ${skillName}`);
    // 实际使用时会替换为 Brain Router 调用
    return { skill: skillName, executed: true };
  }

  /**
   * 解析 SKILL.md 获取 dependencies
   */
  private parseSkillDependencies(skillName: string): string[] {
    const skillPath = join(this.skillsDir, skillName, 'SKILL.md');
    if (!existsSync(skillPath)) return [];

    const content = readFileSync(skillPath, 'utf-8');
    const match = content.match(/^---\n([\s\S]*?)\n---/);
    if (!match) return [];

    const frontmatter = match[1];

    // 查找 dependencies 字段
    const depsMatch = frontmatter.match(/dependencies:\s*\[([^\]]*)\]/);
    if (depsMatch) {
      return depsMatch[1]
        .split(',')
        .map(s => s.trim().replace(/['"]/g, ''))
        .filter(Boolean);
    }

    // 多行格式
    const multilineMatch = frontmatter.match(/dependencies:\s*\n((?:\s+-\s+.+\n?)+)/);
    if (multilineMatch) {
      return multilineMatch[1]
        .split('\n')
        .map(s => s.replace(/^\s*-\s*/, '').trim())
        .filter(Boolean);
    }

    return [];
  }

  /**
   * 添加技能节点
   */
  addNode(skillName: string, dependencies: string[] = []): void {
    const node: SkillNode = {
      name: skillName,
      dependencies,
      status: 'pending',
    };

    this.nodes.set(skillName, node);

    // 初始化邻接表
    if (!this.adjacency.has(skillName)) {
      this.adjacency.set(skillName, new Set());
    }
    if (!this.reverseAdj.has(skillName)) {
      this.reverseAdj.set(skillName, new Set());
    }

    // 添加依赖边
    for (const dep of dependencies) {
      if (!this.adjacency.has(dep)) {
        this.adjacency.set(dep, new Set());
      }
      this.adjacency.get(dep)!.add(skillName);
      this.reverseAdj.get(skillName)!.add(dep);
    }
  }

  /**
   * 从技能名列表构建 DAG
   */
  buildFromSkills(skillNames: string[]): void {
    this.nodes.clear();
    this.adjacency.clear();
    this.reverseAdj.clear();

    for (const skillName of skillNames) {
      const deps = this.parseSkillDependencies(skillName);
      this.addNode(skillName, deps);
    }
  }

  /**
   * 检测循环依赖
   */
  detectCycle(): string[] | null {
    const WHITE = 0, GRAY = 1, BLACK = 2;
    const color = new Map<string, number>();
    const parent = new Map<string, string>();

    for (const node of this.nodes.keys()) {
      color.set(node, WHITE);
    }

    const dfs = (node: string): string[] | null => {
      color.set(node, GRAY);

      for (const neighbor of this.adjacency.get(node) || []) {
        if (!color.has(neighbor)) continue;

        if (color.get(neighbor) === GRAY) {
          // 找到循环
          const cycle = [neighbor, node];
          let current = node;
          while (parent.has(current) && parent.get(current) !== neighbor) {
            current = parent.get(current)!;
            cycle.push(current);
          }
          return cycle.reverse();
        }

        if (color.get(neighbor) === WHITE) {
          parent.set(neighbor, node);
          const result = dfs(neighbor);
          if (result) return result;
        }
      }

      color.set(node, BLACK);
      return null;
    };

    for (const node of this.nodes.keys()) {
      if (color.get(node) === WHITE) {
        const result = dfs(node);
        if (result) return result;
      }
    }

    return null;
  }

  /**
   * 获取执行阶段（并行分组）
   */
  getExecutionPhases(): ExecutionPhase[] {
    const levels = new Map<string, number>();

    const getLevel = (node: string): number => {
      if (levels.has(node)) return levels.get(node)!;

      const deps = this.reverseAdj.get(node) || new Set();
      if (deps.size === 0) {
        levels.set(node, 0);
        return 0;
      }

      const validDeps = [...deps].filter(d => this.nodes.has(d));
      if (validDeps.length === 0) {
        levels.set(node, 0);
        return 0;
      }

      const maxDepLevel = Math.max(...validDeps.map(getLevel));
      levels.set(node, maxDepLevel + 1);
      return levels.get(node)!;
    };

    // 计算所有节点的层级
    for (const node of this.nodes.keys()) {
      getLevel(node);
    }

    // 按层级分组
    const phaseMap = new Map<number, string[]>();
    for (const [node, level] of levels) {
      if (!phaseMap.has(level)) {
        phaseMap.set(level, []);
      }
      phaseMap.get(level)!.push(node);
    }

    // 构建执行阶段
    const phases: ExecutionPhase[] = [];
    for (const [level, nodes] of [...phaseMap.entries()].sort((a, b) => a[0] - b[0])) {
      phases.push({
        phase: level + 1,
        nodes: nodes.sort(),
        mode: nodes.length > 1 ? 'parallel' : 'sequential',
      });
    }

    return phases;
  }

  /**
   * 获取就绪的节点（依赖都已完成）
   */
  getReadyNodes(): string[] {
    const ready: string[] = [];

    for (const [name, node] of this.nodes) {
      if (node.status !== 'pending') continue;

      const deps = this.reverseAdj.get(name) || new Set();
      const allDepsCompleted = [...deps].every(dep => {
        const depNode = this.nodes.get(dep);
        return !depNode || depNode.status === 'completed';
      });

      if (allDepsCompleted) {
        ready.push(name);
      }
    }

    return ready;
  }

  /**
   * 更新节点状态
   */
  updateStatus(nodeName: string, status: NodeStatus, result?: any, error?: string): void {
    const node = this.nodes.get(nodeName);
    if (!node) return;

    node.status = status;
    if (result !== undefined) node.result = result;
    if (error !== undefined) node.error = error;
  }

  /**
   * 执行单个节点
   */
  private async executeNode(nodeName: string, phase: number): Promise<void> {
    this.updateStatus(nodeName, 'running');
    this.onProgress?.(phase, nodeName, 'running');

    try {
      const result = await this.executeFn(nodeName);
      this.updateStatus(nodeName, 'completed', result);
      this.onProgress?.(phase, nodeName, 'completed');
    } catch (error: any) {
      this.updateStatus(nodeName, 'failed', undefined, error.message);
      this.onProgress?.(phase, nodeName, 'failed');
      throw error;
    }
  }

  /**
   * 执行所有阶段
   */
  async execute(): Promise<ExecutionResult> {
    const startTime = Date.now();

    // 检测循环依赖
    const cycle = this.detectCycle();
    if (cycle) {
      return {
        success: false,
        phases: [],
        nodes: this.nodes,
        totalDuration: 0,
      };
    }

    const phases = this.getExecutionPhases();
    console.log(`\n📋 执行计划: ${phases.length} 个阶段, ${this.nodes.size} 个技能\n`);

    for (const phase of phases) {
      console.log(`\n⚡ Phase ${phase.phase} (${phase.mode}): ${phase.nodes.join(', ')}`);

      if (phase.mode === 'parallel') {
        // 并行执行
        const promises = phase.nodes.map(node => this.executeNode(node, phase.phase));
        await Promise.all(promises);
      } else {
        // 顺序执行
        for (const node of phase.nodes) {
          await this.executeNode(node, phase.phase);
        }
      }
    }

    const totalDuration = Date.now() - startTime;
    const success = [...this.nodes.values()].every(n => n.status === 'completed');

    console.log(`\n${success ? '✅' : '❌'} 执行完成 (${totalDuration}ms)`);

    return {
      success,
      phases,
      nodes: this.nodes,
      totalDuration,
    };
  }

  /**
   * 可视化 DAG
   */
  visualize(): string {
    const phases = this.getExecutionPhases();
    const lines: string[] = ['\n📊 DAG 执行图\n'];

    for (const phase of phases) {
      const prefix = phase.phase < phases.length ? '├──' : '└──';
      const mode = phase.mode === 'parallel' ? '⚡ 并行' : '➡️ 顺序';

      lines.push(`${prefix} Phase ${phase.phase} (${mode})`);

      for (let i = 0; i < phase.nodes.length; i++) {
        const isLast = i === phase.nodes.length - 1;
        const nodePrefix = isLast ? '│   └──' : '│   ├──';
        const node = phase.nodes[i];
        const nodeObj = this.nodes.get(node);
        const statusIcon = {
          pending: '⏳',
          running: '🔄',
          completed: '✅',
          failed: '❌',
          skipped: '⏭️',
        }[nodeObj?.status || 'pending'];

        lines.push(`${nodePrefix} ${statusIcon} ${node}`);

        // 显示依赖
        const deps = nodeObj?.dependencies || [];
        if (deps.length > 0) {
          lines.push(`│       └─ 依赖: ${deps.join(', ')}`);
        }
      }
    }

    return lines.join('\n');
  }
}

// ============ 便捷函数 ============

/**
 * 创建编排器并执行技能
 */
export async function orchestrateSkills(
  skillNames: string[],
  config?: OrchestratorConfig
): Promise<ExecutionResult> {
  const orchestrator = new SkillOrchestrator(config);
  orchestrator.buildFromSkills(skillNames);
  return orchestrator.execute();
}

/**
 * 分析技能依赖并返回执行计划
 */
export function analyzeDependencies(skillNames: string[]): {
  phases: ExecutionPhase[];
  cycle: string[] | null;
} {
  const orchestrator = new SkillOrchestrator();
  orchestrator.buildFromSkills(skillNames);

  return {
    phases: orchestrator.getExecutionPhases(),
    cycle: orchestrator.detectCycle(),
  };
}

// ============ CLI ============

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'analyze': {
      const skills = args.slice(1);
      if (skills.length === 0) {
        console.log('用法: skill-orchestrator analyze <skill1> <skill2> ...');
        process.exit(1);
      }

      const orchestrator = new SkillOrchestrator();
      orchestrator.buildFromSkills(skills);

      console.log(orchestrator.visualize());

      const cycle = orchestrator.detectCycle();
      if (cycle) {
        console.log(`\n⚠️ 检测到循环依赖: ${cycle.join(' -> ')}`);
      }
      break;
    }

    case 'execute': {
      const skills = args.slice(1).filter(a => !a.startsWith('--'));
      if (skills.length === 0) {
        console.log('用法: skill-orchestrator execute <skill1> <skill2> ...');
        process.exit(1);
      }

      const orchestrator = new SkillOrchestrator({
        onProgress: (phase, node, status) => {
          const icons: Record<NodeStatus, string> = {
            pending: '⏳',
            running: '🔄',
            completed: '✅',
            failed: '❌',
            skipped: '⏭️',
          };
          console.log(`  ${icons[status]} [P${phase}] ${node}: ${status}`);
        },
      });

      orchestrator.buildFromSkills(skills);
      const result = await orchestrator.execute();

      console.log(`\n📊 执行统计:`);
      console.log(`   成功: ${result.success ? '是' : '否'}`);
      console.log(`   阶段: ${result.phases.length}`);
      console.log(`   耗时: ${result.totalDuration}ms`);
      break;
    }

    default: {
      console.log(`
Skill Orchestrator - DAG 编排器

用法:
  skill-orchestrator analyze <skill1> <skill2> ...  分析依赖关系
  skill-orchestrator execute <skill1> <skill2> ...  执行技能

示例:
  skill-orchestrator analyze commit pr review
  skill-orchestrator execute docs changelog
`);
    }
  }
}

main().catch(console.error);
