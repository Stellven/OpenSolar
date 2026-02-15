/**
 * Persona Drift Guard v1.0 - 人格漂移防护
 *
 * 问题: 长对话中人格逐渐丢失，输出变得机械
 * 对策: 定期检测并刷新人格参数
 *
 * 触发条件:
 *   - 对话轮次 >= 5
 *   - 上下文使用 >= 65%
 *   - 时间超过 30 分钟
 */

import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { ROLES_V3, ControlKnobs } from './persona-router';

// 旋钮显示名称
function getKnobDisplayName(key: keyof ControlKnobs): string {
  const names: Record<keyof ControlKnobs, string> = {
    rigor: '证据洁癖',
    skepticism: '怀疑强度',
    exploration: '发散度',
    decisiveness: '决断性',
    riskAversion: '风险厌恶',
    toolFirst: '工具倾向',
    compression: '压缩率',
    selfCritique: '自检强度',
    socialEmpathy: '同理心',
    competitiveness: '竞技性'
  };
  return names[key] || key;
}

const DB_PATH = `${homedir()}/.solar/solar.db`;
const db = new Database(DB_PATH);

// ============================================================
// Schema 初始化
// ============================================================

db.run(`
  CREATE TABLE IF NOT EXISTS persona_drift_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trigger_type TEXT NOT NULL,     -- 'turn_count' | 'token_usage' | 'time_elapsed' | 'manual'
    trigger_value REAL,
    role_before TEXT,
    knobs_before TEXT,              -- JSON
    action_taken TEXT,              -- 'reminder' | 'reload' | 'checkpoint'
    effectiveness REAL,             -- 0-1, 用户反馈
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);

// ============================================================
// 配置
// ============================================================

export const DRIFT_CONFIG = {
  // 触发阈值
  thresholds: {
    turnCount: 5,              // 对话轮次
    tokenUsage: 0.65,          // 上下文使用率
    timeElapsed: 30 * 60 * 1000  // 时间 (ms)
  },

  // 当前激活的人格
  activeRole: 'critic',       // 默认角色
  activeKnobs: {} as Record<string, number>,

  // 会话状态
  sessionStart: Date.now(),
  turnCount: 0,
  lastRefresh: Date.now()
};

// ============================================================
// 漂移检测
// ============================================================

export interface DriftCheckResult {
  needsRefresh: boolean;
  triggers: string[];
  severity: 'none' | 'low' | 'medium' | 'high';
  recommendation: string;
}

/**
 * 检查是否需要人格刷新
 */
export function checkDrift(
  turnCount?: number,
  tokenUsage?: number,
  timeElapsed?: number
): DriftCheckResult {
  const tc = turnCount ?? DRIFT_CONFIG.turnCount;
  const tu = tokenUsage ?? 0;
  const te = timeElapsed ?? (Date.now() - DRIFT_CONFIG.sessionStart);

  const triggers: string[] = [];
  let severity: 'none' | 'low' | 'medium' | 'high' = 'none';

  // 检查轮次
  if (tc >= DRIFT_CONFIG.thresholds.turnCount) {
    triggers.push(`轮次(${tc}>=${DRIFT_CONFIG.thresholds.turnCount})`);
    severity = 'low';
  }

  // 检查上下文
  if (tu >= DRIFT_CONFIG.thresholds.tokenUsage) {
    triggers.push(`上下文(${(tu * 100).toFixed(0)}%>=${DRIFT_CONFIG.thresholds.tokenUsage * 100}%)`);
    severity = severity === 'low' ? 'medium' : 'low';
  }

  // 检查时间
  if (te >= DRIFT_CONFIG.thresholds.timeElapsed) {
    const minutes = Math.floor(te / 60000);
    triggers.push(`时间(${minutes}分钟>=30分钟)`);
    severity = 'high';
  }

  // 多重触发升级严重度
  if (triggers.length >= 2) {
    severity = 'high';
  }

  return {
    needsRefresh: triggers.length > 0,
    triggers,
    severity,
    recommendation: getRecommendation(severity)
  };
}

function getRecommendation(severity: 'none' | 'low' | 'medium' | 'high'): string {
  switch (severity) {
    case 'high':
      return '强烈建议立即刷新人格，输出可能已经严重漂移';
    case 'medium':
      return '建议刷新人格，保持输出风格一致';
    case 'low':
      return '可以刷新人格作为预防';
    default:
      return '人格状态正常';
  }
}

// ============================================================
// 刷新动作
// ============================================================

export interface RefreshResult {
  action: 'reminder' | 'reload' | 'checkpoint';
  message: string;
  role: string;
  knobs: Record<string, number>;
  logged: boolean;
}

/**
 * 生成人格刷新提醒
 */
export function generateReminder(role?: string): RefreshResult {
  const r = role ?? DRIFT_CONFIG.activeRole;
  const roleConfig = ROLES_V3[r];

  if (!roleConfig) {
    return {
      action: 'reminder',
      message: `⚠️ 人格提醒: 未知角色 ${r}`,
      role: r,
      knobs: {},
      logged: false
    };
  }

  const knobs = roleConfig.knobs;
  const lines: string[] = [];

  lines.push('┌─────────────────────────────────────────────────────────────────┐');
  lines.push('│  🔄 人格刷新提醒                                                │');
  lines.push('├─────────────────────────────────────────────────────────────────┤');
  lines.push(`│  角色: ${r.padEnd(53)}│`);
  lines.push(`│  风格: ${roleConfig.style.tone.padEnd(53)}│`);
  lines.push('│                                                                 │');
  lines.push('│  旋钮:                                                          │');

  for (const [key, value] of Object.entries(knobs)) {
    if (value !== undefined) {
      const name = getKnobDisplayName(key as keyof typeof knobs);
      const bar = '█'.repeat(value) + '░'.repeat(5 - value);
      lines.push(`│    ${name.padEnd(8)} [${bar}] ${value}      │`);
    }
  }

  lines.push('│                                                                 │');
  lines.push('│  禁止: 冷冰冰纯表格、机械回复、没态度流水账                     │');
  lines.push('│  必须: 数据配点评、表格配人话、像跟昊哥聊天                     │');
  lines.push('└─────────────────────────────────────────────────────────────────┘');

  // 更新状态
  DRIFT_CONFIG.activeRole = r;
  DRIFT_CONFIG.activeKnobs = knobs as Record<string, number>;
  DRIFT_CONFIG.lastRefresh = Date.now();

  return {
    action: 'reminder',
    message: lines.join('\n'),
    role: r,
    knobs: knobs as Record<string, number>,
    logged: true
  };
}

/**
 * 记录刷新日志
 */
export function logRefresh(
  sessionId: string,
  triggerType: 'turn_count' | 'token_usage' | 'time_elapsed' | 'manual',
  triggerValue: number,
  action: 'reminder' | 'reload' | 'checkpoint'
): void {
  db.run(`
    INSERT INTO persona_drift_log
    (session_id, trigger_type, trigger_value, role_before, knobs_before, action_taken)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [
    sessionId,
    triggerType,
    triggerValue,
    DRIFT_CONFIG.activeRole,
    JSON.stringify(DRIFT_CONFIG.activeKnobs),
    action
  ]);
}

