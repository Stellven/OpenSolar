#!/usr/bin/env bun
/**
 * /backlog - Solar 待办管理 Skill
 * 项目 → 特性 → 任务 三层结构
 */

import { BacklogManager, type Feature, type Task, type ProjectBacklog } from '/Users/sihaoli/Solar/core/backlog/backlog-manager';

const manager = new BacklogManager();

// Parse arguments
const args = process.argv.slice(2);
const cmd = args[0] || '';

// Parse flags
function parseFlags(args: string[]): { flags: Record<string, string>; positional: string[] } {
  const flags: Record<string, string> = {};
  const positional: string[] = [];

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--')) {
      const [key, value] = arg.slice(2).split('=');
      flags[key] = value || args[++i] || 'true';
    } else if (arg.startsWith('-') && arg.length === 2) {
      const shortMap: Record<string, string> = {
        'p': 'project',
        'P': 'priority',
        'a': 'agent',
        'd': 'due'
      };
      const key = shortMap[arg[1]] || arg[1];
      flags[key] = args[++i] || 'true';
    } else {
      positional.push(arg);
    }
  }

  return { flags, positional };
}

const { flags, positional } = parseFlags(args.slice(1));
const projectId = flags.project || detectProject();

// Detect project from CWD
function detectProject(): string {
  const cwd = process.cwd();
  const parts = cwd.split('/');
  // Find last non-common directory
  for (let i = parts.length - 1; i >= 0; i--) {
    if (!['', 'Users', 'home', process.env.USER].includes(parts[i])) {
      return parts[i];
    }
  }
  return 'default';
}

// TVS Rendering helpers
function renderProgressBar(pct: number, width: number = 6): string {
  const filled = Math.round(pct / 100 * width);
  const empty = width - filled;
  return '█'.repeat(filled) + '░'.repeat(empty);
}

function renderBacklogTable(backlog: ProjectBacklog[]): string {
  if (backlog.length === 0) {
    return `
┌─ 📋 Backlog ────────────────────────────────────┐
│ No features found                               │
│ Use: /backlog add "Feature Name"                │
└─────────────────────────────────────────────────┘`;
  }

  const lines: string[] = [
    '┌─ 📋 Backlog ────────────────────────────────────┐',
    `│ Project: ${projectId.padEnd(38)}│`,
    '├─────────────────────────────────────────────────┤',
    '│ Feature              Status       Progress Tasks│',
    '│ ───────────────────────────────────────────────│'
  ];

  for (const item of backlog.slice(0, 10)) {
    const title = item.feature_title.slice(0, 18).padEnd(18);
    const status = item.feature_status.slice(0, 11).padEnd(11);
    const progress = `${renderProgressBar(item.progress_pct || 0)} ${String(Math.round(item.progress_pct || 0)).padStart(3)}%`;
    const tasks = `${item.completed_tasks}/${item.total_tasks}`.padStart(5);
    lines.push(`│ ${title} ${status} ${progress} ${tasks}│`);
  }

  lines.push('└─────────────────────────────────────────────────┘');
  return lines.join('\n');
}

function renderTaskList(tasks: Task[], featureTitle: string): string {
  const lines: string[] = [
    '┌─ 📝 Tasks ──────────────────────────────────────┐',
    `│ Feature: ${featureTitle.slice(0, 37).padEnd(37)}│`,
    '├─────────────────────────────────────────────────┤'
  ];

  for (const task of tasks) {
    const statusIcon = task.status === 'done' ? '✓' : task.status === 'in_progress' ? '→' : '○';
    const title = task.title.slice(0, 40).padEnd(40);
    const agent = (task.assigned_agent || '').slice(0, 6).padStart(6);
    lines.push(`│ ${statusIcon} ${title}${agent}│`);
  }

  if (tasks.length === 0) {
    lines.push('│ No tasks yet                                    │');
  }

  lines.push('└─────────────────────────────────────────────────┘');
  return lines.join('\n');
}

function renderStats(stats: ReturnType<BacklogManager['getStats']>): string {
  return `
┌─ 📊 Backlog Stats ──────────────────────────────┐
│ Features                                        │
│   Total: ${String(stats.totalFeatures).padStart(4)}    Open: ${String(stats.openFeatures).padStart(4)}                   │
├─────────────────────────────────────────────────┤
│ Tasks                                           │
│   Total: ${String(stats.totalTasks).padStart(4)}    Pending: ${String(stats.pendingTasks).padStart(4)}    Done: ${String(stats.completedTasks).padStart(4)}   │
├─────────────────────────────────────────────────┤
│ Message Queue: ${String(stats.messageQueueSize).padStart(4)} pending                       │
└─────────────────────────────────────────────────┘`;
}

