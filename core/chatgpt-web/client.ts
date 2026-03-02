#!/usr/bin/env bun
/**
 * ChatGPT 网页版客户端
 * 使用 Puppeteer 连接到已运行的 Chrome（调试模式）
 *
 * 用法:
 *   bun client.ts ask "你的问题"
 *   bun client.ts ask "问题" --model o1
 *
 * 前置条件:
 *   1. 关闭所有 Chrome 窗口
 *   2. 运行: ~/.claude/scripts/start-chrome-debug.sh
 *   3. 在打开的 Chrome 中登录 chatgpt.com
 */

import puppeteer from 'puppeteer-core';

interface ChatGPTOptions {
  model?: 'GPT-4o' | 'GPT-4o mini' | 'o1' | 'o3-mini';
  timeout?: number;
}

/**
 * 连接到 Chrome
 */
export async function connectToChrome() {
  const browser = await puppeteer.connect({
    browserURL: 'http://localhost:9222',
    defaultViewport: null,
  });
  return browser;
}

/**
 * 发送消息到 ChatGPT 并获取回复
 */
export async function askChatGPT(
  prompt: string,
  options: ChatGPTOptions = {}
): Promise<string> {
  const { timeout = 60000 } = options;

  console.log('🤖 连接到 Chrome...');
  const browser = await connectToChrome();
  const pages = await browser.pages();

  // 找到或创建 ChatGPT 页面
  let page = pages.find((p) => p.url().includes('chatgpt.com'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://chatgpt.com', { waitUntil: 'networkidle2' });
  }

  // 检查登录状态
  const loginButton = await page.$('button');
  const buttonTexts = await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    return Array.from(buttons).map(b => b.textContent);
  });
  if (buttonTexts.some(t => t?.includes('登录') || t?.includes('Log in'))) {
    throw new Error('❌ 未登录 ChatGPT。请先在 Chrome 中登录');
  }

  console.log('📝 发送问题...');

  // 点击输入框
  const input = await page.$('div[contenteditable="true"]');
  if (!input) {
    throw new Error('❌ 找不到输入框');
  }

  // 清空并输入
  await input.click();
  await page.keyboard.down('Meta');
  await page.keyboard.press('a');
  await page.keyboard.up('Meta');
  await page.keyboard.type(prompt, { delay: 10 });

  // 发送
  await page.keyboard.press('Enter');

  console.log('⏳ 等待回复...');

  // 等待回复出现
  await new Promise((r) => setTimeout(r, 3000));

  // 等待回复完成（检测停止按钮消失）
  try {
    await page.waitForSelector('button[aria-label="停止生成"]', {
      timeout: 5000,
    });
    await page.waitForSelector('button[aria-label="停止生成"]', {
      hidden: true,
      timeout,
    });
  } catch {
    // 可能没有停止按钮
  }

  // 额外等待确保内容完整
  await new Promise((r) => setTimeout(r, 1000));

  // 提取最后一条回复
  const responses = await page.$$('div.markdown');
  if (responses.length === 0) {
    throw new Error('❌ 无法获取回复');
  }

  const lastResponse = responses[responses.length - 1];
  const text = await lastResponse.evaluate((el) => el.textContent);

  // 断开连接（不关闭浏览器）
  await browser.disconnect();

  return text || '';
}

/**
 * 选择模型
 */
export async function selectModel(
  page: puppeteer.Page,
  model: string
): Promise<void> {
  try {
    // 点击模型选择器
    const modelButton = await page.$('button[aria-label*="模型"]');
    if (modelButton) {
      await modelButton.click();
      await new Promise((r) => setTimeout(r, 500));
    }

    // 选择模型
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await btn.evaluate(el => el.textContent);
      if (text?.includes(model)) {
        await btn.click();
        await new Promise((r) => setTimeout(r, 500));
        return;
      }
    }
  } catch {
    console.warn('⚠️ 无法切换模型，使用默认');
  }
}

// CLI 入口
const args = process.argv.slice(2);

if (args[0] === 'ask' && args[1]) {
  const prompt = args.slice(1).join(' ').replace(/^--model \S+ /, '').replace(/ --model \S+$/, '');
  const modelIndex = args.indexOf('--model');
  const model = modelIndex > -1 ? args[modelIndex + 1] : 'GPT-4o';

  console.log(`\n🤖 询问 ChatGPT (${model})...\n`);

  askChatGPT(prompt, { model })
    .then((response) => {
      console.log('📝 回复:\n');
      console.log(response);
      console.log('\n✅ 完成');
    })
    .catch((e) => {
      console.error('\n❌ 错误:', e.message);
    });
} else {
  console.log(`
用法:
  bun client.ts ask "你的问题"
  bun client.ts ask "问题" --model o1

选项:
  --model <model>  选择模型: GPT-4o, GPT-4o mini, o1, o3-mini

前置条件:
  1. 运行: ~/.claude/scripts/start-chrome-debug.sh
  2. 在 Chrome 中登录 chatgpt.com
`);
}