/**
 * 获取刷新统计
 */
export function getRefreshStats(): {
  totalRefreshes: number;
  byTrigger: Record<string, number>;
  avgEffectiveness: number;
  lastRefresh: string | null;
} {
  const stats = db.query(`
    SELECT
      COUNT(*) as total,
      trigger_type,
      AVG(effectiveness) as avg_eff,
      MAX(created_at) as last_refresh
    FROM persona_drift_log
    GROUP BY trigger_type
  `).all() as any[];

  const byTrigger: Record<string, number> = {};
  let total = 0;
  let totalEff = 0;
  let lastRefresh: string | null = null;

  for (const row of stats) {
    byTrigger[row.trigger_type] = row.total;
    total += row.total;
    totalEff += (row.avg_eff || 0) * row.total;
    lastRefresh = row.last_refresh;
  }

  return {
    totalRefreshes: total,
    byTrigger,
    avgEffectiveness: total > 0 ? totalEff / total : 0,
    lastRefresh
  };
}

// ============================================================
// 输出质量检测
// ============================================================

export interface QualityCheck {
  hasPersonality: boolean;
  hasAttitude: boolean;
  isMechanical: boolean;
  score: number;
  issues: string[];
}

/**
 * 检测输出是否有人格特征
 */
export function checkOutputQuality(output: string): QualityCheck {
  const issues: string[] = [];
  let score = 1.0;
  const trimmed = output.trim();

  // 人格标记词
  const personalityMarkers = ['嘿嘿', '哈哈', '嗯', '哦', '呀', '吧', '嘛', '啦', '呢',
    '我觉得', '我认为', '不妨', '值得', '搞定', '挺', '蛮', '稍微', '其实'];

  // 态度标记词
  const attitudeMarkers = ['好', '不错', '很好', '太棒', '优秀', '问题', '风险', '注意',
    '小心', '建议', '推荐', '可以', '应该', '最好'];

  // 检查是否有人格
  const hasPersonality = personalityMarkers.some(m => trimmed.includes(m));

  // 检查是否有态度
  const hasAttitude = attitudeMarkers.some(m => trimmed.includes(m));

  // 机械回复检测：短 + 无人格 + 无态度
  if (trimmed.length < 30 && !hasPersonality && !hasAttitude) {
    issues.push('短回复且无人格/态度: "' + trimmed.substring(0, 20) + '..."');
    score -= 0.3;
  }

  // 极短确认式回复 (< 10字符)
  const shortConfirmPatterns = [/^完成[！!.]*$/, /^已[更新保存完成]*[。.]*$/, /^OK$/i, /^好[的]?$/];
  for (const p of shortConfirmPatterns) {
    if (p.test(trimmed)) {
      issues.push('极短确认式回复');
      score -= 0.4;
      break;
    }
  }

  // 检测纯表格（没有文字点评）
  const tableLines = (output.match(/^\|.*\|$/gm) || []).length;
  const totalLines = output.split('\n').filter(l => l.trim()).length;

  if (tableLines > 3 && tableLines / totalLines > 0.8) {
    issues.push('纯表格无点评');
    score -= 0.2;
  }

  // 长文本但无人格/态度
  if (trimmed.length > 100 && !hasPersonality) {
    issues.push('长文本缺少人格标记');
    score -= 0.1;
  }

  if (trimmed.length > 200 && !hasAttitude) {
    issues.push('长文本缺少态度表达');
    score -= 0.1;
  }

  return {
    hasPersonality,
    hasAttitude,
    isMechanical: issues.length > 0,
    score: Math.max(0, score),
    issues
  };
}

