/**
 * Cortex Query v0.2 - 统一查询入口
 * Tantivy (召回) → SQLite (门禁) → FS (装配)
 *
 * 用法:
 *   bun cortex-query.ts search "memory architecture" 10
 *   bun cortex-query.ts sync
 *   bun cortex-query.ts stats
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { existsSync, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { execSync, execFileSync } from 'child_process';

// ============================================================
// 类型定义
// ============================================================

export interface CortexQueryParams {
  q: string;                           // 查询文本
  task_scope?: string[];               // task_id 过滤
  k?: number;                          // 返回数量 (默认 10)
  gate_policy?: 'loose' | 'strict' | 'none';  // 门禁策略
  need?: ('snippets' | 'evidence' | 'trace')[];  // 需要的额外信息
  kind?: ('source' | 'claim' | 'outline' | 'draft' | 'review' | 'final')[];  // 类型过滤
  min_score?: number;                  // 最低可信度
  after?: number;                      // 时间戳过滤 - 开始 (毫秒)
  before?: number;                     // 时间戳过滤 - 结束 (毫秒)
  expert_model?: string;               // 专家模型过滤
}

export interface CortexHit {
  artifact_id: number;
  task_id: string;
  kind: string;
  score: number;
  title?: string;
  snippet: string;
  source_type: string;
  citation_key?: string;
  ts_ms: number;
  detail?: {
    content_path: string;
    hash: string;
    expert_model?: string;
  };
}

export interface EvidencePack {
  sources: Source[];
  claims: Claim[];
  edges: ArtifactEdge[];
  // 增强功能
  citation_chain?: CitationChain[];
  stats: {
    source_count: number;
    claim_count: number;
    edge_count: number;
    avg_credibility: number;
  };
}

export interface CitationChain {
  artifact_id: number;
  chain: {
    src_id: number;
    dst_id: number;
    edge_type: string;
    depth: number;
  }[];
}

export interface Source {
  source_id: number;
  citation_key: string;
  title: string;
  url?: string;
  finding: string;
  credibility: number;
}

export interface Claim {
  claim_id: number;
  claim_text: string;
  supporting_sources: string[];
  counter_sources: string[];
  confidence: number;
}

export interface ArtifactEdge {
  src_id: number;
  dst_id: number;
  edge_type: string;
  confidence: number;
}

export interface QueryTrace {
  tantivy_query: string;
  sqlite_filters: string[];
  fs_loads: string[];
}

export interface CortexQueryResult {
  hits: CortexHit[];
  evidence_pack?: EvidencePack;
  trace?: QueryTrace;
  meta: {
    latency_ms: number;
    tantivy_docs: number;
    sqlite_filtered: number;
    final_count: number;
  };
}

// ============================================================
// CortexQuery 核心类
// ============================================================

export class CortexQuery {
  private db: Database;
  private tantivyBinary: string;
  private tantivyIndex: string;
  private artifactsDir: string;
  private traceLog: string[] = [];

  constructor() {
    const home = homedir();
    this.db = new Database(`${home}/.solar/solar.db`);
    this.tantivyBinary = `${home}/Solar/core/search/target/release/solar-search`;
    this.tantivyIndex = `${home}/.solar/search/index`;
    this.artifactsDir = `${home}/.solar/cortex/artifacts`;
  }

  /**
   * 统一查询入口
   */
  async query(params: CortexQueryParams): Promise<CortexQueryResult> {
    const startTime = Date.now();
    this.traceLog = [];

    // Step 1: Tantivy 召回
    const tantivyHits = await this.tantivySearch(params);
    this.traceLog.push(`Tantivy returned ${tantivyHits.length} docs`);

    // Step 2: SQLite 门禁过滤
    const filteredHits = await this.sqliteGate(tantivyHits, params);
    this.traceLog.push(`SQLite filtered to ${filteredHits.length} docs`);

    // Step 3: FS 装配详情
    const enrichedHits = await this.enrichFromFS(filteredHits, params);

    // Step 4: 组装 evidence_pack (可选)
    const evidencePack = params.need?.includes('evidence')
      ? await this.buildEvidencePack(enrichedHits)
      : undefined;

    // Step 5: 截取到 k 条
    const k = params.k || 10;
    const finalHits = enrichedHits.slice(0, k);

    return {
      hits: finalHits,
      evidence_pack: evidencePack,
      trace: params.need?.includes('trace') ? {
        tantivy_query: params.q,
        sqlite_filters: this.traceLog,
        fs_loads: finalHits.map(h => h.detail?.content_path || '').filter(Boolean)
      } : undefined,
      meta: {
        latency_ms: Date.now() - startTime,
        tantivy_docs: tantivyHits.length,
        sqlite_filtered: filteredHits.length,
        final_count: finalHits.length
      }
    };
  }

  /**
   * Tantivy 搜索 (召回层)
   */
  private async tantivySearch(params: CortexQueryParams): Promise<number[]> {
    // 如果 Tantivy 不可用，降级到 SQLite 全文搜索
    if (!existsSync(this.tantivyBinary)) {
      return this.sqliteFallbackSearch(params);
    }

    try {
      const cmd = [
        this.tantivyBinary,
        'query',
        params.q,
        '--limit', String((params.k || 10) * 3),  // 召回 3x
        '--format', 'json',
      ];

      if (params.kind?.length) {
        cmd.push('--kind', params.kind.join(','));
      }
      if (params.task_scope?.length) {
        cmd.push('--task-id', params.task_scope.join(','));
      }

      // 使用 execFileSync 正确传递参数 (避免 shell 解析问题)
      const result = execFileSync(this.tantivyBinary, cmd.slice(1), {
        encoding: 'utf-8',
        timeout: 5000,
      });

      // 直接解析 JSON (stdout 已是纯净的 JSON 输出)
      const parsed = JSON.parse(result.trim());

      // CLI 直接返回数组
      const hits = Array.isArray(parsed) ? parsed : (parsed.hits || []);
      return hits.map((h: any) => {
        // 提取 id 中的数字部分 (如 "artifact_123" → 123)
        const id = h.id || '';
        const match = id.match(/(\d+)/);
        return match ? parseInt(match[1], 10) : 0;
      }).filter(id => id > 0);
    } catch (e) {
      console.error('Tantivy search failed, falling back to SQLite:', e);
      return this.sqliteFallbackSearch(params);
    }
  }

  /**
   * SQLite 降级搜索
   */
  private async sqliteFallbackSearch(params: CortexQueryParams): Promise<number[]> {
    const k = (params.k || 10) * 3;

    // 使用 LIKE 搜索 (简单但有效)
    const sql = `
      SELECT artifact_id
      FROM cortex_artifacts a
      WHERE a.content_json LIKE ?
      ORDER BY a.created_at DESC
      LIMIT ?
    `;

    const searchTerm = `%${params.q}%`;
    const rows = this.db.query(sql).all(searchTerm, k) as { artifact_id: number }[];

    return rows.map(r => r.artifact_id);
  }

  /**
   * SQLite 门禁 (过滤层)
   */
  private async sqliteGate(
    artifactIds: number[],
    params: CortexQueryParams
  ): Promise<any[]> {
    if (artifactIds.length === 0) return [];

    const placeholders = artifactIds.map(() => '?').join(',');
    let sql = `
      SELECT a.*, t.topic
      FROM cortex_artifacts a
      LEFT JOIN cortex_tasks t ON a.task_id = t.task_id
      WHERE a.artifact_id IN (${placeholders})
    `;
    const queryParams: any[] = [...artifactIds];

    // 门禁策略
    if (params.gate_policy === 'strict') {
      sql += ` AND COALESCE(a.status, 'active') = 'validated' AND COALESCE(a.score, 0.5) >= ?`;
      queryParams.push(params.min_score || 0.7);
    } else if (params.gate_policy === 'loose' || !params.gate_policy) {
      sql += ` AND COALESCE(a.status, 'active') != 'deprecated'`;
    }
    // 'none' 不添加任何过滤

    // 类型过滤
    if (params.kind?.length) {
      sql += ` AND (a.kind IN (${params.kind.map(() => '?').join(',')}) OR a.artifact_type IN (${params.kind.map(() => '?').join(',')}))`;
      queryParams.push(...params.kind, ...params.kind);
    }

    // task_scope 过滤
    if (params.task_scope?.length) {
      sql += ` AND a.task_id IN (${params.task_scope.map(() => '?').join(',')})`;
      queryParams.push(...params.task_scope);
    }

    // 时间范围
    if (params.after) {
      sql += ` AND COALESCE(a.ts_ms, 0) >= ?`;
      queryParams.push(params.after);
    }
    if (params.before) {
      sql += ` AND COALESCE(a.ts_ms, 9999999999999) <= ?`;
      queryParams.push(params.before);
    }

    // 最低分数
    if (params.min_score && params.gate_policy !== 'strict') {
      sql += ` AND COALESCE(a.score, 0.5) >= ?`;
      queryParams.push(params.min_score);
    }

    // 专家模型过滤
    if (params.expert_model) {
      sql += ` AND a.expert_model = ?`;
      queryParams.push(params.expert_model);
    }

    // 按分数和时间排序
    sql += ` ORDER BY COALESCE(a.score, 0.5) DESC, COALESCE(a.ts_ms, 0) DESC`;

    return this.db.query(sql).all(...queryParams);
  }

  /**
   * FS 装配详情
   */
  private async enrichFromFS(
    hits: any[],
    params: CortexQueryParams
  ): Promise<CortexHit[]> {
    return hits.map(hit => {
      // 从 content_json 提取 snippet
      let snippet = '';
      try {
        const content = typeof hit.content_json === 'string'
          ? JSON.parse(hit.content_json)
          : hit.content_json;

        if (content.outline) {
          snippet = content.outline.substring(0, 200);
        } else if (content.content) {
          snippet = content.content.substring(0, 200);
        } else if (content.finding) {
          snippet = content.finding;
        } else {
          snippet = JSON.stringify(content).substring(0, 200);
        }
      } catch {
        snippet = String(hit.content_json).substring(0, 200);
      }

      return {
        artifact_id: hit.artifact_id,
        task_id: hit.task_id,
        kind: hit.kind || hit.artifact_type,
        score: hit.score || 0.5,
        title: hit.title || hit.topic,
        snippet,
        source_type: hit.source_type || 'unknown',
        citation_key: hit.citation_key,
        ts_ms: hit.ts_ms || new Date(hit.created_at).getTime(),
        detail: params.need?.includes('snippets') ? {
          content_path: hit.content_path || hit.file_path,
          hash: hit.hash,
          expert_model: hit.expert_model
        } : undefined
      };
    });
  }

  /**
   * 构建 Evidence Pack (增强版)
   */
  private async buildEvidencePack(hits: CortexHit[]): Promise<EvidencePack> {
    const taskIds = [...new Set(hits.map(h => h.task_id))];
    const artifactIds = hits.map(h => h.artifact_id);

    // 并行获取 sources, claims, edges
    const [sources, claims, edges] = await Promise.all([
      this.getSources(taskIds),
      this.getClaims(taskIds),
      this.getEdges(artifactIds)
    ]);

    // 构建引用链
    const citationChains = this.buildCitationChains(artifactIds, edges);

    // 计算统计信息
    const avgCredibility = sources.length > 0
      ? sources.reduce((sum, s) => sum + s.credibility, 0) / sources.length
      : 0;

    return {
      sources,
      claims,
      edges,
      citation_chain: citationChains,
      stats: {
        source_count: sources.length,
        claim_count: claims.length,
        edge_count: edges.length,
        avg_credibility: Math.round(avgCredibility * 100) / 100
      }
    };
  }

  /**
   * 构建引用链 (深度控制)
   */
  private buildCitationChains(
    artifactIds: number[],
    edges: ArtifactEdge[],
    maxDepth: number = 3
  ): CitationChain[] {
    const chains: CitationChain[] = [];
    const visited = new Set<number>();

    for (const artifactId of artifactIds) {
      if (visited.has(artifactId)) continue;
      visited.add(artifactId);

      const chain = this.traverseChain(artifactId, edges, [], 0, maxDepth);
      if (chain.length > 0) {
        chains.push({ artifact_id: artifactId, chain });
      }
    }

    return chains;
  }

  /**
   * 递归遍历引用链
   */
  private traverseChain(
    currentId: number,
    edges: ArtifactEdge[],
    path: { src_id: number; dst_id: number; edge_type: string; depth: number }[],
    depth: number,
    maxDepth: number
  ): { src_id: number; dst_id: number; edge_type: string; depth: number }[] {
    if (depth >= maxDepth) return path;

    // 找到从当前节点出发的边
    const outgoingEdges = edges.filter(e => e.src_id === currentId);

    for (const edge of outgoingEdges) {
      path.push({
        src_id: edge.src_id,
        dst_id: edge.dst_id,
        edge_type: edge.edge_type,
        depth
      });

      // 递归遍历
      this.traverseChain(edge.dst_id, edges, path, depth + 1, maxDepth);
    }

    return path;
  }

  private async getSources(taskIds: string[]): Promise<Source[]> {
    if (taskIds.length === 0) return [];

    const placeholders = taskIds.map(() => '?').join(',');
    const sql = `
      SELECT source_id, citation_key, title, url, finding, credibility
      FROM cortex_sources
      WHERE task_id IN (${placeholders})
    `;

    return this.db.query(sql).all(...taskIds) as Source[];
  }

  private async getClaims(taskIds: string[]): Promise<Claim[]> {
    if (taskIds.length === 0) return [];

    const placeholders = taskIds.map(() => '?').join(',');
    const sql = `
      SELECT claim_id, claim_text, supporting_sources, counter_sources, confidence
      FROM cortex_claims
      WHERE task_id IN (${placeholders})
    `;

    const rows = this.db.query(sql).all(...taskIds) as any[];
    return rows.map(r => ({
      claim_id: r.claim_id,
      claim_text: r.claim_text,
      supporting_sources: JSON.parse(r.supporting_sources || '[]'),
      counter_sources: JSON.parse(r.counter_sources || '[]'),
      confidence: r.confidence || 0.5
    }));
  }

  private async getEdges(artifactIds: number[]): Promise<ArtifactEdge[]> {
    if (artifactIds.length === 0) return [];

    const placeholders = artifactIds.map(() => '?').join(',');
    const sql = `
      SELECT src_id, dst_id, edge_type, confidence
      FROM cortex_artifact_edges
      WHERE src_id IN (${placeholders}) OR dst_id IN (${placeholders})
    `;

    return this.db.query(sql).all(...artifactIds, ...artifactIds) as ArtifactEdge[];
  }

  /**
   * 同步 Cortex 数据到 Tantivy
   * Schema Optimization v0.3: 使用 snippet + 新字段
   */
  async syncToTantivy(): Promise<{ synced: number; errors: string[] }> {
    const errors: string[] = [];
    let synced = 0;

    // 获取所有 artifacts
    const artifacts = this.db.query(`
      SELECT a.*, t.topic
      FROM cortex_artifacts a
      LEFT JOIN cortex_tasks t ON a.task_id = t.task_id
      WHERE COALESCE(a.status, 'active') != 'deprecated'
    `).all() as any[];

    console.log(`Found ${artifacts.length} artifacts to sync`);

    // 如果 Tantivy 可用，同步到队列
    if (existsSync(this.tantivyBinary)) {
      for (const artifact of artifacts) {
        try {
          // 提取 snippet (用于搜索，而非存储完整内容)
          const snippet = this.extractSnippet(artifact.content_json, 500);

          // 添加到 Tantivy 队列 (Schema Optimization v0.3: 使用新字段)
          this.db.run(`
            INSERT OR REPLACE INTO tantivy_queue (
              doc_type, source_id, content, title, source_path, timestamp, project, metadata, status,
              artifact_id, content_path, score, kind, task_id, citation_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
          `, [
            'artifact',
            `artifact_${artifact.artifact_id}`,  // source_id 带前缀
            snippet,                               // content 只存 snippet
            artifact.topic || artifact.artifact_type,
            artifact.file_path || '',
            artifact.ts_ms || Date.now(),
            artifact.task_id,
            JSON.stringify({}),                    // metadata 简化
            // Schema Optimization v0.3 新增字段
            artifact.artifact_id,                  // artifact_id (numeric)
            artifact.content_path || artifact.file_path || '',  // content_path
            artifact.score || 0.5,                 // score
            artifact.kind || artifact.artifact_type,  // kind
            artifact.task_id,                      // task_id
            artifact.citation_key || null          // citation_key
          ]);
          synced++;
        } catch (e) {
          errors.push(`Failed to sync artifact ${artifact.artifact_id}: ${e}`);
        }
      }
    } else {
      errors.push('Tantivy binary not found, skipping sync');
    }

    return { synced, errors };
  }

  /**
   * 从 content_json 提取文本片段 (用于索引)
   */
  private extractSnippet(contentJson: any, maxLength: number = 500): string {
    let text = '';

    try {
      const content = typeof contentJson === 'string' ? JSON.parse(contentJson) : contentJson;

      if (content.outline) {
        text = String(content.outline);
      } else if (content.content) {
        text = String(content.content);
      } else if (content.finding) {
        text = String(content.finding);
      } else if (content.claim_text) {
        text = String(content.claim_text);
      } else if (content.prompt) {
        text = String(content.prompt);
      } else {
        text = JSON.stringify(content);
      }
    } catch {
      text = String(contentJson);
    }

    // 截断到指定长度
    return text.substring(0, maxLength);
  }

  /**
   * 统计信息
   */
  async stats(): Promise<{
    artifacts: number;
    sources: number;
    claims: number;
    edges: number;
    tasks: number;
  }> {
    const count = (table: string) => {
      const row = this.db.query(`SELECT COUNT(*) as count FROM ${table}`).get() as { count: number };
      return row.count;
    };

    return {
      artifacts: count('cortex_artifacts'),
      sources: count('cortex_sources'),
      claims: count('cortex_claims'),
      edges: count('cortex_artifact_edges'),
      tasks: count('cortex_tasks')
    };
  }

  close() {
    this.db.close();
  }
}

