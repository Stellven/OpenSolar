/**
 * Skill-RAG: Playbook Matcher
 *
 * 意图→skill_bank 检索（关键词匹配+q_value排序+FTS5兜底）
 *
 * Part of Step 2: Skill-RAG Plan A
 * @version 1.0.0
 * @created 2026-02-24
 */

import Database from 'bun:sqlite';
import { homedir } from 'os';
import { join } from 'path';

const DB_PATH = join(homedir(), '.solar', 'solar.db');

// ============================================================
// 类型定义
// ============================================================

export interface PlaybookMatch {
  skill_id: string;
  name: string;
  description: string;
  llm_prompt_template: string;
  parameters: string[];        // {{param}} names extracted from template
  trigger_keywords: string[];
  q_value: number;
  match_score: number;         // Combined score: kw*0.5 + fts*0.2 + desc*0.3 (retrieval quality)
  kw_score: number;            // Keyword overlap score [0-1]
  fts_score: number;           // FTS5 relevance score [0-1], 0 if no FTS5 match
  desc_score: number;          // Description/name text similarity score [0-1]
  match_method: 'keyword' | 'fts5' | 'description' | 'hybrid';
  success_count: number;
  failure_count: number;
}

export interface MatchResult {
  query: string;
  matches: PlaybookMatch[];
  total_candidates: number;
  elapsed_ms: number;
}

// ============================================================
// 工具函数
// ============================================================

/**
 * Extract {{parameter}} names from a template string
 */
export function extractParamNames(template: string): string[] {
  const matches = template.match(/\{\{(\w+)\}\}/g);
  if (!matches) return [];
  return [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))];
}

/**
 * Calculate keyword overlap score between user intent and trigger keywords
 * Returns 0-1: proportion of keywords found in intent
 */
function keywordScore(intent: string, keywords: string[]): number {
  if (!keywords || keywords.length === 0) return 0;

  const intentLower = intent.toLowerCase();
  let matchCount = 0;

  for (const kw of keywords) {
    if (intentLower.includes(kw.toLowerCase())) {
      matchCount++;
    }
  }

  return matchCount / keywords.length;
}

/**
 * Preprocess user intent for FTS5 query
 * Extracts keywords by removing stop words and common verbs
 * Returns FTS5 query string with OR-separated keywords
 */
function preprocessFTS5Query(intent: string): string {
  // Chinese stop words (common particles, auxiliaries, and action verbs)
  const stopWords = new Set([
    '的', '了', '吗', '呢', '啊', '吧', '呀', '啦', '嘛', '哦', '哈',
    '我', '你', '他', '她', '它', '我们', '你们', '他们',
    '是', '在', '有', '和', '与', '或', '不', '没', '也', '都', '很', '太', '更', '最',
    '这', '那', '哪', '什么', '怎么', '为什么', '如何',
    '帮', '帮我', '给我', '让我', '请', '想', '要', '需要', '希望',
    '写', '做', '搞', '弄', '创建', '生成', '开发', '实现',
    '个', '些', '点', '下', '一', '二', '三', '四', '五'
  ]);

  // Remove punctuation
  const cleaned = intent.replace(/[，。！？、；：""''（）《》【】]/g, '');

  // Extract tokens (2+ char sequences are preferred)
  const tokens: string[] = [];

  // For mixed Chinese/English text, process character by character
  let i = 0;
  while (i < cleaned.length) {
    const char = cleaned[i];

    // Skip whitespace
    if (/\s/.test(char)) {
      i++;
      continue;
    }

    // English word: extract complete word
    if (/[a-zA-Z]/.test(char)) {
      let word = '';
      while (i < cleaned.length && /[a-zA-Z]/.test(cleaned[i])) {
        word += cleaned[i];
        i++;
      }
      if (!stopWords.has(word.toLowerCase())) {
        tokens.push(word);
      }
      continue;
    }

    // Chinese character: extract 2+ char sequences
    if (/[\u4e00-\u9fa5]/.test(char)) {
      // Try to extract 2-char sequence first
      if (i + 1 < cleaned.length) {
        const twoChar = cleaned.slice(i, i + 2);
        // Skip if it's a stop word
        if (stopWords.has(twoChar)) {
          i += 2;
          continue;
        }
        tokens.push(twoChar);
        i += 2;
      } else {
        // Single char at end, skip if stop word
        if (!stopWords.has(char)) {
          tokens.push(char);
        }
        i++;
      }
      continue;
    }

    // Other characters (numbers, symbols), skip
    i++;
  }

  // If no tokens extracted, fall back to bigrams
  if (tokens.length === 0) {
    const chars = cleaned.replace(/\s+/g, '');
    for (let i = 0; i < chars.length - 1; i++) {
      const bigram = chars.slice(i, i + 2);
      if (!/\s/.test(bigram)) {
        tokens.push(bigram);
      }
    }
  }

  // Deduplicate and join with OR
  const uniqueTokens = [...new Set(tokens)];

  // FTS5 query: OR-separated keywords
  return uniqueTokens.length > 0 ? uniqueTokens.join(' OR ') : intent;
}

