#!/usr/bin/env bun
/**
 * Smart Knowledge Sync - 智能知识同步服务
 *
 * 功能：
 * 1. 自动同步 Obsidian 笔记
 * 2. 调用老专家 (Gemini/GLM/DeepSeek) 提取知识
 * 3. 建立知识网络关联
 * 4. 支持 launchd 定时自动运行
 *
 * 使用：
 *   bun smart-sync.ts              # 同步所有
 *   bun smart-sync.ts --watch      # 持续监听
 *   bun smart-sync.ts --install    # 安装 launchd 服务
 *
 * @version 1.0.0
 * @created 2026-02-15
 */

import { Database } from 'bun:sqlite';
import { readdir, readFile, stat, watch } from 'fs/promises';
import { join, extname, basename } from 'path';
import { existsSync } from 'fs';
import { execSync } from 'child_process';

const DB_PATH = process.env.SOLAR_DB || `${process.env.HOME}/.solar/solar.db`;
const OBSIDIAN_VAULT = `${process.env.HOME}/Solar/solar know`;

// ============================================================
// 老专家调用 (融合方案: 规则 + LLM)
// ============================================================

interface ExpertResult {
  entities: Array<{ name: string; type: string; description: string }>;
  relations: Array<{ from: string; to: string; type: string; evidence: string }>;
  claims: Array<{ text: string; domain: string; confidence: number }>;
  summary: string;
  key_insights: string[];
  extraction_method: 'rule' | 'llm' | 'hybrid';  // 标记提取方式
}

/**
 * 复杂度评估 - 决定用规则还是LLM
 */
function assessComplexity(content: string): {
  score: number;
  reasons: string[];
  useLLM: boolean;
} {
  const reasons: string[] = [];
  let score = 0;

  // 1. 文档长度
  if (content.length > 2000) {
    score += 2;
    reasons.push('长文档');
  }

  // 2. 技术术语密度
  const techPattern = /\b(GPU|TPU|CPU|LLM|API|MCP|MoE|Transformer|Attention|Inference|Training)\b/gi;
  const techMatches = content.match(techPattern);
  if (techMatches && techMatches.length > 5) {
    score += 2;
    reasons.push(`技术术语多(${techMatches.length}个)`);
  }

  // 3. 数学/公式
  if (content.includes('$') || /\b\d+\s*[\+\-\*\/]\s*\d+/.test(content)) {
    score += 1;
    reasons.push('含数学公式');
  }

  // 4. 代码块
  if (content.includes('```')) {
    score += 1;
    reasons.push('含代码');
  }

  // 5. 多语言混排
  if (/[\u4e00-\u9fa5]/.test(content) && /[a-zA-Z]{10,}/.test(content)) {
    score += 1;
    reasons.push('中英混排');
  }

  return {
    score,
    reasons,
    useLLM: score >= 3  // 复杂度>=3 用LLM
  };
}

/**
 * LLM 老专家调用 - 真正的智能提取
 * 使用 openclaw CLI 调用
 */
async function callLLMExpert(content: string, sourceTitle: string): Promise<ExpertResult> {
  const prompt = '从以下文档中提取知识，返回纯JSON（不要用代码块包裹）：\n\n' +
    '文档: ' + sourceTitle + '\n' +
    content.substring(0, 3500) + '\n\n' +
    '返回格式: {"entities":[{"name":"xxx","type":"person|technology|concept|tool|organization","description":"简述"}],"claims":[{"text":"结论","confidence":0.8}],"summary":"摘要"}\n\n' +
    '注意：type要准确，技术术语不要标为person';

  try {
    // 使用 openclaw agent --local 调用
    const escapedPrompt = prompt.replace(/"/g, '\\"').replace(/\n/g, ' ');
    const result = execSync(
      `openclaw agent --local --agent main --message "${escapedPrompt}" 2>/dev/null`,
      { maxBuffer: 1024 * 1024, timeout: 60000 }
    ).toString().trim();

    // 提取 JSON
    const jsonMatch = result.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      throw new Error('无法从响应中提取 JSON');
    }

    const parsed = JSON.parse(jsonMatch[0]);

    // 🔧 类型修正层
    const correctedEntities = (parsed.entities || []).map((e: any) => {
      const techTerms = new Set([
        'Agent Workflow', 'Bandwidth Bound', 'Capacity Footprint', 'Catastrophic Forgetting',
        'Coding Agent', 'Compute Bound', 'Context Length', 'Diffusion Models',
        'Disaggregated Serving', 'Evolving Agents', 'Inference Engine', 'Language Model',
        'Memory Capacity', 'Neural Network', 'Operational Intensity', 'Pareto Frontier'
      ]);

      const techSuffixes = [
        'Agent', 'Agents', 'Model', 'Models', 'Network', 'Engine', 'System',
        'Framework', 'Architecture', 'Layer', 'Attention', 'Decoder', 'Encoder',
        'Training', 'Inference', 'Learning', 'Bound', 'Serving', 'Alignment', 'Memory'
      ];

      if (e.type === 'person') {
        if (techTerms.has(e.name)) {
          return { ...e, type: 'technology' };
        }
        for (const suffix of techSuffixes) {
          if (e.name.endsWith(' ' + suffix) || e.name === suffix) {
            return { ...e, type: 'technology' };
          }
        }
      }
      return e;
    });

    return {
      entities: correctedEntities,
      relations: parsed.relations || [],
      claims: parsed.claims || [],
      summary: parsed.summary || '',
      key_insights: parsed.key_insights || [],
      extraction_method: 'llm'
    };
  } catch (error) {
    console.log(`    ⚠️ LLM调用失败，降级到规则: ${(error as Error).message}`);
    return ruleBasedExtraction(content, sourceTitle);
  }
}

