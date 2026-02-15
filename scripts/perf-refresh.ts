#!/usr/bin/env bun
/**
 * 牛马绩效刷新脚本 - 从数据库读取绩效，注入到 niumao-anchors.json
 * 运行: bun ~/.claude/scripts/perf-refresh.ts
 */
import { Database } from 'bun:sqlite';
import { readFileSync, writeFileSync } from 'fs';
import { homedir } from 'os';

const home = homedir();
const db = new Database(`${home}/.solar/solar.db`);
const anchorsPath = `${home}/.claude/niumao-anchors.json`;

// 读取绩效排名
const rankings = db.prepare(`
  SELECT model_id, task_count, avg_score, ranking
  FROM v_niumao_ranking
  ORDER BY ranking
`).all() as { model_id: string; task_count: number; avg_score: number; ranking: number }[];

const total = rankings.length || 1;
const rankMap = new Map(rankings.map(r => [r.model_id, r]));

// 读取牛马配置
const anchors = JSON.parse(readFileSync(anchorsPath, 'utf-8'));

// 生成绩效注入文本
function genPerfText(modelId: string): string {
  const r = rankMap.get(modelId);
  if (!r || !r.avg_score) return '';
  const pct = Math.round((1 - r.ranking / total) * 100);
  const status = pct >= 50 ? '保持优势！' : '需要提升！';
  return ` 【绩效】得分${r.avg_score}，排名${r.ranking}/${total}，超${pct}%同事。${status}`;
}

// 更新各类牛马的 system prompt
for (const category of ['experts', 'workers', 'backup']) {
  const group = anchors[category];
  if (!group) continue;

  for (const [modelId, config] of Object.entries(group)) {
    const cfg = config as { system: string; perf?: string };
    const perfText = genPerfText(modelId);
    cfg.perf = perfText; // 单独存储，不污染原 system
  }
}

// 写回
writeFileSync(anchorsPath, JSON.stringify(anchors, null, 2));
db.close();

console.log(`✅ 绩效已刷新，共 ${total} 个牛马有记录`);
rankings.forEach(r => {
  console.log(`   ${r.ranking}. ${r.model_id}: ${r.avg_score}分 (${r.task_count}次)`);
});
