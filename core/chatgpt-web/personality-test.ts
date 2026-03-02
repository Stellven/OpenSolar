#!/usr/bin/env bun
/**
 * ChatGPT 人格对比测试
 * 用不同的人格设定询问同一个问题，对比输出差异
 */

import puppeteer from 'puppeteer-core';

// 人格定义 (完整 D&D KNOBS - 简化版)
const PERSONALITIES = {
  // 审判官 - 高质疑、严谨
  judge: {
    name: '审判官',
    color: '🔴',
    system: `请用批判性思维回答。KNOBS: rigor=5, skepticism=5, explore=1, risk=5
要求: 先指出问题和风险，再给建议。对每个观点问"证据是什么？"。关注边界情况和失败模式。`,
  },

  // 创想家 - 高探索、创意
  creator: {
    name: '创想家',
    color: '🟢',
    system: `请用创意思维回答。KNOBS: rigor=2, skepticism=1, explore=5, risk=2
要求: 提供多种创新方案，包括大胆想法。不要拘泥于传统做法，鼓励跳出框框思考。`,
  },

  // 稳健派 - 平衡、严谨
  verifier: {
    name: '稳健派',
    color: '🔵',
    system: `请用严谨方式回答。KNOBS: rigor=4, skepticism=4, explore=2, risk=4
要求: 提供完整分析和风险评估，考虑边界情况。给出可验证的建议和测试方案。`,
  },

  // 建设者 - 务实、执行
  builder: {
    name: '建设者',
    color: '🟡',
    system: `请用务实方式回答。KNOBS: rigor=3, skepticism=2, explore=3, risk=2, decide=5
要求: 直接给出可执行步骤和代码示例。避免过度设计，专注快速落地。`,
  },

  // 默认 - 无人格
  default: {
    name: '默认GPT',
    color: '⚪',
    system: null,
  },
};

async function connectToChrome() {
  const browser = await puppeteer.connect({
    browserURL: 'http://localhost:9222',
    defaultViewport: null,
  });
  return browser;
}

async function askWithPersonality(
  page: puppeteer.Page,
  question: string,
  personality: (typeof PERSONALITIES)[keyof typeof PERSONALITIES]
): Promise<string> {
  // 构建带人格的问题 - 用清晰的角色扮演方式
  const fullPrompt = personality.system
    ? `【角色设定】${personality.system}

【问题】${question}

请按照上述角色设定来回答问题。`
    : question;

  // 清空输入框
  const input = await page.$('div[contenteditable="true"]');
  if (!input) throw new Error('找不到输入框');

  await input.click();
  await page.keyboard.down('Meta');
  await page.keyboard.press('a');
  await page.keyboard.up('Meta');

  // 输入问题
  await page.keyboard.type(fullPrompt, { delay: 5 });
  await page.keyboard.press('Enter');

  // 等待回复
  await new Promise((r) => setTimeout(r, 3000));

  try {
    await page.waitForSelector('button[aria-label="停止生成"]', { timeout: 5000 });
    await page.waitForSelector('button[aria-label="停止生成"]', {
      hidden: true,
      timeout: 60000,
    });
  } catch {}

  await new Promise((r) => setTimeout(r, 1500));

  // 获取回复
  const responses = await page.$$('div.markdown');
  if (responses.length === 0) return '无回复';

  const lastResponse = responses[responses.length - 1];
  const text = await lastResponse.evaluate((el) => el.textContent);

  // 开始新对话（清空上下文）
  await page.keyboard.down('Meta');
  await page.keyboard.press('o'); // Cmd+O 新对话
  await page.keyboard.up('Meta');
  await new Promise((r) => setTimeout(r, 1000));

  return text || '';
}

async function main() {
  const question = process.argv[2] || '如何设计一个高并发的用户认证系统？';

  console.log('═══════════════════════════════════════════════════════════');
  console.log('        ChatGPT 人格对比测试');
  console.log('═══════════════════════════════════════════════════════════');
  console.log(`\n📝 测试问题: "${question}"\n`);

  console.log('🤖 连接到 Chrome...');
  const browser = await connectToChrome();
  const pages = await browser.pages();

  let page = pages.find((p) => p.url().includes('chatgpt.com'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://chatgpt.com', { waitUntil: 'networkidle2' });
  }

  const results: { name: string; color: string; response: string }[] = [];

  // 测试每个人格
  for (const [key, personality] of Object.entries(PERSONALITIES)) {
    console.log(`\n${personality.color} 测试: ${personality.name}...`);

    try {
      const response = await askWithPersonality(page, question, personality);
      results.push({
        name: personality.name,
        color: personality.color,
        response: response.slice(0, 500), // 截断
      });
      console.log(`   ✅ 完成 (${response.length} 字符)`);
    } catch (e: any) {
      console.log(`   ❌ 失败: ${e.message}`);
      results.push({
        name: personality.name,
        color: personality.color,
        response: `错误: ${e.message}`,
      });
    }

    // 等待一下避免太快
    await new Promise((r) => setTimeout(r, 2000));
  }

  await browser.disconnect();

  // 输出对比结果
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('        对比结果');
  console.log('═══════════════════════════════════════════════════════════\n');

  for (const result of results) {
    console.log(`${result.color} 【${result.name}】`);
    console.log('─'.repeat(50));
    console.log(result.response);
    console.log('\n');
  }
}

main().catch(console.error);
