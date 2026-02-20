#!/usr/bin/env bun
/**
 * Routing Rules Initializer - 路由规则初始化器
 *
 * 功能:
 * 1. 从 sroe_requests 提取模型使用模式
 * 2. 从 sys_quality_scores 获取 Q-scores
 * 3. 生成初始路由规则
 * 4. 写入 sys_routing_model 表
 *
 * 创建时间: 2026-02-19
 */

import { Database } from 'bun:sqlite';
import path from 'path';

interface ModelUsage {
  model: string;
  task_type: string;
  usage_count: number;
  success_count: number;
  success_rate: number;
}

interface ModelScore {
  model: string;
  satisfaction: number;
  completion_rate: number;
}

interface RoutingRule {
  rule_name: string;
  priority: number;
  conditions: any;
  target_model: string;
  fallback_model?: string;
  enabled: boolean;
  description: string;
  base_weight: number;
}

export class RoutingRulesInitializer {
  private db: Database;

  constructor(dbPath?: string) {
    const defaultPath = path.join(process.env.HOME || '.', '.solar', 'solar.db');
    this.db = new Database(dbPath || defaultPath);
    this.db.exec('PRAGMA journal_mode = WAL;');
  }

  /**
   * 获取模型使用统计
   */
  getModelUsage(): ModelUsage[] {
    return this.db.query<ModelUsage>(`
      SELECT
        selected_model as model,
        COALESCE(task_type, 'general') as task_type,
        COUNT(*) as usage_count,
        COUNT(CASE WHEN finish_reason = 'stop' THEN 1 END) as success_count,
        ROUND(COUNT(CASE WHEN finish_reason = 'stop' THEN 1 END) * 100.0 / COUNT(*), 2) as success_rate
      FROM sroe_requests
      WHERE selected_model IS NOT NULL
      GROUP BY selected_model, task_type
      HAVING usage_count >= 3
      ORDER BY task_type, usage_count DESC
    `).all();
  }

  /**
   * 获取模型 Q-scores
   */
  getModelScores(): Map<string, ModelScore> {
    const scores = this.db.query<ModelScore>(`
      SELECT
        entity_id as model,
        satisfaction,
        completion_rate
      FROM sys_quality_scores
      WHERE entity_type = 'model'
    `).all();

    return new Map(scores.map(s => [s.model, s]));
  }

  /**
   * 生成路由规则
   */
  generateRules(usage: ModelUsage[], scores: Map<string, ModelScore>): RoutingRule[] {
    const rules: RoutingRule[] = [];

    // 按任务类型分组
    const byTaskType = new Map<string, ModelUsage[]>();
    for (const u of usage) {
      if (!byTaskType.has(u.task_type)) {
        byTaskType.set(u.task_type, []);
      }
      byTaskType.get(u.task_type)!.push(u);
    }

    // 为每个任务类型生成规则
    for (const [taskType, models] of byTaskType) {
      // 按使用量 + 成功率排序
      models.sort((a, b) => {
        const scoreA = a.usage_count * (a.success_rate / 100);
        const scoreB = b.usage_count * (b.success_rate / 100);
        return scoreB - scoreA;
      });

      // 前3名作为候选
      const topModels = models.slice(0, 3);

      for (let i = 0; i < topModels.length; i++) {
        const model = topModels[i];
        const qScore = scores.get(model.model);

        const rule: RoutingRule = {
          rule_name: `${taskType}_${model.model}_priority${i + 1}`,
          priority: 100 - i * 10, // 100, 90, 80
          conditions: {
            task_type: taskType,
            complexity: i === 0 ? 'any' : (i === 1 ? 'medium' : 'low')
          },
          target_model: model.model,
          fallback_model: i < topModels.length - 1 ? topModels[i + 1].model : undefined,
          enabled: true,
          description: `${taskType} 任务第 ${i + 1} 优先级模型 (使用 ${model.usage_count} 次, 成功率 ${model.success_rate}%)`,
          base_weight: qScore ? qScore.satisfaction : 0.5
        };

        rules.push(rule);
      }
    }

    // 添加默认规则 (general 任务)
    if (!byTaskType.has('general')) {
      const generalModels = usage.filter(u => u.task_type === 'general').slice(0, 3);
      for (let i = 0; i < generalModels.length; i++) {
        const model = generalModels[i];
        const qScore = scores.get(model.model);

        rules.push({
          rule_name: `default_${model.model}_priority${i + 1}`,
          priority: 50 - i * 5,
          conditions: { task_type: 'general' },
          target_model: model.model,
          fallback_model: i < generalModels.length - 1 ? generalModels[i + 1].model : undefined,
          enabled: true,
          description: `默认规则第 ${i + 1} 优先级 (使用 ${model.usage_count} 次)`,
          base_weight: qScore ? qScore.satisfaction : 0.5
        });
      }
    }

    return rules;
  }