/**
 * 规则提取 - 快速、免费
 */
function ruleBasedExtraction(content: string, sourceTitle: string): ExpertResult {
  const defaultResult: ExpertResult = {
    entities: [],
    relations: [],
    claims: [],
    summary: '',
    key_insights: [],
    extraction_method: 'rule'
  };

  // 简单规则提取（不依赖外部调用）
  // 1. 提取可能的实体（人名、技术名词等）

  // 已知的技术术语（不应被识别为人名）
  const techTerms = new Set([
    'Pareto Frontier', 'Batch Size', 'Speculative Decoding', 'Crisp Specification',
    'Low Precision', 'Paradigm Shift', 'Machine Learning', 'Deep Learning',
    'Neural Network', 'Language Model', 'Knowledge Base', 'Inference Engine',
    'Training Data', 'Model Architecture', 'Attention Mechanism', 'Transform',
    'GPU', 'TPU', 'CPU', 'API', 'SDK', 'LLM', 'GPT', 'BERT', 'MoE', 'MCP',
    'Multi-Head', 'Self-Attention', 'Fine-Tuning', 'Pre-Training',
  ]);

  const entityPatterns = [
    // 技术概念：特定技术名词
    { pattern: /\b(Pareto\s+Frontier|Speculative\s+Decoding|Batch\s+Size|Crisp\s+Specification)\b/gi, type: 'concept' },
    // 技术概念：带技术后缀的术语
    { pattern: /\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Model|Network|Engine|System|Framework|Architecture|Layer|Attention|Decoder|Encoder|Training|Inference|Learning)))\b/g, type: 'technology' },
    // 人名：仅限明确的人名模式（如 Jeff Dean, Geoffrey Hinton）
    { pattern: /\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b/g, type: 'person', checkNotTech: true },
    // 中文技术
    { pattern: /(?:使用|基于|采用|利用|实现|优化)[「『"]?([^「」『』"\n]{2,20})[」』"]?/g, type: 'technology' },
    // 工具/缩写
    { pattern: /\b([A-Z]{2,}[A-Za-z]*)\b/g, type: 'tool' },
    // 中文概念
    { pattern: /「([^」]{2,20})」|『([^』]{2,20})』/g, type: 'concept' },
  ];

  const entities: ExpertResult['entities'] = [];

  // 提取实体
  for (const { pattern, type, checkNotTech } of entityPatterns) {
    const matches = content.matchAll(pattern);
    for (const match of matches) {
      const name = match[1] || match[2] || match[0];
      if (name && name.length > 1 && name.length < 50) {
        const trimmedName = name.trim();
        // 如果需要检查是否为技术术语
        if (checkNotTech && techTerms.has(trimmedName)) {
          continue; // 跳过已知技术术语
        }
        entities.push({
          name: trimmedName,
          type,
          description: `从 ${sourceTitle} 中提取`
        });
      }
    }
  }

  // 去重
  const seenNames = new Set<string>();
  const uniqueEntities = entities.filter(e => {
    if (seenNames.has(e.name)) return false;
    seenNames.add(e.name);
    return true;
  });

  // 2. 提取可能的结论（以"结论"、"所以"、"因此"开头的句子）
  const claimPatterns = [
    /(?:结论|总结|所以|因此|可见|综上)[：:，,]?\s*([^。\n]{10,200})/g,
    /(?:主要|核心|关键)(?:观点|发现|结论)[：:，,]?\s*([^。\n]{10,200})/g,
  ];

  const claims: ExpertResult['claims'] = [];
  for (const pattern of claimPatterns) {
    const matches = content.matchAll(pattern);
    for (const match of matches) {
      if (match[1]) {
        claims.push({
          text: match[1].trim(),
          domain: 'general',
          confidence: 0.7
        });
      }
    }
  }

  // 3. 生成摘要（前200字符）
  const summary = content.substring(0, 200).replace(/\n/g, ' ').trim();

  // 4. 提取关键洞察（标题和重点）
  const key_insights: string[] = [];
  const headingMatches = content.matchAll(/^#+\s+(.+)$/gm);
  for (const match of headingMatches) {
    if (match[1] && key_insights.length < 5) {
      key_insights.push(match[1].trim());
    }
  }

  return {
    entities: uniqueEntities.slice(0, 20),  // 最多20个实体
    relations: [],  // 暂不支持自动关系提取
    claims: claims.slice(0, 10),  // 最多10个结论
    summary,
    key_insights: key_insights.slice(0, 5),
    extraction_method: 'rule'
  };
}

