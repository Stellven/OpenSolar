#!/usr/bin/env bun
/**
 * /xiaoai skill - 调用小爱 (OpenClaw)
 *
 * 用法:
 *   bun call.ts "任务描述"
 *   bun call.ts --agent main --thinking high "任务描述"
 */

interface Args {
  message: string;
  agent: string;
  thinking: string;
  model?: string;
}

function parseArgs(): Args {
  const args = process.argv.slice(2);
  let message = '';
  let agent = 'main';
  let thinking = 'medium';
  let model: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--agent' && args[i + 1]) {
      agent = args[i + 1];
      i++;
    } else if (args[i] === '--thinking' && args[i + 1]) {
      thinking = args[i + 1];
      i++;
    } else if (args[i] === '--model' && args[i + 1]) {
      model = args[i + 1];
      i++;
    } else if (!args[i].startsWith('--')) {
      message += (message ? ' ' : '') + args[i];
    }
  }

  return { message, agent, thinking, model };
}

async function callXiaoAi(args: Args): Promise<void> {
  if (!args.message) {
    console.log('用法: /xiaoai <任务描述>');
    console.log('示例: /xiaoai 查一下今天的邮件');
    process.exit(1);
  }

  console.log(`💝 调用小爱... (agent: ${args.agent}, thinking: ${args.thinking})`);
  console.log(`📝 任务: ${args.message.slice(0, 50)}${args.message.length > 50 ? '...' : ''}`);
  console.log('');

  // 构建命令
  const cmd = ['openclaw', 'agent', '--local', '--agent', args.agent, '--thinking', args.thinking];

  if (args.model) {
    cmd.push('--message', `用 ${args.model} 模型处理: ${args.message}`);
  } else {
    cmd.push('--message', args.message);
  }

  // 执行
  const result = Bun.spawn(cmd, {
    stdout: 'inherit',
    stderr: 'inherit',
    env: {
      ...process.env,
      PATH: '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/lisihao/n/bin'
    }
  });

  const exitCode = await result.exited;

  if (exitCode !== 0) {
    console.error('\n❌ 小爱调用失败');
    process.exit(exitCode);
  }
}

// 主入口
const args = parseArgs();
callXiaoAi(args);
