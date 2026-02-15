/**
 * ARE DAG Builder
 *
 * Build and analyze DAG from Plan IR
 */

import { PlanIR, PlanTask } from '../types';

// ============================================
// DAG Node
// ============================================

export interface DAGNode {
  task: PlanTask;
  dependencies: Set<string>;    // Incoming edges (must complete before this)
  dependents: Set<string>;      // Outgoing edges (blocked by this)
  depth: number;                // Topological depth for parallel scheduling
  criticalPath: boolean;        // Is on the critical path?
}

// ============================================
// DAG
// ============================================

export class DAG {
  private nodes: Map<string, DAGNode> = new Map();
  private roots: Set<string> = new Set();     // Tasks with no dependencies
  private leaves: Set<string> = new Set();    // Tasks with no dependents
  private criticalPathLength: number = 0;

  constructor(plan: PlanIR) {
    this.build(plan);
  }

  /**
   * Build DAG from plan
   */
  private build(plan: PlanIR): void {
    // Create nodes
    for (const task of plan.tasks) {
      this.nodes.set(task.task_id, {
        task,
        dependencies: new Set(task.depends_on),
        dependents: new Set(),
        depth: 0,
        criticalPath: false,
      });
    }

    // Build reverse edges (dependents)
    for (const task of plan.tasks) {
      for (const dep of task.depends_on) {
        const depNode = this.nodes.get(dep);
        if (depNode) {
          depNode.dependents.add(task.task_id);
        }
      }
    }

    // Find roots and leaves
    for (const [id, node] of this.nodes) {
      if (node.dependencies.size === 0) {
        this.roots.add(id);
      }
      if (node.dependents.size === 0) {
        this.leaves.add(id);
      }
    }

    // Calculate depths (topological order)
    this.calculateDepths();

    // Mark critical path
    this.markCriticalPath();
  }

  /**
   * Calculate topological depth for each node
   * Depth = max(depth of dependencies) + 1
   */
  private calculateDepths(): void {
    const visited = new Set<string>();

    const visit = (taskId: string): number => {
      if (visited.has(taskId)) {
        return this.nodes.get(taskId)!.depth;
      }

      const node = this.nodes.get(taskId)!;
      let maxDepDepth = -1;

      for (const dep of node.dependencies) {
        maxDepDepth = Math.max(maxDepDepth, visit(dep));
      }

      node.depth = maxDepDepth + 1;
      visited.add(taskId);
      return node.depth;
    };

    for (const taskId of this.nodes.keys()) {
      visit(taskId);
    }

    // Calculate critical path length
    this.criticalPathLength = Math.max(...Array.from(this.nodes.values()).map(n => n.depth)) + 1;
  }

  /**
   * Mark nodes on the critical path
   * Critical path = longest path through the DAG
   */
  private markCriticalPath(): void {
    // Start from leaves and work backwards
    const maxDepth = this.criticalPathLength - 1;

    const markBackward = (taskId: string, targetDepth: number): void => {
      const node = this.nodes.get(taskId)!;
      if (node.depth !== targetDepth) return;

      node.criticalPath = true;

      // Find dependency on critical path
      for (const dep of node.dependencies) {
        const depNode = this.nodes.get(dep)!;
        if (depNode.depth === targetDepth - 1) {
          markBackward(dep, targetDepth - 1);
        }
      }
    };

    // Find all nodes at max depth (leaves on critical path)
    for (const leafId of this.leaves) {
      const node = this.nodes.get(leafId)!;
      if (node.depth === maxDepth) {
        markBackward(leafId, maxDepth);
      }
    }
  }

  /**
   * Get tasks that are ready to execute (all dependencies satisfied)
   */
  getReadyTasks(completed: Set<string>): PlanTask[] {
    const ready: PlanTask[] = [];

    for (const [id, node] of this.nodes) {
      if (completed.has(id)) continue;

      // Check if all dependencies are completed
      let allDepsCompleted = true;
      for (const dep of node.dependencies) {
        if (!completed.has(dep)) {
          allDepsCompleted = false;
          break;
        }
      }

      if (allDepsCompleted) {
        ready.push(node.task);
      }
    }

    // Sort by: critical path first, then by depth (earlier first)
    return ready.sort((a, b) => {
      const nodeA = this.nodes.get(a.task_id)!;
      const nodeB = this.nodes.get(b.task_id)!;

      // Critical path tasks first
      if (nodeA.criticalPath !== nodeB.criticalPath) {
        return nodeA.criticalPath ? -1 : 1;
      }

      // Earlier depth first
      return nodeA.depth - nodeB.depth;
    });
  }