/**
 * 融合提取 - 主入口
 * 策略：复杂度评估 → 规则/LLM路由 → 效果评估 → 降级
 */
async function callExpertForExtraction(content: string, sourceTitle: string): Promise<ExpertResult> {
  // Step 1: 复杂度评估
  const complexity = assessComplexity(content);
  console.log(`    复杂度: ${complexity.score} (${complexity.reasons.join(', ') || '简单'})`);

  // Step 2: 路由决策
  if (complexity.useLLM) {
    console.log(`    🤖 使用LLM老专家提取...`);
    const result = await callLLMExpert(content, sourceTitle);

    // Step 3: 效果评估 - 如果LLM效果差，降级到规则
    if (result.entities.length < 3) {
      console.log(`    ⚠️ LLM提取效果差(${result.entities.length}实体)，尝试规则补充...`);
      const ruleResult = ruleBasedExtraction(content, sourceTitle);

      // 融合：LLM结果 + 规则补充
      const existingNames = new Set(result.entities.map(e => e.name));
      const additionalEntities = ruleResult.entities.filter(e => !existingNames.has(e.name));

      return {
        ...result,
        entities: [...result.entities, ...additionalEntities.slice(0, 5)],
        extraction_method: 'hybrid'
      };
    }

    return result;
  } else {
    // 简单文档用规则
    console.log(`    ⚡ 使用规则提取...`);
    const result = ruleBasedExtraction(content, sourceTitle);

    // 如果规则效果差，降级到LLM
    if (result.entities.length < 3 && content.length > 500) {
      console.log(`    ⚠️ 规则提取效果差(${result.entities.length}实体)，降级到LLM...`);
      return callLLMExpert(content, sourceTitle);
    }

    return result;
  }
}

// ============================================================
// 智能同步引擎
// ============================================================

class SmartKnowledgeSync {
  private db: Database;

  constructor() {
    this.db = new Database(DB_PATH);
  }

  async syncDocument(filePath: string, content: string): Promise<{
    entities: number;
    relations: number;
    claims: number;
  }> {
    const title = basename(filePath, extname(filePath));

    // 1. 调用老专家提取知识
    console.log(`  🔍 分析: ${title}`);
    const knowledge = await callExpertForExtraction(content, title);

    // 2. 存入知识网络
    let entityCount = 0;
    let relationCount = 0;
    let claimCount = 0;

    // 存储实体
    const entityNames: string[] = [];
    for (const entity of knowledge.entities) {
      try {
        this.db.run(`
          INSERT INTO knowledge_entities (name, type, description, importance)
          VALUES (?, ?, ?, ?)
          ON CONFLICT(name) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            importance = MAX(excluded.importance, importance),
            updated_at = CURRENT_TIMESTAMP
        `, [entity.name, entity.type, entity.description || '', 0.6]);
        entityCount++;
        entityNames.push(entity.name);
      } catch (e) {
        // 忽略重复
      }
    }

    // 🔗 自动建立知识关联（核心：让孤立点变成网络）
    // 1. 同现关系：同一篇文章的实体建立 co_occurs_in 关系
    for (let i = 0; i < entityNames.length; i++) {
      for (let j = i + 1; j < entityNames.length; j++) {
        try {
          this.db.run(`
            INSERT OR IGNORE INTO knowledge_relations
            (from_entity, to_entity, relation_type, evidence, source_doc)
            VALUES (?, ?, 'co_occurs_in', ?, ?)
          `, [entityNames[i], entityNames[j], `同现于: ${title}`, filePath]);
          relationCount++;
        } catch (e) {
          // 忽略
        }
      }
    }

    // 2. 结论关联：结论与文章中的关键实体建立关系
    for (const claim of knowledge.claims) {
      if (!claim?.text) continue;  // 空值检查
      for (const entityName of entityNames.slice(0, 5)) { // 只关联前5个核心实体
        if (claim.text.includes(entityName)) {
          try {
            this.db.run(`
              INSERT OR IGNORE INTO knowledge_relations
              (from_entity, to_entity, relation_type, evidence, source_doc)
              VALUES (?, ?, 'supports_claim', ?, ?)
            `, [entityName, claim.text.substring(0, 50), `结论支持: ${claim.text.substring(0, 100)}`, filePath]);
            relationCount++;
          } catch (e) {
            // 忽略
          }
        }
      }
    }

    // 存储关系（老专家提取的显式关系）
    for (const rel of knowledge.relations) {
      try {
        this.db.run(`
          INSERT OR IGNORE INTO knowledge_relations
          (from_entity, to_entity, relation_type, evidence, source_doc)
          VALUES (?, ?, ?, ?, ?)
        `, [rel.from, rel.to, rel.type, rel.evidence || '', filePath]);
        relationCount++;
      } catch (e) {
        // 忽略重复
      }
    }

    // 存储结论
    for (const claim of knowledge.claims) {
      try {
        this.db.run(`
          INSERT INTO knowledge_claims
          (claim_text, domain, confidence, supporting_sources)
          VALUES (?, ?, ?, ?)
        `, [claim.text, claim.domain || 'general', claim.confidence || 0.7, JSON.stringify([filePath])]);
        claimCount++;
      } catch (e) {
        // 忽略重复
      }
    }

    return { entities: entityCount, relations: relationCount, claims: claimCount };
  }

