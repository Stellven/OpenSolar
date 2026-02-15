#!/usr/bin/env bun
/**
 * iMessage 发送工具
 * 使用 AppleScript 发送 iMessage
 */

import { execSync } from 'child_process';

const phone = process.argv[2];
const message = process.argv[3];

if (!phone || !message) {
  console.error('用法: bun send.ts <手机号> <消息内容>');
  console.error('示例: bun send.ts "+8618688716450" "你好"');
  process.exit(1);
}

const script = `
tell application "Messages"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant "${phone}" of targetService
    send "${message.replace(/"/g, '\\"')}" to targetBuddy
end tell
`;

try {
  execSync(`osascript -e '${script.replace(/'/g, "'\\''")}'`, {
    stdio: 'inherit'
  });
  console.log(`✅ iMessage 已发送到 ${phone}`);
} catch (error) {
  console.error(`❌ 发送失败: ${error.message}`);
  process.exit(1);
}