/**
 * Calculate text similarity between intent and skill name/description
 * Uses character-level and bigram overlap (works for Chinese without tokenizer)
 * Returns 0-1
 */
function descriptionScore(intent: string, name: string, description: string): number {
  if (!intent || (!name && !description)) return 0;

  const intentLower = intent.toLowerCase();
  const target = `${name} ${description}`.toLowerCase();

  // 1. Character overlap: how many unique intent chars appear in target
  const intentChars = [...new Set(intentLower.replace(/\s+/g, ''))];
  if (intentChars.length === 0) return 0;
  let charHits = 0;
  for (const ch of intentChars) {
    if (target.includes(ch)) charHits++;
  }
  const charScore = charHits / intentChars.length;

  // 2. Bigram overlap: how many intent bigrams appear in target
  const makeBigrams = (s: string): Set<string> => {
    const clean = s.replace(/\s+/g, '');
    const set = new Set<string>();
    for (let i = 0; i < clean.length - 1; i++) {
      set.add(clean.slice(i, i + 2));
    }
    return set;
  };
  const intentBigrams = makeBigrams(intentLower);
  const targetBigrams = makeBigrams(target);
  if (intentBigrams.size === 0) return charScore * 0.5;
  let bigramHits = 0;
  for (const bg of intentBigrams) {
    if (targetBigrams.has(bg)) bigramHits++;
  }
  const bigramScore = bigramHits / intentBigrams.size;

  // 3. Substring bonus: if intent appears directly in name or description
  const substringBonus = target.includes(intentLower) ? 0.3 :
    name.toLowerCase().includes(intentLower) ? 0.4 : 0;

  // Weighted combination, capped at 1.0
  const raw = charScore * 0.3 + bigramScore * 0.5 + substringBonus * 0.2;

  // Apply threshold: below 0.3 is noise for Chinese (too many common chars)
  return raw < 0.3 ? 0 : Math.min(raw, 1.0);
}

// ============================================================
// 核心匹配
// ============================================================

/**
 * Main matching function: intent → skill_bank playbooks
 *
 * Algorithm (Phase 3 三通道版):
 *   1. Load all skill_bank entries with templates
 *   2. Calculate 3 parallel scores:
 *      - Keyword overlap (kw_score)
 *      - FTS5 search (fts_score)
 *      - Description text matching (desc_score) - 新增
 *   3. Merge results: keyword + FTS5 + description 去重
 *   4. Gate: kwScore > 0 || ftsScore > 0 || descScore > 0 (任一通道命中即入选)
 *   5. Combined score: kwScore * 0.5 + ftsScore * 0.2 + descScore * 0.3
 *   6. Return top-K sorted by combined score
 *
 * 关键改进 (vs Phase 2):
 *   - 新增 description 通道：字符重叠 + bigram 匹配 + 子串加成
 *   - 解决 FTS5 中文分词问题 (unicode61 不支持 CJK 边界)
 *   - 调整权重: kw 0.6→0.5, fts 0.4→0.2, desc 新增 0.3
 *   - 扩展 match_method: 'keyword' | 'fts5' | 'description' | 'hybrid'
 */
