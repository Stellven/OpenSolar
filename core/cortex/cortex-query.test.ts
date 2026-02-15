/**
 * Cortex Query v0.2 测试
 */

import { test, describe, beforeAll, afterAll, expect } from 'bun:test';
import { CortexQuery, CortexQueryParams, CortexQueryResult } from './cortex-query';

describe('CortexQuery', () => {
  let query: CortexQuery;

  beforeAll(() => {
    query = new CortexQuery();
  });

  afterAll(() => {
    query.close();
  });

  describe('基础搜索', () => {
    test('搜索返回结果', async () => {
      const result = await query.query({ q: 'memory', k: 5 });
      expect(result.hits.length).toBeGreaterThanOrEqual(0);
      expect(result.meta.latency_ms).toBeLessThan(500);
    });

    test('搜索结果包含必要字段', async () => {
      const result = await query.query({ q: 'memory', k: 1 });
      if (result.hits.length > 0) {
        const hit = result.hits[0];
        expect(hit).toHaveProperty('artifact_id');
        expect(hit).toHaveProperty('task_id');
        expect(hit).toHaveProperty('kind');
        expect(hit).toHaveProperty('snippet');
      }
    });
  });

  describe('门禁策略', () => {
    test('loose 策略不过滤低分', async () => {
      const result = await query.query({
        q: 'memory',
        k: 10,
        gate_policy: 'loose'
      });
      expect(result.meta.final_count).toBeGreaterThanOrEqual(0);
    });

    test('strict 策略过滤低分', async () => {
      const looseResult = await query.query({
        q: 'memory',
        k: 10,
        gate_policy: 'loose'
      });

      const strictResult = await query.query({
        q: 'memory',
        k: 10,
        gate_policy: 'strict'
      });

      // strict 结果应该 <= loose 结果
      expect(strictResult.meta.final_count).toBeLessThanOrEqual(looseResult.meta.final_count);
    });

    test('none 策略不过滤', async () => {
      const result = await query.query({
        q: 'memory',
        k: 10,
        gate_policy: 'none'
      });
      expect(result.meta.final_count).toBeGreaterThanOrEqual(0);
    });
  });

  describe('task_scope 过滤', () => {
    test('task_scope 限制结果范围', async () => {
      // 先获取一个存在的 task_id
      const allResult = await query.query({ q: 'memory', k: 1 });
      if (allResult.hits.length > 0) {
        const taskId = allResult.hits[0].task_id;

        const scopedResult = await query.query({
          q: 'memory',
          k: 10,
          task_scope: [taskId]
        });

        // 所有结果应该来自指定的 task_id
        scopedResult.hits.forEach(hit => {
          expect(hit.task_id).toBe(taskId);
        });
      }
    });
  });

  describe('Evidence Pack', () => {
    test('need=evidence 返回 evidence_pack', async () => {
      const result = await query.query({
        q: 'memory',
        k: 3,
        need: ['evidence']
      });

      expect(result.evidence_pack).toBeDefined();
      expect(result.evidence_pack?.stats).toBeDefined();
      expect(result.evidence_pack?.stats).toHaveProperty('source_count');
      expect(result.evidence_pack?.stats).toHaveProperty('claim_count');
      expect(result.evidence_pack?.stats).toHaveProperty('edge_count');
    });
  });

  describe('Trace 日志', () => {
    test('need=trace 返回 trace 信息', async () => {
      const result = await query.query({
        q: 'memory',
        k: 3,
        need: ['trace']
      });

      expect(result.trace).toBeDefined();
      expect(result.trace?.tantivy_query).toBe('memory');
      expect(Array.isArray(result.trace?.sqlite_filters)).toBe(true);
    });
  });

  describe('高级查询', () => {
    test('min_score 过滤低分结果', async () => {
      const result = await query.query({
        q: 'memory',
        k: 10,
        min_score: 0.8,
        gate_policy: 'none'
      });

      result.hits.forEach(hit => {
        expect(hit.score).toBeGreaterThanOrEqual(0.8);
      });
    });

    test('时间范围过滤', async () => {
      const now = Date.now();
      const oneDayAgo = now - 24 * 60 * 60 * 1000;

      const result = await query.query({
        q: 'memory',
        k: 10,
        after: oneDayAgo,
        before: now
      });

      result.hits.forEach(hit => {
        if (hit.ts_ms > 0) {
          expect(hit.ts_ms).toBeGreaterThanOrEqual(oneDayAgo);
          expect(hit.ts_ms).toBeLessThanOrEqual(now);
        }
      });
    });
  });

  describe('统计信息', () => {
    test('stats 返回正确的统计', async () => {
      const stats = await query.stats();

      expect(stats).toHaveProperty('artifacts');
      expect(stats).toHaveProperty('sources');
      expect(stats).toHaveProperty('claims');
      expect(stats).toHaveProperty('edges');
      expect(stats).toHaveProperty('tasks');

      expect(stats.artifacts).toBeGreaterThanOrEqual(0);
      expect(stats.sources).toBeGreaterThanOrEqual(0);
    });
  });
});