  async syncVault(vaultPath: string): Promise<{
    total: number;
    entities: number;
    relations: number;
    claims: number;
  }> {
    const result = { total: 0, entities: 0, relations: 0, claims: 0 };

    if (!existsSync(vaultPath)) {
      console.log(`  ⚠️ Vault 不存在: ${vaultPath}`);
      return result;
    }

    // 扫描所有 markdown 文件
    const scanDir = async (dir: string): Promise<string[]> => {
      const files: string[] = [];
      const entries = await readdir(dir, { withFileTypes: true });

      for (const entry of entries) {
        const fullPath = join(dir, entry.name);
        if (entry.isDirectory() && !entry.name.startsWith('.')) {
          files.push(...await scanDir(fullPath));
        } else if (entry.isFile() && ['.md', '.markdown'].includes(extname(entry.name))) {
          files.push(fullPath);
        }
      }
      return files;
    };

    const files = await scanDir(vaultPath);
    result.total = files.length;

    console.log(`\n📚 同步 Obsidian Vault: ${files.length} 个文件`);

    for (const file of files) {
      // 检查是否已处理过
      const existing = this.db.query<{ hash: string }, [string]>(`
        SELECT content_hash FROM cortex_doc_hashes WHERE doc_path = ?
      `).get(file);

      const content = await readFile(file, 'utf-8');
      const hash = await this.hashContent(content);

      if (existing && existing.hash === hash) {
        console.log(`  ⏭️ 跳过 (未变更): ${basename(file)}`);
        continue;
      }

      // 同步文档
      const syncResult = await this.syncDocument(file, content);
      result.entities += syncResult.entities;
      result.relations += syncResult.relations;
      result.claims += syncResult.claims;

      // 更新哈希
      this.db.run(`
        INSERT INTO cortex_doc_hashes (doc_path, content_hash, synced_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(doc_path) DO UPDATE SET
          content_hash = excluded.content_hash,
          synced_at = CURRENT_TIMESTAMP
      `, [file, hash]);
    }

    return result;
  }

  private async hashContent(content: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(hashBuffer))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('')
      .substring(0, 16);
  }

  close(): void {
    this.db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--install')) {
    // 安装 launchd 服务
    const plistPath = `${process.env.HOME}/Library/LaunchAgents/com.solar.knowledge-sync.plist`;
    const plistContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.solar.knowledge-sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/bun</string>
        <string>${process.env.HOME}/.claude/core/cortex/smart-sync.ts</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/tmp/solar-knowledge-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/solar-knowledge-sync.err</string>
</dict>
</plist>`;

    await import('fs/promises').then(fs => fs.writeFile(plistPath, plistContent));
    console.log('✅ launchd 配置已创建');
    console.log('启动: launchctl load ~/Library/LaunchAgents/com.solar.knowledge-sync.plist');
    return;
  }

  // 执行同步
  console.log('╔════════════════════════════════════════════════════════════╗');
  console.log('║           Solar 智能知识同步 v1.0                           ║');
  console.log('╚════════════════════════════════════════════════════════════╝');

  const sync = new SmartKnowledgeSync();

  try {
    const result = await sync.syncVault(OBSIDIAN_VAULT);

    console.log('\n📊 同步结果:');
    console.log(`  📄 文档: ${result.total}`);
    console.log(`  🏷️ 实体: ${result.entities}`);
    console.log(`  🔗 关系: ${result.relations}`);
    console.log(`  💡 结论: ${result.claims}`);
  } finally {
    sync.close();
  }
}

main();