export function matchPlaybooks(intent: string, topK: number = 5): MatchResult {
  const start = Date.now();
  const db = new Database(DB_PATH, { readonly: true });

  try {
    // Step 1: Load all skill_bank entries with templates
    const rows = db.query(`
      SELECT skill_id, name, description, llm_prompt_template,
             trigger_keywords, q_value, success_count, failure_count
      FROM sys_skill_bank
      WHERE length(llm_prompt_template) > 0
      ORDER BY q_value DESC
    `).all() as any[];

    // Step 2: Keyword + Description scoring for all entries
    const kwMap = new Map<string, { row: any; keywords: string[]; kwScore: number; descScore: number }>();
    for (const row of rows) {
      let keywords: string[] = [];
      try { keywords = JSON.parse(row.trigger_keywords || '[]'); } catch { keywords = []; }
      const kwScore = keywordScore(intent, keywords);
      const dScore = descriptionScore(intent, row.name, row.description);
      kwMap.set(row.skill_id, { row, keywords, kwScore, descScore: dScore });
    }

    // Step 3: FTS5 search IN PARALLEL (始终运行，不再是 fallback)
    const ftsScoreMap = new Map<string, number>();
    try {
      // Preprocess query for FTS5 (extract keywords from Chinese text)
      const ftsQuery = preprocessFTS5Query(intent);

      const ftsRows = db.query(`
        SELECT doc_id, rank
        FROM fts_unified_search
        WHERE fts_unified_search MATCH ?
          AND doc_type = 'skill_bank'
        ORDER BY rank
        LIMIT ?
      `).all(ftsQuery, topK * 3) as any[];

      if (ftsRows.length > 0) {
        // Normalize FTS5 rank to [0-1] (rank is negative, more negative = better)
        const ranks = ftsRows.map(r => Math.abs(r.rank as number));
        const maxRank = Math.max(...ranks, 1);
        for (const ftsRow of ftsRows) {
          const normalizedScore = 1 - (Math.abs(ftsRow.rank as number) / (maxRank + 1));
          ftsScoreMap.set(ftsRow.doc_id as string, Math.max(normalizedScore, 0.1));
        }
      }
    } catch {
      // FTS5 query might fail on malformed input, that's ok
    }

    // Step 4: Merge and score candidates
    const candidates: PlaybookMatch[] = [];

    for (const [skillId, entry] of kwMap) {
      const { row, keywords, kwScore, descScore } = entry;
      const ftsScore = ftsScoreMap.get(skillId) || 0;
      const qValue = row.q_value || 0.5;

      // Gate: 至少有一种匹配方式命中
      if (kwScore > 0 || ftsScore > 0 || descScore > 0) {
        const combined = kwScore * 0.5 + ftsScore * 0.2 + descScore * 0.3;
        const method: 'keyword' | 'fts5' | 'description' | 'hybrid' =
          (kwScore > 0 ? 1 : 0) + (ftsScore > 0 ? 1 : 0) + (descScore > 0 ? 1 : 0) > 1 ? 'hybrid' :
          kwScore > 0 ? 'keyword' :
          ftsScore > 0 ? 'fts5' : 'description';

        candidates.push({
          skill_id: row.skill_id,
          name: row.name,
          description: row.description,
          llm_prompt_template: row.llm_prompt_template,
          parameters: extractParamNames(row.llm_prompt_template),
          trigger_keywords: keywords,
          q_value: qValue,
          match_score: combined,
          kw_score: kwScore,
          fts_score: ftsScore,
          desc_score: descScore,
          match_method: method,
          success_count: row.success_count || 0,
          failure_count: row.failure_count || 0
        });
      }
    }

    // Step 5: Check FTS5 results that might not be in kwMap (edge case: orphan FTS5 matches)
    for (const [docId, ftsScore] of ftsScoreMap) {
      if (!kwMap.has(docId)) {
        // FTS5 found a skill not in main query (shouldn't happen, but be safe)
        const skill = db.query(`
          SELECT skill_id, name, description, llm_prompt_template,
                 trigger_keywords, q_value, success_count, failure_count
          FROM sys_skill_bank WHERE skill_id = ?
        `).get(docId) as any;

        if (skill && skill.llm_prompt_template) {
          let keywords: string[] = [];
          try { keywords = JSON.parse(skill.trigger_keywords || '[]'); } catch {}
          candidates.push({
            skill_id: skill.skill_id,
            name: skill.name,
            description: skill.description,
            llm_prompt_template: skill.llm_prompt_template,
            parameters: extractParamNames(skill.llm_prompt_template),
            trigger_keywords: keywords,
            q_value: skill.q_value || 0.5,
            match_score: ftsScore * 0.4,
            kw_score: 0,
            fts_score: ftsScore,
            desc_score: 0,
            match_method: 'fts5',
            success_count: skill.success_count || 0,
            failure_count: skill.failure_count || 0
          });
        }
      }
    }

    // Sort by combined score descending
    candidates.sort((a, b) => b.match_score - a.match_score);

    return {
      query: intent,
      matches: candidates.slice(0, topK),
      total_candidates: rows.length,
      elapsed_ms: Date.now() - start
    };
  } finally {
    db.close();
  }
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log(`
Skill-RAG: Playbook Matcher v1.0

用法:
  bun playbook-matcher.ts <intent>     # 检索匹配的 playbook
  bun playbook-matcher.ts --stats      # 查看 skill_bank 统计

示例:
  bun playbook-matcher.ts "代码有bug，报错了"
  bun playbook-matcher.ts "帮我review这段代码"
  bun playbook-matcher.ts "性能很慢需要优化"
`);
    process.exit(0);
  }

  if (args[0] === '--stats') {
    const db = new Database(DB_PATH, { readonly: true });
    const total = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank').get() as any).c;
    const withTemplate = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE length(llm_prompt_template) > 0').get() as any).c;
    const used = (db.query('SELECT COUNT(*) as c FROM sys_skill_bank WHERE success_count > 0 OR failure_count > 0').get() as any).c;
    const avgQ = (db.query('SELECT AVG(q_value) as avg FROM sys_skill_bank').get() as any).avg;
    db.close();

    console.log(`\n📊 sys_skill_bank 统计:`);
    console.log(`  总条目: ${total}`);
    console.log(`  有模板: ${withTemplate}`);
    console.log(`  被使用过: ${used}`);
    console.log(`  平均 q_value: ${avgQ?.toFixed(3) || 'N/A'}`);
    console.log();
    process.exit(0);
  }

  const intent = args.join(' ');
  const result = matchPlaybooks(intent);

  console.log(`\n🔍 Playbook 检索: "${intent}"`);
  console.log(`   候选池: ${result.total_candidates} | 匹配: ${result.matches.length} | 耗时: ${result.elapsed_ms}ms\n`);

  if (result.matches.length === 0) {
    console.log('   ❌ 无匹配 playbook\n');
  } else {
    for (const m of result.matches) {
      console.log(`   ${m.match_method === 'keyword' ? '🎯' : '🔎'} [${m.match_score.toFixed(2)}] ${m.name} (${m.skill_id})`);
      console.log(`      q_value=${m.q_value} | 成功=${m.success_count} 失败=${m.failure_count}`);
      console.log(`      评分: kw=${m.kw_score.toFixed(2)} fts=${m.fts_score.toFixed(2)} desc=${m.desc_score.toFixed(2)} | 方法=${m.match_method}`);
      console.log(`      关键词: ${m.trigger_keywords.join(', ')}`);
      console.log(`      参数: ${m.parameters.length > 0 ? m.parameters.map(p => `{{${p}}}`).join(', ') : '无'}`);
      console.log(`      模板: ${m.llm_prompt_template.substring(0, 80)}...`);
      console.log();
    }
  }
}