// ============================================================
// CLI 入口
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];
  const query = new CortexQuery();

  switch (cmd) {
    case 'search':
    case 'query': {
      const q = process.argv[3];
      const k = parseInt(process.argv[4]) || 10;

      if (!q) {
        console.error('Usage: cortex-query.ts search <query> [k]');
        process.exit(1);
      }

      const params: CortexQueryParams = {
        q,
        k,
        task_scope: process.env.TASK_SCOPE?.split(','),
        gate_policy: (process.env.GATE_POLICY as any) || 'loose',
        need: (process.env.NEED?.split(',') as any[]) || ['snippets'],
        min_score: process.env.MIN_SCORE ? parseFloat(process.env.MIN_SCORE) : undefined,
      };

      const result = await query.query(params);
      console.log(JSON.stringify(result, null, 2));
      break;
    }

    case 'sync': {
      console.log('Syncing Cortex data to Tantivy...');
      const result = await query.syncToTantivy();
      console.log(`Synced ${result.synced} artifacts`);
      if (result.errors.length > 0) {
        console.error('Errors:', result.errors);
      }
      break;
    }

    case 'stats': {
      const stats = await query.stats();
      console.log(JSON.stringify(stats, null, 2));
      break;
    }

    default:
      console.error('Usage: cortex-query.ts <search|sync|stats> [args]');
      console.error('  search <query> [k]  - Search cortex artifacts');
      console.error('  sync                - Sync to Tantivy');
      console.error('  stats               - Show statistics');
      process.exit(1);
  }

  query.close();
}
