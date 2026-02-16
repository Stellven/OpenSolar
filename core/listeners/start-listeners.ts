#!/usr/bin/env bun
/**
 * Solar Listeners Daemon
 * 启动所有消息监听器 + 执行器
 */

import { GmailListener } from './gmail-listener';
import { iMessageListener } from './imessage-listener';
import { MessageExecutor } from './message-executor';

const listeners = {
  gmail: new GmailListener(),
  imessage: new iMessageListener(),
};

const executor = new MessageExecutor();

async function main() {
  console.log('[Solar Listeners] Starting...');
  console.log('[Solar Listeners] PID:', process.pid);

  // Handle shutdown signals
  process.on('SIGINT', shutdown);
  process.on('SIGTERM', shutdown);

  // Start all listeners and executor
  await Promise.all([
    listeners.gmail.start(),
    listeners.imessage.start(),
    executor.start(30000), // 每 30 秒检查一次任务队列
  ]);

  console.log('[Solar Listeners] All listeners + executor started');
}

function shutdown() {
  console.log('[Solar Listeners] Shutting down...');
  listeners.gmail.stop();
  listeners.imessage.stop();
  executor.stop();
  process.exit(0);
}

main().catch(console.error);
