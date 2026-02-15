#!/usr/bin/env bun
/**
 * Playwright Web Search - WebSearch 工具的替代方案
 *
 * 用法: bun playwright-search.ts "搜索关键词" [--engine google|bing|duckduckgo]
 */

const SEARCH_ENGINES = {
  google: {
    url: 'https://www.google.com/search?q=',
    selectors: {
      results: '#search .g',
      title: 'h3',
      link: 'a[href^="http"]',
      snippet: '[data-sncf]'
    }
  },
  bing: {
    url: 'https://www.bing.com/search?q=',
    selectors: {
      results: '.b_algo',
      title: 'h2',
      link: 'a[href^="http"]',
      snippet: '.b_caption p'
    }
  },
  duckduckgo: {
    url: 'https://duckduckgo.com/?q=',
    selectors: {
      results: '[data-testid="result"]',
      title: 'h2',
      link: 'a[href^="http"]',
      snippet: '[data-testid="result-snippet"]'
    }
  }
};

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source: string;
}

async function search(query: string, engine: keyof typeof SEARCH_ENGINES = 'google'): Promise<SearchResult[]> {
  const { chromium } = await import('playwright');
  const config = SEARCH_ENGINES[engine];

  console.error(`[Search] Using ${engine} to search: "${query}"`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  const page = await context.newPage();

  try {
    // 导航到搜索页面
    await page.goto(config.url + encodeURIComponent(query), {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    // 等待结果加载
    await page.waitForSelector(config.selectors.results, { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(1000); // 额外等待

    // 提取搜索结果
    const results = await page.evaluate((selectors) => {
      const items: Array<{ title: string; url: string; snippet: string }> = [];
      const resultElements = document.querySelectorAll(selectors.results);

      resultElements.forEach((el, index) => {
        if (index >= 10) return; // 最多 10 个结果

        const titleEl = el.querySelector(selectors.title);
        const linkEl = el.querySelector(selectors.link);
        const snippetEl = el.querySelector(selectors.snippet);

        if (titleEl && linkEl) {
          items.push({
            title: titleEl.textContent?.trim() || '',
            url: linkEl.getAttribute('href') || '',
            snippet: snippetEl?.textContent?.trim() || ''
          });
        }
      });

      return items;
    }, config.selectors);

    await browser.close();

    return results
      .filter(r => r.title && r.url)
      .map(r => ({
        ...r,
        source: engine
      }));

  } catch (error) {
    await browser.close();
    throw error;
  }
}

function formatResults(results: SearchResult[]): string {
  if (results.length === 0) {
    return 'No results found.';
  }

  const lines: string[] = ['# Web Search Results\n'];

  results.forEach((result, index) => {
    lines.push(`## ${index + 1}. ${result.title}`);
    lines.push(`**URL**: ${result.url}`);
    if (result.snippet) {
      lines.push(`**Snippet**: ${result.snippet}`);
    }
    lines.push('');
  });

  return lines.join('\n');
}

// 主函数
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === '--help' || args[0] === '-h') {
    console.log(`
Playwright Web Search - WebSearch 替代方案

用法:
  bun playwright-search.ts "搜索关键词" [选项]

选项:
  --engine <name>  搜索引擎 (google|bing|duckduckgo)，默认 google
  --json           输出 JSON 格式
  --help           显示帮助

示例:
  bun playwright-search.ts "AI agents"
  bun playwright-search.ts "人工智能" --engine bing --json
`);
    process.exit(0);
  }

  let query = '';
  let engine: keyof typeof SEARCH_ENGINES = 'google';
  let jsonOutput = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--engine' && args[i + 1]) {
      engine = args[i + 1] as keyof typeof SEARCH_ENGINES;
      i++;
    } else if (args[i] === '--json') {
      jsonOutput = true;
    } else if (!args[i].startsWith('--')) {
      query = args[i];
    }
  }

  if (!query) {
    console.error('Error: No search query provided');
    process.exit(1);
  }

  if (!SEARCH_ENGINES[engine]) {
    console.error(`Error: Unknown search engine "${engine}"`);
    console.error(`Available engines: ${Object.keys(SEARCH_ENGINES).join(', ')}`);
    process.exit(1);
  }

  try {
    const results = await search(query, engine);

    if (jsonOutput) {
      console.log(JSON.stringify(results, null, 2));
    } else {
      console.log(formatResults(results));
    }
  } catch (error) {
    console.error('Search failed:', error);
    process.exit(1);
  }
}

main();