// ============================================================
// Hook 集成
// ============================================================

/**
 * 生成 Hook 脚本内容
 */
export function generateHookScript(): string {
  return `#!/bin/bash
# persona-drift-reminder.sh
# 在对话轮次达到阈值时提醒刷新人格

TURN_COUNT=\${CLAUDE_TURN_COUNT:-0}
SESSION_START=\${CLAUDE_SESSION_START:-0}

# 检查是否需要提醒
if [ "$TURN_COUNT" -ge 5 ]; then
    # 每5轮提醒一次
    if [ $((TURN_COUNT % 5)) -eq 0 ]; then
        echo ""
        echo "┌─────────────────────────────────────────────────────────────────┐"
        echo "│  🔄 人格刷新提醒 (轮次: $TURN_COUNT)                            │"
        echo "├─────────────────────────────────────────────────────────────────┤"
        echo "│  长对话可能导致人格漂移，建议:                                  │"
        echo "│  1. 检查输出是否保持风格一致                                    │"
        echo "│  2. 必要时运行: bun persona-drift-guard.ts refresh              │"
        echo "└─────────────────────────────────────────────────────────────────┘"
        echo ""
    fi
fi

exit 0
`;
}

// ============================================================
// CLI
// ============================================================

if (import.meta.main) {
  const cmd = process.argv[2];

  switch (cmd) {
    case 'check': {
      const turnCount = parseInt(process.argv[3]) || DRIFT_CONFIG.turnCount;
      const tokenUsage = parseFloat(process.argv[4]) || 0;
      const result = checkDrift(turnCount, tokenUsage);

      console.log('\n🔍 人格漂移检测:\n');
      console.log(`  需要刷新: ${result.needsRefresh ? '是' : '否'}`);
      console.log(`  严重程度: ${result.severity}`);
      console.log(`  触发因素: ${result.triggers.length > 0 ? result.triggers.join(', ') : '无'}`);
      console.log(`  建议: ${result.recommendation}`);
      break;
    }

    case 'refresh': {
      const role = process.argv[3] || 'critic';
      const result = generateReminder(role);
      console.log('\n' + result.message);
      break;
    }

    case 'quality': {
      const text = process.argv.slice(3).join(' ') || '完成！已更新。';
      const result = checkOutputQuality(text);

      console.log('\n📊 输出质量检测:\n');
      console.log(`  有人格: ${result.hasPersonality ? '✓' : '✗'}`);
      console.log(`  有态度: ${result.hasAttitude ? '✓' : '✗'}`);
      console.log(`  机械回复: ${result.isMechanical ? '✗' : '✓'}`);
      console.log(`  评分: ${(result.score * 100).toFixed(0)}%`);

      if (result.issues.length > 0) {
        console.log(`\n  问题:`);
        result.issues.forEach(i => console.log(`    - ${i}`));
      }
      break;
    }

    case 'stats': {
      const stats = getRefreshStats();
      console.log('\n📊 刷新统计:\n');
      console.log(`  总刷新次数: ${stats.totalRefreshes}`);
      console.log(`  平均效果: ${(stats.avgEffectiveness * 100).toFixed(0)}%`);
      console.log(`  最近刷新: ${stats.lastRefresh || '无'}`);
      console.log(`\n  按触发类型:`);
      for (const [trigger, count] of Object.entries(stats.byTrigger)) {
        console.log(`    ${trigger}: ${count}`);
      }
      break;
    }

    case 'hook': {
      console.log(generateHookScript());
      break;
    }

    case 'roles': {
      console.log('\n📋 可用角色:\n');
      for (const [name, config] of Object.entries(ROLES_V3)) {
        console.log(`  ${name.padEnd(15)} - ${config.style.tone}`);
      }
      console.log('\n使用: bun persona-drift-guard.ts refresh <role>');
      break;
    }

    default:
      console.log(`
🔄 Persona Drift Guard - 人格漂移防护

用法:
  bun persona-drift-guard.ts check [turns] [tokenUsage]  # 检查是否需要刷新
  bun persona-drift-guard.ts refresh [role]              # 生成刷新提醒
  bun persona-drift-guard.ts quality <text>              # 检测输出质量
  bun persona-drift-guard.ts stats                       # 查看刷新统计
  bun persona-drift-guard.ts hook                        # 生成 Hook 脚本
  bun persona-drift-guard.ts roles                       # 列出可用角色

触发条件:
  - 对话轮次 >= 5
  - 上下文使用 >= 65%
  - 时间超过 30 分钟

示例:
  bun persona-drift-guard.ts check 6 0.7
  bun persona-drift-guard.ts refresh architect
  bun persona-drift-guard.ts quality "完成！已更新。"
`);
  }
}

export default {
  DRIFT_CONFIG,
  checkDrift,
  generateReminder,
  logRefresh,
  getRefreshStats,
  checkOutputQuality,
  generateHookScript
};