  /**
   * 写入路由规则到数据库
   */
  writeRules(rules: RoutingRule[]): number {
    console.log('  📝 写入路由规则...');

    const insert = this.db.prepare(`
      INSERT INTO sys_routing_model (
        rule_name, priority, conditions, target_model, fallback_model,
        enabled, description, base_weight
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);

    const transaction = this.db.transaction(() => {
      let count = 0;
      for (const rule of rules) {
        try {
          insert.run(
            rule.rule_name,
            rule.priority,
            JSON.stringify(rule.conditions),
            rule.target_model,
            rule.fallback_model || null,
            rule.enabled ? 1 : 0,
            rule.description,
            rule.base_weight
          );
          count++;
        } catch (error: any) {
          if (!error.message.includes('UNIQUE constraint failed')) {
            console.error(`    ⚠️  插入失败 [${rule.rule_name}]:`, error.message);
          }
        }
      }
      return count;
    });

    return transaction();
  }

  /**
   * 显示统计信息
   */
  displayStats(): void {
    console.log('\n📊 路由规则统计:');

    const stats = this.db.query<{
      task_type: string;
      rule_count: number;
      models: string;
    }>(`
      SELECT
        json_extract(conditions, '$.task_type') as task_type,
        COUNT(*) as rule_count,
        GROUP_CONCAT(target_model) as models
      FROM sys_routing_model
      WHERE enabled = 1
      GROUP BY json_extract(conditions, '$.task_type')
      ORDER BY rule_count DESC
    `).all();

    for (const stat of stats) {
      console.log(`  ${stat.task_type || 'general'}: ${stat.rule_count} 条规则`);
      console.log(`    模型: ${stat.models}`);
    }

    // 总数
    const total = this.db.query<{ count: number }>(`
      SELECT COUNT(*) as count FROM sys_routing_model WHERE enabled = 1
    `).get()!;

    console.log(`\n  总计: ${total.count} 条激活规则`);
  }

  /**
   * 主执行流程
   */
  async run(): Promise<void> {
    console.log('🚀 Routing Rules Initializer 启动\n');

    try {
      // 1. 获取使用统计
      console.log('📊 步骤1: 提取模型使用模式...');
      const usage = this.getModelUsage();
      console.log(`  ✅ 找到 ${usage.length} 条使用记录`);

      // 2. 获取 Q-scores
      console.log('\n📊 步骤2: 获取模型 Q-scores...');
      const scores = this.getModelScores();
      console.log(`  ✅ 找到 ${scores.size} 个模型评分`);

      // 3. 生成规则
      console.log('\n📊 步骤3: 生成路由规则...');
      const rules = this.generateRules(usage, scores);
      console.log(`  ✅ 生成 ${rules.length} 条规则`);

      // 4. 写入数据库
      const written = this.writeRules(rules);
      console.log(`  ✅ 写入 ${written} 条规则\n`);

      // 5. 显示统计
      this.displayStats();

      console.log('\n✅ 路由规则初始化完成！');

    } catch (error) {
      console.error('❌ 执行失败:', error);
      throw error;
    } finally {
      this.db.close();
    }
  }
}

// CLI 入口
if (import.meta.main) {
  const initializer = new RoutingRulesInitializer();
  await initializer.run();
}
