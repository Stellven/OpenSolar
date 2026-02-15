#!/usr/bin/env bun
/**
 * Phase 2.3: 历史记录追踪器
 *
 * 功能:
 * 1. 保存检测记录到 SQLite
 * 2. 对比历史数据
 * 3. 趋势分析
 */

import Database from "bun:sqlite";
import { existsSync } from "fs";
import path from "path";

const DB_PATH = path.join(__dirname, "skin-check-history.db");

interface HistoryRecord {
  id?: number;
  timestamp: string;
  photoPath: string;
  skinType: string;
  confidence: number;
  features: string[];
  lesionCount: number;
  severityScore: number;
  mode: string;
}

interface TrendAnalysis {
  period: string;            // "7d", "30d", "90d"
  totalRecords: number;
  skinTypeChanges: number;   // 皮肤类型变化次数
  avgSeverity: number;       // 平均严重程度
  lesionTrend: "improving" | "worsening" | "stable";
  recommendations: string[];
}

/**
 * 初始化数据库
 */
function initDatabase(): Database {
  const db = new Database(DB_PATH);

  // 创建历史记录表
  db.run(`
    CREATE TABLE IF NOT EXISTS skin_check_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      timestamp TEXT NOT NULL,
      photo_path TEXT NOT NULL,
      skin_type TEXT NOT NULL,
      confidence REAL NOT NULL,
      features TEXT NOT NULL,
      lesion_count INTEGER DEFAULT 0,
      severity_score INTEGER DEFAULT 0,
      mode TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // 创建索引
  db.run(`
    CREATE INDEX IF NOT EXISTS idx_timestamp
    ON skin_check_history(timestamp)
  `);

  return db;
}

/**
 * 保存检测记录
 */
export function saveRecord(record: HistoryRecord): number {
  const db = initDatabase();

  const result = db.run(`
    INSERT INTO skin_check_history
    (timestamp, photo_path, skin_type, confidence, features, lesion_count, severity_score, mode)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `,
    record.timestamp,
    record.photoPath,
    record.skinType,
    record.confidence,
    JSON.stringify(record.features),
    record.lesionCount,
    record.severityScore,
    record.mode
  );

  db.close();
  return result.lastInsertRowid as number;
}

/**
 * 获取历史记录
 */
export function getHistory(limit: number = 10): HistoryRecord[] {
  const db = initDatabase();

  const rows = db.query(`
    SELECT * FROM skin_check_history
    ORDER BY timestamp DESC
    LIMIT ?
  `).all(limit);

  db.close();

  return rows.map((row: any) => ({
    id: row.id,
    timestamp: row.timestamp,
    photoPath: row.photo_path,
    skinType: row.skin_type,
    confidence: row.confidence,
    features: JSON.parse(row.features),
    lesionCount: row.lesion_count,
    severityScore: row.severity_score,
    mode: row.mode
  }));
}

/**
 * 分析趋势
 */
export function analyzeTrend(period: string = "30d"): TrendAnalysis {
  const db = initDatabase();

  // 计算时间范围
  const days = parseInt(period);
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - days);

  const records = db.query(`
    SELECT * FROM skin_check_history
    WHERE timestamp >= ?
    ORDER BY timestamp ASC
  `).all(cutoffDate.toISOString());

  db.close();

  if (records.length === 0) {
    return {
      period,
      totalRecords: 0,
      skinTypeChanges: 0,
      avgSeverity: 0,
      lesionTrend: "stable",
      recommendations: ["暂无历史数据，建议多次检测建立基线"]
    };
  }

  // 分析皮肤类型变化
  let skinTypeChanges = 0;
  let prevSkinType = (records[0] as any).skin_type;

  for (let i = 1; i < records.length; i++) {
    if ((records[i] as any).skin_type !== prevSkinType) {
      skinTypeChanges++;
      prevSkinType = (records[i] as any).skin_type;
    }
  }

  // 平均严重程度
  const avgSeverity = records.reduce((sum, r: any) => sum + r.severity_score, 0) / records.length;

  // 病灶趋势分析
  const recentSeverity = records.slice(-3).reduce((sum, r: any) => sum + r.severity_score, 0) / 3;
  const oldSeverity = records.slice(0, 3).reduce((sum, r: any) => sum + r.severity_score, 0) / 3;

  let lesionTrend: "improving" | "worsening" | "stable";
  if (recentSeverity < oldSeverity - 10) {
    lesionTrend = "improving";
  } else if (recentSeverity > oldSeverity + 10) {
    lesionTrend = "worsening";
  } else {
    lesionTrend = "stable";
  }

  // 生成建议
  const recommendations: string[] = [];

  if (lesionTrend === "improving") {
    recommendations.push("✅ 皮肤状况有所改善，继续保持现有护理方案");
  } else if (lesionTrend === "worsening") {
    recommendations.push("⚠️ 皮肤状况有恶化趋势，建议咨询皮肤科医生");
  } else {
    recommendations.push("📊 皮肤状况保持稳定");
  }

  if (skinTypeChanges > 2) {
    recommendations.push("⚠️ 皮肤类型变化频繁，可能与季节或护肤品有关");
  }

  if (avgSeverity > 50) {
    recommendations.push("⚠️ 平均严重程度较高，建议专业诊断");
  }

  return {
    period,
    totalRecords: records.length,
    skinTypeChanges,
    avgSeverity: Math.round(avgSeverity),
    lesionTrend,
    recommendations
  };
}

/**
 * 对比两次检测
 */
export function compareRecords(id1: number, id2: number): any {
  const db = initDatabase();

  const record1 = db.query("SELECT * FROM skin_check_history WHERE id = ?").get(id1) as any;
  const record2 = db.query("SELECT * FROM skin_check_history WHERE id = ?").get(id2) as any;

  db.close();

  if (!record1 || !record2) {
    return { error: "记录不存在" };
  }

  return {
    skinTypeChange: record1.skin_type !== record2.skin_type,
    confidenceDelta: record2.confidence - record1.confidence,
    severityDelta: record2.severity_score - record1.severity_score,
    lesionCountDelta: record2.lesion_count - record1.lesion_count,
    timeDelta: new Date(record2.timestamp).getTime() - new Date(record1.timestamp).getTime()
  };
}

// CLI 模式
if (import.meta.main) {
  const command = process.argv[2];

  if (command === "list") {
    const limit = parseInt(process.argv[3] || "10");
    const history = getHistory(limit);

    console.log(`\n📊 最近 ${limit} 次检测记录:\n`);

    if (history.length === 0) {
      console.log("暂无历史记录");
    } else {
      history.forEach((record, i) => {
        const date = new Date(record.timestamp).toLocaleString('zh-CN');
        console.log(`${i + 1}. [${date}] ${record.skinType} (置信度: ${(record.confidence * 100).toFixed(1)}%)`);
        console.log(`   病灶: ${record.lesionCount} 个, 严重程度: ${record.severityScore}/100`);
      });
    }
  } else if (command === "trend") {
    const period = process.argv[3] || "30d";
    const trend = analyzeTrend(period);

    console.log(`\n📈 趋势分析 (最近 ${trend.period}):\n`);
    console.log(`记录数: ${trend.totalRecords} 次`);
    console.log(`皮肤类型变化: ${trend.skinTypeChanges} 次`);
    console.log(`平均严重程度: ${trend.avgSeverity}/100`);
    console.log(`病灶趋势: ${trend.lesionTrend === "improving" ? "改善" : trend.lesionTrend === "worsening" ? "恶化" : "稳定"}`);
    console.log("\n建议:");
    trend.recommendations.forEach(r => console.log(`  ${r}`));
  } else if (command === "compare") {
    const id1 = parseInt(process.argv[3]);
    const id2 = parseInt(process.argv[4]);

    if (isNaN(id1) || isNaN(id2)) {
      console.error("用法: bun history-tracker.ts compare <id1> <id2>");
      process.exit(1);
    }

    const comparison = compareRecords(id1, id2);

    if (comparison.error) {
      console.error(comparison.error);
    } else {
      console.log(`\n🔄 对比记录 #${id1} vs #${id2}:\n`);
      console.log(`皮肤类型变化: ${comparison.skinTypeChange ? "是" : "否"}`);
      console.log(`置信度变化: ${comparison.confidenceDelta > 0 ? "+" : ""}${(comparison.confidenceDelta * 100).toFixed(1)}%`);
      console.log(`严重程度变化: ${comparison.severityDelta > 0 ? "+" : ""}${comparison.severityDelta}`);
      console.log(`病灶数变化: ${comparison.lesionCountDelta > 0 ? "+" : ""}${comparison.lesionCountDelta}`);
      console.log(`时间间隔: ${Math.round(comparison.timeDelta / 1000 / 60 / 60 / 24)} 天`);
    }
  } else {
    console.log("用法:");
    console.log("  bun history-tracker.ts list [数量]");
    console.log("  bun history-tracker.ts trend [7d|30d|90d]");
    console.log("  bun history-tracker.ts compare <id1> <id2>");
  }
}
