#!/usr/bin/env bun
/**
 * DAG Visualizer - DAG 可视化工具
 *
 * 功能：
 * 1. 将 Plan 转换为 DAG 图形
 * 2. ASCII 终端输出
 * 3. HTML 可视化输出
 *
 * @created 2026-02-27
 */

import type { Plan, PlanStep, PlanStepStatus } from './types';
import { writeFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

// ============ 类型定义 ============

export interface DAGNode {
  id: string;
  label: string;
  agent: string;
  status: PlanStepStatus;
  dependencies: string[];
  level: number;  // 拓扑层级
  position: { x: number; y: number };
}

export interface DAGEdge {
  from: string;
  to: string;
}

export interface DAGGraph {
  nodes: DAGNode[];
  edges: DAGEdge[];
  levels: DAGNode[][];  // 按层级分组的节点
}

// ============ 状态颜色映射 ============

const STATUS_COLORS: Record<PlanStepStatus, { symbol: string; color: string; bg: string }> = {
  pending: { symbol: '○', color: '\x1b[90m', bg: '#9CA3AF' },
  running: { symbol: '◐', color: '\x1b[33m', bg: '#FBBF24' },
  completed: { symbol: '●', color: '\x1b[32m', bg: '#10B981' },
  failed: { symbol: '✗', color: '\x1b[31m', bg: '#EF4444' },
  skipped: { symbol: '⊘', color: '\x1b[90m', bg: '#6B7280' }
};

const STATUS_RESET = '\x1b[0m';

// ============ DAG 构建器 ============

/**
 * 将 Plan 转换为 DAG 图
 */
export function buildDAG(plan: Plan): DAGGraph {
  const nodes: DAGNode[] = [];
  const edges: DAGEdge[] = [];

  // 1. 创建节点
  for (const step of plan.steps) {
    nodes.push({
      id: step.id,
      label: truncateLabel(step.action, 20),
      agent: step.agent || 'Unknown',
      status: step.status,
      dependencies: step.dependencies,
      level: 0,
      position: { x: 0, y: 0 }
    });
  }

  // 2. 创建边
  for (const step of plan.steps) {
    for (const depId of step.dependencies) {
      edges.push({ from: depId, to: step.id });
    }
  }

  // 3. 计算拓扑层级（Kahn 算法）
  const levels = computeTopologicalLevels(nodes, edges);

  // 4. 分配位置
  let maxWidth = 0;
  for (const level of levels) {
    maxWidth = Math.max(maxWidth, level.length);
  }

  for (let l = 0; l < levels.length; l++) {
    const levelNodes = levels[l];
    const y = l;
    for (let i = 0; i < levelNodes.length; i++) {
      const node = levelNodes[i];
      node.level = l;
      // 居中排列
      const xOffset = (maxWidth - levelNodes.length) / 2;
      node.position = { x: i + xOffset, y };
    }
  }

  return { nodes, edges, levels };
}

/**
 * 计算拓扑层级
 */
function computeTopologicalLevels(nodes: DAGNode[], edges: DAGEdge[]): DAGNode[][] {
  const levels: DAGNode[][] = [];
  const nodeMap = new Map(nodes.map(n => [n.id, n]));
  const inDegree = new Map(nodes.map(n => [n.id, 0]));

  // 计算入度
  for (const edge of edges) {
    inDegree.set(edge.to, (inDegree.get(edge.to) || 0) + 1);
  }

  // 找出所有入度为 0 的节点（第一层）
  let currentLevel = nodes.filter(n => inDegree.get(n.id) === 0);

  while (currentLevel.length > 0) {
    levels.push(currentLevel);

    // 下一层节点
    const nextLevel: DAGNode[] = [];
    for (const node of currentLevel) {
      // 找到所有依赖当前节点的边
      for (const edge of edges.filter(e => e.from === node.id)) {
        const targetNode = nodeMap.get(edge.to);
        if (targetNode) {
          const newDegree = (inDegree.get(edge.to) || 0) - 1;
          inDegree.set(edge.to, newDegree);
          if (newDegree === 0 && !nextLevel.includes(targetNode)) {
            nextLevel.push(targetNode);
          }
        }
      }
    }

    currentLevel = nextLevel;
  }

  return levels;
}

/**
 * 截断标签
 */
function truncateLabel(label: string, maxLen: number): string {
  if (label.length <= maxLen) return label;
  return label.slice(0, maxLen - 3) + '...';
}

// ============ ASCII 渲染器 ============

/**
 * 渲染 ASCII DAG
 */
export function renderASCII(dag: DAGGraph): string {
  const lines: string[] = [];

  lines.push('');
  lines.push('╔════════════════════════════════════════════════════════════════╗');
  lines.push('║                      DAG 可视化                                 ║');
  lines.push('╚════════════════════════════════════════════════════════════════╝');
  lines.push('');

  // 图例
  lines.push('图例:');
  for (const [status, { symbol, color }] of Object.entries(STATUS_COLORS)) {
    lines.push(`  ${color}${symbol}${STATUS_RESET} ${status}`);
  }
  lines.push('');

  // 按层级渲染
  for (let l = 0; l < dag.levels.length; l++) {
    const levelNodes = dag.levels[l];

    lines.push(`┌─────────────────────────────────────────────────────────────────┐`);
    lines.push(`│ Level ${l}${' '.repeat(57)}`.slice(0, 65) + '│');
    lines.push(`├─────────────────────────────────────────────────────────────────┤`);

    for (const node of levelNodes) {
      const { symbol, color } = STATUS_COLORS[node.status];
      const agent = `[${node.agent}]`.padEnd(12);
      const label = node.label.padEnd(25);

      lines.push(`│  ${color}${symbol}${STATUS_RESET} ${node.id.padEnd(10)} ${agent} ${label}│`.slice(0, 66) + '│');
    }

    lines.push(`└─────────────────────────────────────────────────────────────────┘`);

    // 绘制连接线到下一层
    if (l < dag.levels.length - 1) {
      const nextLevel = dag.levels[l + 1];
      const hasConnections = dag.edges.some(e =>
        levelNodes.some(n => n.id === e.from) &&
        nextLevel.some(n => n.id === e.to)
      );

      if (hasConnections) {
        lines.push('                              │');
        lines.push('                              ▼');
      }
    }
  }

  // 统计
  lines.push('');
  lines.push('统计:');
  const statusCount: Record<string, number> = {};
  for (const node of dag.nodes) {
    statusCount[node.status] = (statusCount[node.status] || 0) + 1;
  }
  for (const [status, count] of Object.entries(statusCount)) {
    const { color } = STATUS_COLORS[status as PlanStepStatus];
    lines.push(`  ${color}${status}${STATUS_RESET}: ${count}`);
  }
  lines.push('');

  return lines.join('\n');
}

/**
 * 渲染简洁版 ASCII（单行模式）
 */
export function renderCompact(dag: DAGGraph): string {
  const lines: string[] = [];

  for (let l = 0; l < dag.levels.length; l++) {
    const levelNodes = dag.levels[l];
    const nodeStrs = levelNodes.map(n => {
      const { symbol, color } = STATUS_COLORS[n.status];
      return `${color}${symbol}${STATUS_RESET} ${n.id}`;
    });

    lines.push(`L${l}: ${nodeStrs.join(' → ')}`);
  }

  return lines.join('\n');
}

// ============ HTML 渲染器 ============

/**
 * 渲染 HTML DAG
 */
export function renderHTML(dag: DAGGraph, title: string = 'DAG 可视化'): string {
  const width = 800;
  const nodeWidth = 180;
  const nodeHeight = 80;
  const levelGap = 120;
  const nodeGap = 20;

  // 计算最大宽度
  let maxNodesInLevel = 0;
  for (const level of dag.levels) {
    maxNodesInLevel = Math.max(maxNodesInLevel, level.length);
  }
  const svgWidth = Math.max(width, maxNodesInLevel * (nodeWidth + nodeGap) + 100);
  const svgHeight = dag.levels.length * (nodeHeight + levelGap) + 100;

  // 生成节点 SVG
  const nodeSVGs: string[] = [];
  for (let l = 0; l < dag.levels.length; l++) {
    const levelNodes = dag.levels[l];
    const levelWidth = levelNodes.length * (nodeWidth + nodeGap) - nodeGap;
    const startX = (svgWidth - levelWidth) / 2;

    for (let i = 0; i < levelNodes.length; i++) {
      const node = levelNodes[i];
      const x = startX + i * (nodeWidth + nodeGap);
      const y = 50 + l * (nodeHeight + levelGap);
      const { bg } = STATUS_COLORS[node.status];

      nodeSVGs.push(`
        <g class="node" data-id="${node.id}">
          <rect x="${x}" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"
                fill="${bg}" stroke="#374151" stroke-width="2"/>
          <text x="${x + nodeWidth / 2}" y="${y + 25}" text-anchor="middle"
                fill="white" font-weight="bold" font-size="14">${node.id}</text>
          <text x="${x + nodeWidth / 2}" y="${y + 45}" text-anchor="middle"
                fill="white" font-size="12">${node.agent}</text>
          <text x="${x + nodeWidth / 2}" y="${y + 65}" text-anchor="middle"
                fill="white" font-size="11" opacity="0.8">${node.label}</text>
        </g>
      `);
    }
  }

  // 生成边 SVG
  const edgeSVGs: string[] = [];
  for (const edge of dag.edges) {
    const fromNode = dag.nodes.find(n => n.id === edge.from);
    const toNode = dag.nodes.find(n => n.id === edge.to);
    if (!fromNode || !toNode) continue;

    const fromX = fromNode.position.x * (nodeWidth + nodeGap) + nodeWidth / 2 + (svgWidth - dag.levels[fromNode.level].length * (nodeWidth + nodeGap)) / 2;
    const fromY = 50 + fromNode.level * (nodeHeight + levelGap) + nodeHeight;
    const toX = toNode.position.x * (nodeWidth + nodeGap) + nodeWidth / 2 + (svgWidth - dag.levels[toNode.level].length * (nodeWidth + nodeGap)) / 2;
    const toY = 50 + toNode.level * (nodeHeight + levelGap);

    edgeSVGs.push(`
      <path d="M${fromX},${fromY} C${fromX},${fromY + 40} ${toX},${toY - 40} ${toX},${toY}"
            stroke="#6B7280" stroke-width="2" fill="none" marker-end="url(#arrowhead)"/>
    `);
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #111827;
      color: #F9FAFB;
      padding: 20px;
    }
    h1 { text-align: center; margin-bottom: 20px; }
    .container { overflow-x: auto; }
    svg { display: block; margin: 0 auto; }
    .legend {
      display: flex; justify-content: center; gap: 20px;
      margin-bottom: 20px; flex-wrap: wrap;
    }
    .legend-item { display: flex; align-items: center; gap: 8px; }
    .legend-dot { width: 16px; height: 16px; border-radius: 50%; }
    .node:hover rect { stroke: #60A5FA; stroke-width: 3; cursor: pointer; }
  </style>
</head>
<body>
  <h1>${title}</h1>

  <div class="legend">
    ${Object.entries(STATUS_COLORS).map(([status, { bg }]) => `
      <div class="legend-item">
        <div class="legend-dot" style="background: ${bg}"></div>
        <span>${status}</span>
      </div>
    `).join('')}
  </div>

  <div class="container">
    <svg width="${svgWidth}" height="${svgHeight}">
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7" fill="#6B7280"/>
        </marker>
      </defs>

      <!-- Edges -->
      ${edgeSVGs.join('')}

      <!-- Nodes -->
      ${nodeSVGs.join('')}
    </svg>
  </div>

  <script>
    document.querySelectorAll('.node').forEach(node => {
      node.addEventListener('click', () => {
        const id = node.dataset.id;
        console.log('Clicked:', id);
        // TODO: 显示详情面板
      });
    });
  </script>
</body>
</html>`;
}

/**
 * 保存 HTML 到文件
 */
export function saveHTML(html: string, filename: string = 'dag.html'): string {
  const outputPath = join(homedir(), '.claude', 'output', filename);
  writeFileSync(outputPath, html, 'utf-8');
  return outputPath;
}

// ============ CLI ============

if (import.meta.main) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'demo') {
    // 演示 DAG
    const demoPlan: Plan = {
      id: 'demo-plan',
      goal: '实现用户登录功能',
      steps: [
        { id: 'step-0', action: '分析需求', agent: 'Researcher', dependencies: [], status: 'completed', retryCount: 0, maxRetries: 3 },
        { id: 'step-1', action: '设计数据模型', agent: 'Architect', dependencies: ['step-0'], status: 'completed', retryCount: 0, maxRetries: 3 },
        { id: 'step-2', action: '实现用户模型', agent: 'Coder', dependencies: ['step-1'], status: 'running', retryCount: 0, maxRetries: 3 },
        { id: 'step-3', action: '实现认证逻辑', agent: 'Coder', dependencies: ['step-1'], status: 'pending', retryCount: 0, maxRetries: 3 },
        { id: 'step-4', action: '编写单元测试', agent: 'Tester', dependencies: ['step-2', 'step-3'], status: 'pending', retryCount: 0, maxRetries: 3 },
        { id: 'step-5', action: '代码审查', agent: 'Reviewer', dependencies: ['step-4'], status: 'pending', retryCount: 0, maxRetries: 3 }
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      currentStepIndex: 2,
      constraints: ['不引入新依赖']
    };

    const dag = buildDAG(demoPlan);

    // ASCII 输出
    console.log(renderASCII(dag));

    // 紧凑版
    console.log('\n紧凑版:');
    console.log(renderCompact(dag));

    // HTML 输出
    const html = renderHTML(dag, '用户登录功能 - DAG');
    const outputPath = saveHTML(html, 'demo-dag.html');
    console.log(`\n📄 HTML 已保存: ${outputPath}`);

  } else if (command === 'html') {
    // 生成演示 HTML
    const demoPlan: Plan = {
      id: 'demo-plan',
      goal: '示例 DAG',
      steps: [
        { id: 'step-0', action: '开始', agent: 'System', dependencies: [], status: 'completed', retryCount: 0, maxRetries: 3 },
        { id: 'step-1', action: '步骤 A', agent: 'Coder', dependencies: ['step-0'], status: 'running', retryCount: 0, maxRetries: 3 },
        { id: 'step-2', action: '步骤 B', agent: 'Coder', dependencies: ['step-0'], status: 'pending', retryCount: 0, maxRetries: 3 },
        { id: 'step-3', action: '步骤 C', agent: 'Tester', dependencies: ['step-1', 'step-2'], status: 'pending', retryCount: 0, maxRetries: 3 }
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
      currentStepIndex: 1,
      constraints: []
    };

    const dag = buildDAG(demoPlan);
    const html = renderHTML(dag, args[1] || 'DAG 可视化');
    const outputPath = saveHTML(html, args[2] || 'dag.html');
    console.log(`📄 HTML 已保存: ${outputPath}`);

  } else {
    console.log(`
DAG Visualizer - DAG 可视化工具

用法:
  bun dag-visualizer.ts demo    # 显示演示 DAG
  bun dag-visualizer.ts html    # 生成 HTML 文件

输出:
  - ASCII 终端图形
  - HTML 可视化文件 (~/.claude/output/dag.html)
`);
  }
}

export type { DAGGraph, DAGNode, DAGEdge };
