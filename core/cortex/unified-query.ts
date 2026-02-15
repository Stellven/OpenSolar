/**
 * Unified Query - 统一知识查询入口
 *
 * 整合 Cortex Query v0.2 + Knowledge Query
 *
 * 用法:
 *   bun unified-query.ts search "memory architecture" 10
 *   bun unified-query.ts evidence "AI Agent"          # 需要 evidence_pack
 *   bun unified-query.ts graph "MoE"                  # 知识图谱
 *   bun unified-query.ts all "GPU"                    # 全部来源
 *   bun unified-query.ts stats                        # 统计信息
 *
 * @version 1.0.0
 */

import { CortexQuery, CortexQueryParams, CortexQueryResult } from './cortex-query';
import { Database } from 'bun:sqlite';
import { homedir } from 'os';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// 类型定义
// ============================================================

export type QueryMode = 'cortex' | 'knowledge' | 'all';

export interface UnifiedQueryParams {
  q: string;
  k?: number;
  mode?: QueryMode;
  need_evidence?: boolean;
  need_graph?: boolean;
  gate_policy?: 'loose' | 'strict' | 'none';
  min_score?: number;
}

export interface UnifiedQueryResult {
  // Cortex 结果
  cortex?: CortexQueryResult;

  // Knowledge Graph 结果
  knowledge?: {
    entities: KnowledgeEntity[];
    relations: KnowledgeRelation[];
    claims: KnowledgeClaim[];
  };

  // 汇总
  summary: {
    total_sources: number;
    cortex_hits: number;
    knowledge_entities: number;
    knowledge_claims: number;
    latency_ms: number;
  };
}

interface KnowledgeEntity {
  name: string;
  type: string;
  description: string;
  importance: number;
}

interface KnowledgeRelation {
  from_entity: string;
  to_entity: string;
  relation_type: string;
  evidence: string;
}

interface KnowledgeClaim {
  claim_text: string;
  domain: string;
  confidence: number;
  supporting_sources: string[];
}

// ============================================================
// UnifiedQuery 类
// ============================================================

export class UnifiedQuery {
  private cortexQuery: CortexQuery;
  private db: Database;

  constructor() {
    this.cortexQuery = new CortexQuery();
    this.db = db;
  }

  /**
   * 统一查询入口
   */
  async query(params: UnifiedQueryParams): Promise<UnifiedQueryResult> {
    const startTime = Date.now();
    const k = params.k || 10;
    const mode = params.mode || 'all';

    const result: UnifiedQueryResult = {
      summary: {
        total_sources: 0,
        cortex_hits: 0,
        knowledge_entities: 0,
        knowledge_claims: 0,
        latency_ms: 0
      }
    };

    // 并行查询两个系统
    const queries: Promise<void>[] = [];

    // Cortex Query
    if (mode === 'all' || mode === 'cortex') {
      queries.push(this.queryCortex(params, result));
    }

    // Knowledge Query
    if (mode === 'all' || mode === 'knowledge') {
      queries.push(this.queryKnowledge(params, result));
    }

    await Promise.all(queries);

    // 汇总
    result.summary.cortex_hits = result.cortex?.hits?.length || 0;
    result.summary.knowledge_entities = result.knowledge?.entities?.length || 0;
    result.summary.knowledge_claims = result.knowledge?.claims?.length || 0;
    result.summary.total_sources = result.summary.cortex_hits +
                                    result.summary.knowledge_entities +
                                    result.summary.knowledge_claims;
    result.summary.latency_ms = Date.now() - startTime;

    return result;
  }

  /**
   * Cortex 子系统查询
   */
  private async queryCortex(
    params: UnifiedQueryParams,
    result: UnifiedQueryResult
  ): Promise<void> {
    try {
      const cortexParams: CortexQueryParams = {
        q: params.q,
        k: params.k || 10,
        gate_policy: params.gate_policy || 'loose',
        min_score: params.min_score,
        need: params.need_evidence ? ['snippets', 'evidence'] : ['snippets']
      };

      result.cortex = await this.cortexQuery.query(cortexParams);
    } catch (e) {
      console.error('Cortex query failed:', e);
    }
  }

  /**
   * Knowledge 子系统查询
   */
  private async queryKnowledge(
    params: UnifiedQueryParams,
    result: UnifiedQueryResult
  ): Promise<void> {
    try {
      const keyword = `%${params.q}%`;
      const k = params.k || 10;

      // 查询实体
      const entities = this.db.query(`
        SELECT name, type, description, importance
        FROM knowledge_entities
        WHERE name LIKE ? OR description LIKE ?
        ORDER BY importance DESC
        LIMIT ?
      `).all(keyword, keyword, k) as KnowledgeEntity[];

      // 查询结论
      const claims = this.db.query(`
        SELECT claim_text, domain, confidence, supporting_sources
        FROM knowledge_claims
        WHERE claim_text LIKE ?
        ORDER BY confidence DESC
        LIMIT ?
      `).all(keyword, k) as any[];

      const parsedClaims: KnowledgeClaim[] = claims.map(c => ({
        claim_text: c.claim_text,
        domain: c.domain,
        confidence: c.confidence,
        supporting_sources: JSON.parse(c.supporting_sources || '[]')
      }));

      // 查询关系 (如果需要图谱)
      let relations: KnowledgeRelation[] = [];
      if (params.need_graph) {
        relations = this.db.query(`
          SELECT from_entity, to_entity, relation_type, evidence
          FROM knowledge_relations
          WHERE from_entity LIKE ? OR to_entity LIKE ?
          LIMIT ?
        `).all(keyword, keyword, k * 2) as KnowledgeRelation[];
      }

      result.knowledge = {
        entities,
        relations,
        claims: parsedClaims
      };
    } catch (e) {
      console.error('Knowledge query failed:', e);
    }
  }