  /**
   * Get topological order of all tasks
   */
  getTopologicalOrder(): PlanTask[] {
    const result: PlanTask[] = [];
    const visited = new Set<string>();

    const visit = (taskId: string): void => {
      if (visited.has(taskId)) return;

      const node = this.nodes.get(taskId)!;

      // Visit dependencies first
      for (const dep of node.dependencies) {
        visit(dep);
      }

      visited.add(taskId);
      result.push(node.task);
    };

    for (const taskId of this.nodes.keys()) {
      visit(taskId);
    }

    return result;
  }

  /**
   * Get parallel execution schedule
   * Returns array of task groups that can execute in parallel
   */
  getParallelSchedule(): PlanTask[][] {
    const schedule: PlanTask[][] = [];
    const completed = new Set<string>();

    while (completed.size < this.nodes.size) {
      const ready = this.getReadyTasks(completed);
      if (ready.length === 0) {
        // Should not happen if DAG is valid
        throw new Error('Deadlock detected in DAG');
      }

      schedule.push(ready);

      for (const task of ready) {
        completed.add(task.task_id);
      }
    }

    return schedule;
  }

  /**
   * Get node by task ID
   */
  getNode(taskId: string): DAGNode | undefined {
    return this.nodes.get(taskId);
  }

  /**
   * Get all nodes
   */
  getAllNodes(): DAGNode[] {
    return Array.from(this.nodes.values());
  }

  /**
   * Get root tasks (no dependencies)
   */
  getRoots(): PlanTask[] {
    return Array.from(this.roots).map(id => this.nodes.get(id)!.task);
  }

  /**
   * Get leaf tasks (no dependents)
   */
  getLeaves(): PlanTask[] {
    return Array.from(this.leaves).map(id => this.nodes.get(id)!.task);
  }

  /**
   * Get critical path tasks
   */
  getCriticalPath(): PlanTask[] {
    return Array.from(this.nodes.values())
      .filter(n => n.criticalPath)
      .sort((a, b) => a.depth - b.depth)
      .map(n => n.task);
  }

  /**
   * Get critical path length
   */
  getCriticalPathLength(): number {
    return this.criticalPathLength;
  }

  /**
   * Get maximum parallelism (max number of concurrent tasks)
   */
  getMaxParallelism(): number {
    const schedule = this.getParallelSchedule();
    return Math.max(...schedule.map(group => group.length));
  }

  /**
   * Get parallel efficiency estimate
   * = critical_path_length / total_tasks
   */
  getParallelEfficiency(): number {
    const totalTasks = this.nodes.size;
    if (totalTasks === 0) return 1;
    return this.criticalPathLength / totalTasks;
  }

  /**
   * Get affected tasks when a task fails
   * Returns all tasks that depend (directly or indirectly) on the failed task
   */
  getAffectedTasks(failedTaskId: string): Set<string> {
    const affected = new Set<string>();

    const visit = (taskId: string): void => {
      const node = this.nodes.get(taskId);
      if (!node) return;

      for (const dependent of node.dependents) {
        if (!affected.has(dependent)) {
          affected.add(dependent);
          visit(dependent);
        }
      }
    };

    visit(failedTaskId);
    return affected;
  }

  /**
   * Print DAG as ASCII art for debugging
   */
  toAscii(): string {
    const lines: string[] = [];
    const schedule = this.getParallelSchedule();

    lines.push('DAG Structure:');
    lines.push('─'.repeat(50));

    for (let i = 0; i < schedule.length; i++) {
      const group = schedule[i];
      const taskStrs = group.map(t => {
        const node = this.nodes.get(t.task_id)!;
        const marker = node.criticalPath ? '◆' : '○';
        return `${marker} ${t.task_id}:${t.name.slice(0, 20)}`;
      });

      lines.push(`Level ${i}: ${taskStrs.join(' | ')}`);
    }

    lines.push('─'.repeat(50));
    lines.push(`Critical Path: ${this.getCriticalPath().map(t => t.task_id).join(' → ')}`);
    lines.push(`Max Parallelism: ${this.getMaxParallelism()}`);
    lines.push(`Parallel Efficiency: ${(this.getParallelEfficiency() * 100).toFixed(1)}%`);

    return lines.join('\n');
  }
}

// ============================================
// DAG Builder
// ============================================

export class DAGBuilder {
  /**
   * Build DAG from Plan IR
   */
  build(plan: PlanIR): DAG {
    return new DAG(plan);
  }

  /**
   * Optimize DAG by merging small sequential tasks
   * Returns optimized Plan IR
   */
  optimize(plan: PlanIR): PlanIR {
    // TODO: Implement optimizations
    // - Merge small sequential tasks
    // - Reorder independent tasks for better cache locality
    // - Split large tasks for parallelism
    return plan;
  }
}

export const dagBuilder = new DAGBuilder();
