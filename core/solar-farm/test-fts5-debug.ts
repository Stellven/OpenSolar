// Test FTS5 preprocessing
function preprocessFTS5Query(intent: string): string {
  const stopWords = new Set([
    '的', '了', '吗', '呢', '啊', '吧', '呀', '啦', '嘛', '哦', '哈',
    '我', '你', '他', '她', '它', '我们', '你们', '他们',
    '是', '在', '有', '和', '与', '或', '不', '没', '也', '都', '很', '太', '更', '最',
    '这', '那', '哪', '什么', '怎么', '为什么', '如何',
    '帮', '帮我', '给我', '让我', '请', '想', '要', '需要', '希望',
    '写', '做', '搞', '弄', '创建', '生成', '开发', '实现',
    '个', '些', '点', '下', '一', '二', '三', '四', '五'
  ]);

  const cleaned = intent.replace(/[，。！？、；：""''（）《》【】]/g, ' ');
  const tokens: string[] = [];
  const words = cleaned.split(/\s+/).filter(w => w.length > 0);

  for (const word of words) {
    if (stopWords.has(word.toLowerCase())) continue;
    if (/^[a-zA-Z]+$/.test(word)) {
      tokens.push(word);
      continue;
    }
    if (word.length >= 2) {
      tokens.push(word);
    }
  }

  if (tokens.length === 0) {
    const chars = cleaned.replace(/\s+/g, '');
    for (let i = 0; i < chars.length - 1; i++) {
      const bigram = chars.slice(i, i + 2);
      if (!/\s/.test(bigram)) {
        tokens.push(bigram);
      }
    }
  }

  const uniqueTokens = [...new Set(tokens)];
  return uniqueTokens.length > 0 ? uniqueTokens.join(' OR ') : intent;
}

// Test cases
const testCases = [
  "写个技术文档",
  "帮我写文档",
  "技术文档"
];

import Database from 'bun:sqlite';
const db = new Database('/Users/sihaoli/.solar/solar.db', { readonly: true });

for (const query of testCases) {
  const processed = preprocessFTS5Query(query);
  console.log(`\n原始查询: "${query}"`);
  console.log(`预处理后: "${processed}"`);
  
  // Test FTS5
  try {
    const results = db.query(`
      SELECT doc_id, rank
      FROM fts_unified_search
      WHERE fts_unified_search MATCH ?
        AND doc_type = 'skill_bank'
      ORDER BY rank
      LIMIT 3
    `).all(processed);
    
    console.log(`FTS5 结果: ${results.length} 条`);
    if (results.length > 0) {
      console.log(results);
    }
  } catch (e: any) {
    console.log(`FTS5 错误: ${e.message}`);
  }
}

db.close();