  /**
   * 格式化输出
   */
  formatOutput(result: UnifiedQueryResult): string {
    const lines: string[] = [];

    lines.push(`\n🔍 统一查询结果 (${result.summary.latency_ms}ms)`);
    lines.push(`   来源: Cortex ${result.summary.cortex_hits} | 知识库 ${result.summary.knowledge_entities + result.summary.knowledge_claims}`);
    lines.push('');

    // Cortex 结果
    if (result.cortex?.hits?.length) {
      lines.push('📚 Cortex 参考资料:');
      result.cortex.hits.forEach((h, i) => {
        lines.push(`   ${i + 1}. [${(h.score * 100).toFixed(0)}%] ${h.title || h.task_id}`);
        lines.push(`      ${h.snippet.substring(0, 60)}...`);
      });
      lines.push('');

      // Evidence Pack
      if (result.cortex.evidence_pack) {
        const ep = result.cortex.evidence_pack;
        lines.push(`📊 Evidence Pack:`);
        lines.push(`   来源: ${ep.stats.source_count} | 结论: ${ep.stats.claim_count} | 平均可信度: ${ep.stats.avg_credibility}`);
        lines.push('');
      }
    }

    // Knowledge 结果
    if (result.knowledge) {
      if (result.knowledge.entities.length) {
        lines.push('👤 知识图谱实体:');
        result.knowledge.entities.slice(0, 5).forEach(e => {
          lines.push(`   [${e.type}] ${e.name}: ${e.description?.substring(0, 40) || ''}...`);
        });
        lines.push('');
      }

      if (result.knowledge.claims.length) {
        lines.push('💡 知识库结论:');
        result.knowledge.claims.slice(0, 5).forEach(c => {
          lines.push(`   [${(c.confidence * 100).toFixed(0)}%] ${c.claim_text.substring(0, 60)}...`);
        });
        lines.push('');
      }

      if (result.knowledge.relations.length) {
        lines.push('🔗 实体关系:');
        result.knowledge.relations.slice(0, 5).forEach(r => {
          lines.push(`   ${r.from_entity} --[${r.relation_type}]--> ${r.to_entity}`);
        });
      }
    }

    return lines.join('\n');
  }

  /**
   * 统计信息
   */
  async stats(): Promise<{
    cortex: { artifacts: number; sources: number; claims: number; tasks: number };
    knowledge: { entities: number; relations: number; claims: number };
  }> {
    const cortexStats = await this.cortexQuery.stats();

    const count = (table: string) => {
      try {
        const row = this.db.query(`SELECT COUNT(*) as count FROM ${table}`).get() as { count: number };
        return row?.count || 0;
      } catch {
        return 0;
      }
    };

    return {
      cortex: cortexStats,
      knowledge: {
        entities: count('knowledge_entities'),
        relations: count('knowledge_relations'),
        claims: count('knowledge_claims')
      }
    };
  }

  close() {
    this.cortexQuery.close();
    this.db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];
  const query = new UnifiedQuery();

  switch (cmd) {
    case 'search':
    case 'query': {
      const q = process.argv[3];
      const k = parseInt(process.argv[4]) || 10;

      if (!q) {
        console.error('Usage: unified-query.ts search <query> [k]');
        process.exit(1);
      }

      const result = await query.query({
        q,
        k,
        mode: 'all',
        need_evidence: process.env.EVIDENCE === 'true'
      });

      console.log(query.formatOutput(result));
      break;
    }

    case 'evidence': {
      const q = process.argv[3];
      if (!q) {
        console.error('Usage: unified-query.ts evidence <query>');
        process.exit(1);
      }

      const result = await query.query({
        q,
        k: 5,
        mode: 'cortex',
        need_evidence: true,
        gate_policy: 'strict'
      });

      console.log(query.formatOutput(result));

      if (result.cortex?.evidence_pack) {
        console.log('\n📋 详细证据:');
        console.log(JSON.stringify(result.cortex.evidence_pack, null, 2));
      }
      break;
    }

    case 'graph': {
      const q = process.argv[3];
      if (!q) {
        console.error('Usage: unified-query.ts graph <entity>');
        process.exit(1);
      }

      const result = await query.query({
        q,
        k: 10,
        mode: 'knowledge',
        need_graph: true
      });

      console.log(query.formatOutput(result));
      break;
    }

    case 'stats': {
      const stats = await query.stats();
      console.log('\n📊 统一知识库统计:\n');
      console.log('Cortex 系统:');
      console.log(`   Artifacts: ${stats.cortex.artifacts}`);
      console.log(`   Sources: ${stats.cortex.sources}`);
      console.log(`   Claims: ${stats.cortex.claims}`);
      console.log(`   Tasks: ${stats.cortex.tasks}`);
      console.log('\nKnowledge 系统:');
      console.log(`   Entities: ${stats.knowledge.entities}`);
      console.log(`   Relations: ${stats.knowledge.relations}`);
      console.log(`   Claims: ${stats.knowledge.claims}`);
      break;
    }

    default:
      console.log(`
📚 Solar 统一知识查询

用法:
  unified-query.ts search <query> [k]   - 统一搜索 (默认 k=10)
  unified-query.ts evidence <query>     - 深度证据搜索 (Cortex only, strict)
  unified-query.ts graph <entity>       - 知识图谱搜索 (Knowledge only)
  unified-query.ts stats                - 统计信息

环境变量:
  EVIDENCE=true   - 搜索时包含 evidence_pack

示例:
  unified-query.ts search "memory architecture" 10
  unified-query.ts evidence "AI Agent 记忆机制"
  unified-query.ts graph "Transformer"
  unified-query.ts stats
`);
  }

  query.close();
}

export default UnifiedQuery;
