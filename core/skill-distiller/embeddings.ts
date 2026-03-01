/**
 * Skill Embeddings
 * 技能向量嵌入支持（P1）
 *
 * 使用 Brain Router 的嵌入功能为技能生成向量
 */

import type { Skill } from './schema';

// 嵌入维度（与 OpenAI text-embedding-3-small 对齐）
const EMBEDDING_DIMENSION = 1536;

// 本地嵌入缓存
const embeddingCache = new Map<string, number[]>();

/**
 * 生成文本嵌入
 * 优先使用远程 API，失败时使用本地哈希
 */
export async function generateEmbedding(text: string): Promise<number[]> {
  // 检查缓存
  const cacheKey = text.slice(0, 100);
  if (embeddingCache.has(cacheKey)) {
    return embeddingCache.get(cacheKey)!;
  }

  try {
    // 尝试调用 Brain Router 嵌入 API
    const response = await fetch('http://localhost:3000/api/brain-router/embeddings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input: text }),
      signal: AbortSignal.timeout(5000)
    });

    if (response.ok) {
      const data = await response.json();
      const embedding = data.embedding || data.data?.[0]?.embedding;
      if (embedding) {
        embeddingCache.set(cacheKey, embedding);
        return embedding;
      }
    }
  } catch {
    // API 不可用，使用本地方案
  }

  // 本地方案：使用简单的文本哈希生成伪向量
  return generateLocalEmbedding(text);
}

/**
 * 本地嵌入生成（改进版 - 基于 TF-IDF 风格）
 * 使用更好的文本特征提取
 */
function generateLocalEmbedding(text: string): number[] {
  const embedding: number[] = [];

  // 预处理
  const normalizedText = text.toLowerCase();
  const tokens = normalizedText.split(/[\s\-_]+|(?=[A-Z])/).filter(t => t.length >= 2);

  // 技术关键词权重
  const techKeywords = [
    'python', 'javascript', 'typescript', 'react', 'vue', 'angular', 'node', 'nodejs',
    'kubernetes', 'k8s', 'docker', 'terraform', 'aws', 'azure', 'gcp',
    'api', 'rest', 'graphql', 'grpc', 'http', 'json', 'xml',
    'sql', 'nosql', 'postgres', 'mysql', 'mongodb', 'redis',
    'test', 'testing', 'unit', 'e2e', 'integration',
    'security', 'auth', 'oauth', 'jwt', 'encryption',
    'performance', 'optimization', 'cache', 'async',
    'git', 'github', 'gitlab', 'ci', 'cd', 'pipeline',
    'debug', 'error', 'exception', 'log', 'trace',
    'design', 'pattern', 'architecture', 'refactor',
    'ai', 'ml', 'llm', 'rag', 'embedding', 'vector'
  ];

  // 为每个维度生成特征
  for (let i = 0; i < EMBEDDING_DIMENSION; i++) {
    let sum = 0;
    const seed = i * 0.618033988749895; // 黄金比例

    // 基础特征：词频
    for (let j = 0; j < tokens.length; j++) {
      const token = tokens[j];
      const charSum = token.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
      const posWeight = 1 / (1 + j * 0.1); // 位置权重
      const techBoost = techKeywords.includes(token) ? 2.0 : 1.0;

      sum += Math.sin(charSum * seed * 0.001) * posWeight * techBoost;
    }

    // 添加技术关键词匹配特征
    for (const kw of techKeywords) {
      if (normalizedText.includes(kw)) {
        const kwHash = kw.split('').reduce((s, c) => s + c.charCodeAt(0), 0);
        sum += Math.cos(kwHash * seed * 0.001) * 0.5;
      }
    }

    embedding.push(sum / Math.max(tokens.length, 1));
  }

  // 归一化
  const norm = Math.sqrt(embedding.reduce((sum, v) => sum + v * v, 0)) || 1;
  return embedding.map(v => v / norm);
}

/**
 * 计算余弦相似度
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;

  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

/**
 * 为技能生成嵌入文本
 */
export function getSkillEmbeddingText(skill: Skill): string {
  const parts = [
    skill.name,
    skill.description,
    ...(skill.trigger_keywords || []),
    ...(skill.tags || [])
  ];
  return parts.filter(Boolean).join(' ');
}

/**
 * 批量生成技能嵌入
 */
export async function batchGenerateEmbeddings(
  skills: Skill[]
): Promise<Map<string, number[]>> {
  const results = new Map<string, number[]>();

  for (const skill of skills) {
    const text = getSkillEmbeddingText(skill);
    const embedding = await generateEmbedding(text);
    results.set(skill.skill_id, embedding);

    // 避免频繁调用
    await new Promise(resolve => setTimeout(resolve, 50));
  }

  return results;
}

/**
 * 语义搜索技能
 */
export async function semanticSearch(
  query: string,
  skills: Skill[],
  topK: number = 5
): Promise<{ skill: Skill; score: number }[]> {
  // 生成查询向量
  const queryEmbedding = await generateEmbedding(query);

  // 计算相似度
  const scores: { skill: Skill; score: number }[] = [];

  for (const skill of skills) {
    const text = getSkillEmbeddingText(skill);
    const skillEmbedding = await generateEmbedding(text);
    const score = cosineSimilarity(queryEmbedding, skillEmbedding);
    scores.push({ skill, score });
  }

  // 排序返回 topK
  return scores
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);
}