function renderQueue(queue: ReturnType<BacklogManager['getMessageQueue']>): string {
  const lines: string[] = [
    '┌─ 📬 Message Queue ──────────────────────────────┐',
    '│ Source     Sender        Content         Priority│',
    '├─────────────────────────────────────────────────┤'
  ];

  for (const msg of queue) {
    const source = msg.source.slice(0, 8).padEnd(8);
    const sender = (msg.sender || 'unknown').slice(0, 10).padEnd(10);
    const content = msg.content.slice(0, 15).padEnd(15);
    const priority = String(msg.priority).padStart(4);
    lines.push(`│ ${source} ${sender} ${content} ${priority}│`);
  }

  if (queue.length === 0) {
    lines.push('│ Queue is empty                                  │');
  }

  lines.push('└─────────────────────────────────────────────────┘');
  return lines.join('\n');
}

// Command handlers
async function handleList(): Promise<void> {
  const backlog = manager.getProjectBacklog(projectId);
  console.log(renderBacklogTable(backlog));
}

async function handleAdd(): Promise<void> {
  const title = positional[0];
  if (!title) {
    console.error('Usage: /backlog add "Feature Title" [-p project] [-P priority]');
    process.exit(1);
  }

  const feature = manager.addFeature(projectId, title, {
    priority: flags.priority ? parseInt(flags.priority) : 50
  });

  console.log(`✓ Feature added: ${feature.feature_id}`);
}

async function handleTask(): Promise<void> {
  const featureId = positional[0];
  const title = positional[1];

  if (!featureId || !title) {
    console.error('Usage: /backlog task <feature_id> "Task Title" [-P priority] [-a agent]');
    process.exit(1);
  }

  const task = manager.addTask(featureId, title, {
    priority: flags.priority ? parseInt(flags.priority) : 50,
    assigned_agent: flags.agent
  });

  console.log(`✓ Task added: ${task.task_id}`);
}

async function handleDone(): Promise<void> {
  const id = positional[0];
  if (!id) {
    console.error('Usage: /backlog done <task_id|feature_id>');
    process.exit(1);
  }

  // Try task first, then feature
  const task = manager.getTask(id);
  if (task) {
    manager.completeTask(id);
    console.log(`✓ Task completed: ${id}`);
    return;
  }

  const feature = manager.updateFeature(id, { status: 'done' });
  if (feature) {
    console.log(`✓ Feature completed: ${id}`);
    return;
  }

  console.error(`Not found: ${id}`);
  process.exit(1);
}

async function handleSearch(): Promise<void> {
  const query = positional[0];
  if (!query) {
    console.error('Usage: /backlog search "query"');
    process.exit(1);
  }

  const results = manager.search(query, projectId);

  console.log(`\nSearch results for "${query}":`);

  if (results.features.length > 0) {
    console.log('\nFeatures:');
    for (const f of results.features) {
      console.log(`  ${f.feature_id}: ${f.title} [${f.status}]`);
    }
  }

  if (results.tasks.length > 0) {
    console.log('\nTasks:');
    for (const t of results.tasks) {
      console.log(`  ${t.task_id}: ${t.title} [${t.status}]`);
    }
  }

  if (results.features.length === 0 && results.tasks.length === 0) {
    console.log('No results found');
  }
}

async function handleExtract(): Promise<void> {
  // This would be called by Claude to extract tasks from current session
  // For now, just show instructions
  console.log(`
To extract tasks from conversation, provide them in JSON format:
{
  "session_id": "current-session-id",
  "tasks": [
    { "title": "Task description", "featureId": "project:feature" }
  ]
}

Claude will parse the conversation and identify actionable items.
`);
}

async function handleQueue(): Promise<void> {
  const limit = positional[0] ? parseInt(positional[0]) : 10;
  const queue = manager.getMessageQueue(limit);
  console.log(renderQueue(queue));
}

async function handleStats(): Promise<void> {
  const stats = manager.getStats(projectId);
  console.log(renderStats(stats));
}

async function handleFeature(): Promise<void> {
  const featureId = positional[0];
  if (!featureId) {
    console.error('Usage: /backlog feature <feature_id>');
    process.exit(1);
  }

  const feature = manager.getFeature(featureId);
  if (!feature) {
    console.error(`Feature not found: ${featureId}`);
    process.exit(1);
  }

  const tasks = manager.listTasks(featureId);
  console.log(renderTaskList(tasks, feature.title));
}

// Main
async function main(): Promise<void> {
  try {
    switch (cmd) {
      case '':
      case 'list':
        await handleList();
        break;
      case 'add':
        await handleAdd();
        break;
      case 'task':
        await handleTask();
        break;
      case 'done':
        await handleDone();
        break;
      case 'search':
        await handleSearch();
        break;
      case 'extract':
        await handleExtract();
        break;
      case 'queue':
        await handleQueue();
        break;
      case 'stats':
        await handleStats();
        break;
      case 'feature':
        await handleFeature();
        break;
      default:
        console.error(`Unknown command: ${cmd}`);
        console.log(`
Usage: /backlog [command] [args]

Commands:
  (default)   Show project backlog
  add         Add a feature
  task        Add a task to feature
  done        Mark task/feature as done
  search      Search features and tasks
  extract     Extract tasks from session
  queue       Show message queue
  stats       Show statistics
  feature     Show feature details
`);
        process.exit(1);
    }
  } finally {
    manager.close();
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
