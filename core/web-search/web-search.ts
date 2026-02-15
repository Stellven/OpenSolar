#!/usr/bin/env bun
/**
 * Web Search - WebSearch 工具的可靠替代方案
 *
 * 使用多种开放 API 进行搜索，避免反爬问题
 *
 * 用法: bun web-search.ts "搜索关键词"
 */

interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source: string;
}

// Wikipedia API 搜索
async function searchWikipedia(query: string): Promise<SearchResult[]> {
  const url = `https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=${encodeURIComponent(query)}&format=json&utf8=&srlimit=5`;

  try {
    const response = await fetch(url);
    const data = await response.json() as { query?: { search?: Array<{ title: string; snippet: string; pageid: number }> } };

    return (data.query?.search || []).map(item => ({
      title: item.title,
      url: `https://en.wikipedia.org/wiki/${encodeURIComponent(item.title.replace(/ /g, '_'))}`,
      snippet: item.snippet.replace(/<\/?span[^>]*>/g, ''),
      source: 'Wikipedia'
    }));
  } catch (error) {
    console.error('[Wikipedia] Search failed:', error);
    return [];
  }
}

// DuckDuckGo Instant Answer API
async function searchDuckDuckGo(query: string): Promise<SearchResult[]> {
  const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1`;

  try {
    const response = await fetch(url);
    const data = await response.json() as {
      AbstractText?: string;
      AbstractURL?: string;
      Heading?: string;
      RelatedTopics?: Array<{ Text?: string; FirstURL?: string }>;
    };

    const results: SearchResult[] = [];

    // 主要结果
    if (data?.AbstractText && data?.AbstractURL) {
      results.push({
        title: data.Heading || 'Summary',
        url: data.AbstractURL,
        snippet: data.AbstractText,
        source: 'DuckDuckGo'
      });
    }

    // 相关主题
    (data.RelatedTopics || []).slice(0, 5).forEach(topic => {
      if (topic.Text && topic.FirstURL) {
        results.push({
          title: topic.Text.split(' - ')[0] || 'Related',
          url: topic.FirstURL,
          snippet: topic.Text,
          source: 'DuckDuckGo'
        });
      }
    });

    return results;
  } catch (error) {
    console.error('[DuckDuckGo] Search failed:', error);
    return [];
  }
}

// Hacker News API (适合技术搜索)
async function searchHackerNews(query: string): Promise<SearchResult[]> {
  const url = `https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(query)}&hitsPerPage=5`;

  try {
    const response = await fetch(url);
    const data = await response.json() as { hits?: Array<{ title?: string; url?: string; objectID?: string; points?: number }> };

    return (data.hits || []).map(item => ({
      title: item.title || '',
      url: item.url || `https://news.ycombinator.com/item?id=${item.objectID}`,
      snippet: `Points: ${item.points || 0}`,
      source: 'HackerNews'
    }));
  } catch (error) {
    console.error('[HackerNews] Search failed:', error);
    return [];
  }
}

// 组合搜索
async function search(query: string): Promise<SearchResult[]> {
  console.error(`[Search] Searching for: "${query}"`);

  const [wiki, ddg, hn] = await Promise.all([
    searchWikipedia(query),
    searchDuckDuckGo(query),
    searchHackerNews(query)
  ]);

  // 合并结果，按来源分组
  const results: SearchResult[] = [];

  // DuckDuckGo 结果优先（通常是摘要）
  if (ddg.length > 0) {
    results.push(...ddg);
  }

  // 然后是 Wikipedia
  if (wiki.length > 0) {
    results.push(...wiki);
  }

  // 最后是 Hacker News（技术相关）
  if (hn.length > 0) {
    results.push(...hn);
  }

  return results.slice(0, 10);
}

function formatResults(results: SearchResult[]): string {
  if (results.length === 0) {
    return 'No results found.';
  }

  const lines: string[] = ['# Web Search Results\n'];

  results.forEach((result, index) => {
    lines.push(`## ${index + 1}. ${result.title}`);
    lines.push(`**URL**: ${result.url}`);
    lines.push(`**Source**: ${result.source}`);
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
Web Search - WebSearch 替代方案

用法:
  bun web-search.ts "搜索关键词" [选项]

选项:
  --json     输出 JSON 格式
  --help     显示帮助

数据源:
  - DuckDuckGo Instant Answer API
  - Wikipedia API
  - Hacker News Algolia API

示例:
  bun web-search.ts "AI agents"
  bun web-search.ts "machine learning" --json
`);
    process.exit(0);
  }

  let query = '';
  let jsonOutput = false;

  for (const arg of args) {
    if (arg === '--json') {
      jsonOutput = true;
    } else if (!arg.startsWith('--')) {
      query = arg;
    }
  }

  if (!query) {
    console.error('Error: No search query provided');
    process.exit(1);
  }

  try {
    const results = await search(query);

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
