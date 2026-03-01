#!/usr/bin/env bun
/**
 * Solar Skill CLI
 * 技能系统命令行工具
 *
 * 用法:
 *   bun ~/.claude/core/skill-distiller/cli.ts create --name "技能名" --description "描述"
 *   bun ~/.claude/core/skill-distiller/cli.ts distill --favorite <id>
 *   bun ~/.claude/core/skill-distiller/cli.ts list [--status pending_review]
 *   bun ~/.claude/core/skill-distiller/cli.ts approve <skill_id>
 *   bun ~/.claude/core/skill-distiller/cli.ts search <query>
 *   bun ~/.claude/core/skill-distiller/cli.ts stats
 *
 * P1 新增:
 *   bun ~/.claude/core/skill-distiller/cli.ts evolve
 *   bun ~/.claude/core/skill-distiller/cli.ts report
 *   bun ~/.claude/core/skill-distiller/cli.ts semantic-search <query>
 *   bun ~/.claude/core/skill-distiller/cli.ts feedback <skill_id> --outcome success|failure
 */

import { parseArgs } from 'util';
import { Database } from 'bun:sqlite';
import {
  createSkillManually,
  distillFromFavorite,
  batchDistillFavorites
} from './distiller';
import {
  getSkill,
  updateSkillStatus,
  getPendingSkills,
  getSkillStats,
  retrieveSkills,
  getFavoriteForDistillation
} from './db';
import { evolveSkills, getEvolutionReport, updateQValue } from './evolution';
import { semanticSearch } from './embeddings';
import { reportSkillExecution } from './retriever';
// P2 imports
import {
  analyzeFailure,
  getFailurePatterns,
  batchAnalyzeFailures,
  triggerSkillImprovement
} from './failure-analyzer';
import {
  createTestCase,
  getTestCases,
  runRegressionTests,
  compareVersions,
  generateTestCases
} from './regression-tester';
import {
  publishSkill,
  subscribeSkill,
  reviewSkill,
  getMarketplaceStats,
  getRecommendedSkills,
  getAgentSkillLibrary,
  getSkillReviews
} from './marketplace';
import type { Skill } from './schema';
import type { AgentRole } from './marketplace';

// 解析命令行参数
const { values, positionals } = parseArgs({
  args: Bun.argv.slice(2),
  options: {
    name: { type: 'string', short: 'n' },
    description: { type: 'string', short: 'd' },
    layer: { type: 'string', short: 'l', default: 'domain' },
    scope: { type: 'string', short: 's', default: 'task_specific' },
    favorite: { type: 'string', short: 'f' },
    status: { type: 'string' },
    limit: { type: 'string', default: '10' },
    min_importance: { type: 'string', default: '7' },
    tags: { type: 'string', short: 't' },
    template: { type: 'string' },
    // P1 新增
    outcome: { type: 'string' },
    rating: { type: 'string' },
    comment: { type: 'string' },
    // P2 新增
    author: { type: 'string' },
    agent: { type: 'string' },
    old_version: { type: 'string' },
    new_version: { type: 'string' },
    // 通用
    json: { type: 'boolean', default: false },
    help: { type: 'boolean', short: 'h' }
  },
  strict: false
});

const command = positionals[0];

// 帮助信息
if (values.help || !command) {
  console.log(`
Solar Skill CLI - 技能系统命令行工具

命令:
  create        手动创建技能
  distill       从收藏夹蒸馏技能
  batch         批量蒸馏
  list          列出技能
  approve       审核通过技能
  reject        拒绝技能
  search        搜索技能
  show          显示技能详情
  stats         显示统计信息

P1 命令:
  evolve        执行技能进化（晋升/降级/归档）
  report        显示进化报告
  semantic-search 语义搜索
  feedback      记录技能执行反馈

P2 命令:
  analyze-failure  分析技能失败模式
  test          运行回归测试
  test-compare  比较版本差异
  publish       发布技能到市场
  subscribe     订阅技能
  review-skill  评价技能
  reviews       查看技能评价列表
  market        查看市场统计
  recommend     获取推荐技能
  library       查看牛马技能库
  improve       触发技能改进

示例:
  # 手动创建技能
  bun cli.ts create --name "调试 TypeError" --description "系统化调试 TypeError" --tags "debug,error"

  # 从收藏夹蒸馏
  bun cli.ts distill --favorite 123

  # 批量蒸馏
  bun cli.ts batch --min_importance 8 --limit 20

  # 列出待审核技能
  bun cli.ts list --status pending_review

  # 审核通过
  bun cli.ts approve skill_xxx

  # 搜索技能
  bun cli.ts search "调试"

  # P1: 技能进化
  bun cli.ts evolve
  bun cli.ts report

  # P2: 失败分析
  bun cli.ts analyze-failure skill_xxx
  bun cli.ts improve skill_xxx

  # P2: 回归测试
  bun cli.ts test skill_xxx
  bun cli.ts test-compare skill_xxx 1.0.0 2.0.0

  # P2: 技能市场
  bun cli.ts publish skill_xxx --author builder
  bun cli.ts subscribe skill_xxx --agent architect
  bun cli.ts review-skill skill_xxx --rating 5 --comment "非常好用"
  bun cli.ts market
  bun cli.ts recommend --agent builder
`);
  process.exit(0);
}

// 执行命令
switch (command) {
  case 'create':
    handleCreate();
    break;

  case 'distill':
    handleDistill();
    break;

  case 'batch':
    handleBatch();
    break;

  case 'list':
    handleList();
    break;

  case 'approve':
    handleApprove();
    break;

  case 'reject':
    handleReject();
    break;

  case 'search':
    handleSearch();
    break;

  case 'show':
    handleShow();
    break;

  case 'stats':
    handleStats();
    break;

  // P1 新增命令
  case 'evolve':
    handleEvolve();
    break;

  case 'report':
    handleReport();
    break;

  case 'semantic-search':
    handleSemanticSearch();
    break;

  case 'feedback':
    handleFeedback();
    break;

  // P2 新增命令
  case 'analyze-failure':
    handleAnalyzeFailure();
    break;

  case 'test':
    handleTest();
    break;

  case 'test-compare':
    handleTestCompare();
    break;

  case 'publish':
    handlePublish();
    break;

  case 'subscribe':
    handleSubscribe();
    break;

  case 'review-skill':
    handleReviewSkill();
    break;

  case 'market':
    handleMarket();
    break;

  case 'recommend':
    handleRecommend();
    break;

  case 'library':
    handleLibrary();
    break;

  case 'improve':
    handleImprove();
    break;

  case 'reviews':
    handleReviews();
    break;

  default:
    console.error(`未知命令: ${command}`);
    process.exit(1);
}

// === 命令处理函数 ===

function handleCreate(): void {
  if (!values.name || !values.description) {
    console.error('❌ 缺少必要参数: --name 和 --description');
    process.exit(1);
  }

  const skillId = createSkillManually({
    name: values.name,
    description: values.description,
    layer: values.layer as Skill['layer'],
    scope: values.scope as Skill['scope'],
    tags: values.tags?.split(',').map(t => t.trim()),
    llm_prompt_template: values.template,
    skill_type: 'template'
  });

  console.log(`✅ 技能已创建: ${skillId}`);
  console.log(`   状态: pending_review (等待审核)`);
  console.log(`   审核命令: bun cli.ts approve ${skillId}`);
}

async function handleDistill(): Promise<void> {
  const favoriteId = parseInt(values.favorite || '0');

  if (!favoriteId) {
    console.error('❌ 缺少参数: --favorite <id>');
    process.exit(1);
  }

  // 先显示收藏内容
  const favorite = getFavoriteForDistillation(favoriteId);
  if (!favorite) {
    console.error(`❌ 收藏 ${favoriteId} 不存在`);
    process.exit(1);
  }

  console.log(`\n📖 收藏内容:`);
  console.log(`   标题: ${favorite.title}`);
  console.log(`   问题: ${favorite.question?.slice(0, 100)}...`);
  console.log(`   标签: ${favorite.tags.join(', ')}\n`);

  console.log(`🔄 正在调用审判官蒸馏...`);

  const result = await distillFromFavorite(favoriteId, {
    layer: values.layer as Skill['layer']
  });

  if (result.success && result.skill) {
    console.log(`\n✅ 蒸馏成功!`);
    console.log(`   技能ID: ${result.skill.skill_id}`);
    console.log(`   名称: ${result.skill.name}`);
    console.log(`   描述: ${result.skill.description}`);
    console.log(`   层级: ${result.skill.layer}`);
    console.log(`   置信度: ${(result.confidence * 100).toFixed(1)}%`);
    console.log(`\n   状态: pending_review (等待审核)`);
    console.log(`   审核命令: bun cli.ts approve ${result.skill.skill_id}`);
  } else {
    console.log(`\n❌ 蒸馏失败: ${result.error}`);
    console.log(`   置信度: ${(result.confidence * 100).toFixed(1)}%`);
  }
}

async function handleBatch(): Promise<void> {
  const limit = parseInt(values.limit);
  const minImportance = parseInt(values.min_importance);

  console.log(`\n🔄 批量蒸馏配置:`);
  console.log(`   最低重要性: ${minImportance}`);
  console.log(`   数量限制: ${limit}`);
  console.log(`   目标层级: ${values.layer || '自动'}\n`);

  const result = await batchDistillFavorites({
    min_importance: minImportance,
    limit,
    layer: values.layer as Skill['layer']
  });

  console.log(`\n📊 批量蒸馏完成:`);
  console.log(`   成功: ${result.success}`);
  console.log(`   失败: ${result.failed}`);
  console.log(`   技能ID: ${result.skills.join(', ')}`);
}

function handleList(): void {
  const status = values.status;

  let skills: Skill[];

  if (status === 'pending_review') {
    skills = getPendingSkills();
    console.log(`\n📋 待审核技能 (${skills.length}):\n`);
  } else {
    const result = retrieveSkills({
      query: '',
      context: status ? { tags: [status] } : undefined,
      top_k: parseInt(values.limit)
    });
    skills = result.skills;
    console.log(`\n📋 技能列表 (${skills.length}):\n`);
  }

  if (skills.length === 0) {
    console.log('   无数据');
    return;
  }

  for (const skill of skills) {
    const statusIcon = {
      active: '✅',
      pending_review: '⏳',
      deprecated: '❌',
      archived: '📦'
    }[skill.status] || '❓';

    console.log(`${statusIcon} ${skill.skill_id}`);
    console.log(`   名称: ${skill.name}`);
    console.log(`   层级: ${skill.layer} | 成功: ${skill.success_count} | 失败: ${skill.failure_count}`);
    console.log(`   描述: ${skill.description?.slice(0, 60)}...`);
    console.log('');
  }
}

function handleApprove(): void {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  const success = updateSkillStatus(skillId, 'active');

  if (success) {
    console.log(`✅ 技能已审核通过: ${skillId}`);
    console.log(`   名称: ${skill.name}`);
    console.log(`   现在可以被检索和使用`);
  } else {
    console.error(`❌ 更新失败`);
  }
}

function handleReject(): void {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const success = updateSkillStatus(skillId, 'deprecated');

  if (success) {
    console.log(`❌ 技能已拒绝/弃用: ${skillId}`);
  } else {
    console.error(`❌ 更新失败`);
  }
}

function handleSearch(): void {
  const query = positionals.slice(1).join(' ');

  if (!query) {
    console.error('❌ 缺少搜索关键词');
    process.exit(1);
  }

  const result = retrieveSkills({
    query,
    top_k: parseInt(values.limit)
  });

  console.log(`\n🔍 搜索结果: "${query}" (${result.total} 条, ${result.query_time_ms}ms)\n`);

  if (result.skills.length === 0) {
    console.log('   未找到匹配技能');
    return;
  }

  for (const skill of result.skills) {
    console.log(`📌 ${skill.name} (${skill.skill_id})`);
    console.log(`   ${skill.description?.slice(0, 80)}...`);
    console.log(`   层级: ${skill.layer} | Q值: ${skill.q_value.toFixed(2)} | 成功率: ${skill.success_count}/${skill.success_count + skill.failure_count}`);
    console.log('');
  }
}

function handleShow(): void {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);

  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  if (values.json) {
    console.log(JSON.stringify(skill, null, 2));
    return;
  }

  console.log(`\n📌 技能详情\n`);
  console.log(`ID:          ${skill.skill_id}`);
  console.log(`名称:        ${skill.name}`);
  console.log(`描述:        ${skill.description}`);
  console.log(`类型:        ${skill.skill_type}`);
  console.log(`层级:        ${skill.layer}`);
  console.log(`范围:        ${skill.scope}`);
  console.log(`状态:        ${skill.status}`);
  console.log(`版本:        ${skill.version}`);
  console.log(`来源:        ${skill.source}`);
  console.log(`\n统计:`);
  console.log(`  成功:      ${skill.success_count}`);
  console.log(`  失败:      ${skill.failure_count}`);
  console.log(`  Q值:       ${skill.q_value.toFixed(3)}`);
  console.log(`  验证:      ${skill.validated ? '是' : '否'}`);

  if (skill.trigger_keywords?.length) {
    console.log(`\n触发关键词:  ${skill.trigger_keywords.join(', ')}`);
  }

  if (skill.tags?.length) {
    console.log(`标签:        ${skill.tags.join(', ')}`);
  }

  if (skill.llm_prompt_template) {
    console.log(`\n执行模板:`);
    console.log('```');
    console.log(skill.llm_prompt_template);
    console.log('```');
  }
}

function handleStats(): void {
  const stats = getSkillStats();

  console.log(`\n📊 技能库统计\n`);
  console.log(`总计: ${stats.total} 个技能\n`);

  console.log(`按状态:`);
  for (const [status, count] of Object.entries(stats.by_status)) {
    console.log(`  ${status}: ${count}`);
  }

  console.log(`\n按层级:`);
  for (const [layer, count] of Object.entries(stats.by_layer)) {
    console.log(`  ${layer}: ${count}`);
  }

  console.log(`\n按来源 (前5):`);
  const sortedSources = Object.entries(stats.by_source)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  for (const [source, count] of sortedSources) {
    console.log(`  ${source}: ${count}`);
  }
}

// === P1 新增命令处理函数 ===

async function handleEvolve(): Promise<void> {
  console.log(`\n🔄 执行技能进化...\n`);

  const result = await evolveSkills();

  console.log(`📊 进化结果:`);
  console.log(`   晋升 (task_specific → general): ${result.promoted.length}`);
  if (result.promoted.length > 0) {
    for (const id of result.promoted) {
      console.log(`      - ${id}`);
    }
  }

  console.log(`   降级 (active → deprecated): ${result.degraded.length}`);
  if (result.degraded.length > 0) {
    for (const id of result.degraded) {
      console.log(`      - ${id}`);
    }
  }

  console.log(`   归档 (active → archived): ${result.archived.length}`);
  if (result.archived.length > 0) {
    for (const id of result.archived) {
      console.log(`      - ${id}`);
    }
  }

  console.log(`\n✅ 进化完成`);
}

function handleReport(): void {
  console.log(`\n📊 技能进化报告\n`);

  const report = getEvolutionReport();

  console.log(`\n🎯 晋升候选 (高成功率，可升级为通用技能):`);
  if (report.candidates_for_promotion.length === 0) {
    console.log(`   无`);
  } else {
    for (const c of report.candidates_for_promotion) {
      console.log(`   📈 ${c.name} (${c.skill_id})`);
      console.log(`      成功率: ${(c.score * 100).toFixed(1)}%`);
    }
  }

  console.log(`\n⚠️  降级候选 (高失败率，需关注):`);
  if (report.candidates_for_degradation.length === 0) {
    console.log(`   无`);
  } else {
    for (const c of report.candidates_for_degradation) {
      console.log(`   📉 ${c.name} (${c.skill_id})`);
      console.log(`      失败率: ${(c.failure_rate * 100).toFixed(1)}%`);
    }
  }

  console.log(`\n📦 归档候选 (长期未使用):`);
  if (report.candidates_for_archive.length === 0) {
    console.log(`   无`);
  } else {
    for (const c of report.candidates_for_archive) {
      console.log(`   🗄️  ${c.name} (${c.skill_id})`);
      console.log(`      最后使用: ${c.last_used}`);
    }
  }
}

async function handleSemanticSearch(): Promise<void> {
  const query = positionals.slice(1).join(' ');

  if (!query) {
    console.error('❌ 缺少搜索关键词');
    process.exit(1);
  }

  console.log(`\n🔍 语义搜索: "${query}"\n`);
  console.log(`   生成查询向量...`);

  // 获取所有活跃技能
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const skills = db.prepare(`
    SELECT * FROM sys_skill_bank WHERE status = 'active' LIMIT 50
  `).all() as unknown[];
  db.close();

  const parsedSkills = skills.map(row => {
    const r = row as Record<string, unknown>;
    return {
      skill_id: r.skill_id as string,
      name: r.name as string,
      description: r.description as string,
      layer: r.layer as string,
      tags: JSON.parse(r.tags as string || '[]'),
      success_count: r.success_count as number || 0,
      failure_count: r.failure_count as number || 0,
      q_value: r.q_value as number || 0.5
    } as Skill;
  });

  console.log(`   比较语义相似度...`);
  const results = await semanticSearch(query, parsedSkills, parseInt(values.limit));

  console.log(`\n   找到 ${results.length} 个相关技能:\n`);

  for (const { skill, score } of results) {
    console.log(`📌 ${skill.name} (${skill.skill_id})`);
    console.log(`   相似度: ${(score * 100).toFixed(1)}%`);
    console.log(`   ${skill.description?.slice(0, 80)}...`);
    console.log('');
  }
}

function handleFeedback(): void {
  const skillId = positionals[1];
  const outcome = values.outcome || 'success';

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  const success = outcome === 'success';

  // 记录反馈
  reportSkillExecution(skillId, success, {
    user_rating: values.rating ? parseInt(values.rating) : undefined,
    comment: values.comment
  });

  // 更新 Q 值
  updateQValue(skillId, success);

  console.log(`\n✅ 反馈已记录`);
  console.log(`   技能: ${skill.name}`);
  console.log(`   结果: ${success ? '成功' : '失败'}`);
  console.log(`   Q值已更新`);
}

// === P2 新增命令处理函数 ===

function handleAnalyzeFailure(): void {
  const skillId = positionals[1];

  if (!skillId) {
    // 批量分析
    console.log(`\n🔍 批量失败分析\n`);

    const result = batchAnalyzeFailures();

    console.log(`   分析了 ${result.analyzed} 个高失败率技能\n`);

    if (result.top_issues.length === 0) {
      console.log(`   ✅ 没有发现高失败率技能`);
      return;
    }

    for (const issue of result.top_issues) {
      console.log(`   ⚠️  ${issue.name} (${issue.skill_id})`);
      console.log(`      失败率: ${(issue.failure_rate * 100).toFixed(1)}%`);
      console.log(`      类别: ${issue.category}`);
      console.log('');
    }
    return;
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  console.log(`\n🔍 失败分析: ${skill.name}\n`);

  const patterns = getFailurePatterns(skillId);

  if (patterns.length === 0) {
    console.log(`   ✅ 该技能没有失败记录`);
    return;
  }

  for (const pattern of patterns) {
    console.log(`   📉 ${pattern.pattern}`);
    console.log(`      次数: ${pattern.count}`);
    console.log(`      根因: ${pattern.root_cause}`);
    console.log(`      建议: ${pattern.fix_suggestion}`);
    console.log('');
  }
}

async function handleTest(): Promise<void> {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  console.log(`\n🧪 回归测试: ${skill.name}\n`);

  // 获取测试用例
  let testCases = getTestCases(skillId);

  if (testCases.length === 0) {
    console.log(`   ⚠️  没有测试用例，自动生成...`);
    testCases = generateTestCases(skill);
    for (const tc of testCases) {
      createTestCase({
        skill_id: tc.skill_id,
        name: tc.name,
        input: tc.input,
        expected_output: tc.expected_output,
        validation_criteria: tc.validation_criteria
      });
    }
    console.log(`   生成了 ${testCases.length} 个测试用例\n`);
  }

  // 运行测试
  const result = await runRegressionTests(skillId);

  console.log(`   总测试: ${result.total}`);
  console.log(`   ✅ 通过: ${result.passed}`);
  console.log(`   ❌ 失败: ${result.failed}`);

  if (result.failed > 0) {
    console.log(`\n   失败详情:`);
    for (const r of result.results.filter(x => !x.passed)) {
      console.log(`      - ${r.test_id}: ${r.error_message}`);
    }
  }
}

function handleTestCompare(): void {
  const skillId = positionals[1];
  const oldVersion = values.old_version || positionals[2];
  const newVersion = values.new_version || positionals[3];

  if (!skillId || !oldVersion || !newVersion) {
    console.error('❌ 缺少参数: skill_id, old_version, new_version');
    console.log('   用法: bun cli.ts test-compare skill_xxx 1.0.0 2.0.0');
    process.exit(1);
  }

  console.log(`\n📊 版本对比: ${oldVersion} → ${newVersion}\n`);

  const report = compareVersions(skillId, oldVersion, newVersion);

  console.log(`   技能: ${report.skill_id}`);
  console.log(`   总测试: ${report.total_tests}`);
  console.log(`   通过: ${report.passed}`);
  console.log(`   失败: ${report.failed}`);

  if (report.regressions.length > 0) {
    console.log(`\n   ⚠️  回退:`);
    for (const r of report.regressions) {
      console.log(`      - ${r}`);
    }
  }

  if (report.improvements.length > 0) {
    console.log(`\n   ✅ 改进:`);
    for (const i of report.improvements) {
      console.log(`      - ${i}`);
    }
  }
}

function handlePublish(): void {
  const skillId = positionals[1];
  const authorAgent = (values.author || 'builder') as AgentRole;

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const validRoles = ['inquisitor', 'builder', 'architect', 'explorer', 'creator', 'verifier'];
  if (!validRoles.includes(authorAgent)) {
    console.error(`❌ 无效的牛马角色: ${authorAgent}`);
    console.log(`   有效角色: ${validRoles.join(', ')}`);
    process.exit(1);
  }

  console.log(`\n📤 发布技能到市场\n`);

  const result = publishSkill(skillId, authorAgent);

  if (result.success) {
    console.log(`   ✅ ${result.message}`);
    console.log(`   发布ID: ${result.publication_id}`);
  } else {
    console.log(`   ❌ ${result.message}`);
  }
}

function handleSubscribe(): void {
  const skillId = positionals[1];
  const agentRole = (values.agent || 'builder') as AgentRole;

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const validRoles = ['inquisitor', 'builder', 'architect', 'explorer', 'creator', 'verifier'];
  if (!validRoles.includes(agentRole)) {
    console.error(`❌ 无效的牛马角色: ${agentRole}`);
    console.log(`   有效角色: ${validRoles.join(', ')}`);
    process.exit(1);
  }

  console.log(`\n📥 订阅技能\n`);

  const result = subscribeSkill(skillId, agentRole);

  if (result.success) {
    console.log(`   ✅ ${result.message}`);
  } else {
    console.log(`   ❌ ${result.message}`);
  }
}

function handleReviewSkill(): void {
  const skillId = positionals[1];
  const rating = values.rating ? parseInt(values.rating) : 5;
  const comment = values.comment || '';
  const reviewerAgent = (values.agent || 'builder') as AgentRole;

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  if (rating < 1 || rating > 5) {
    console.error('❌ 评分必须在 1-5 之间');
    process.exit(1);
  }

  console.log(`\n⭐ 评价技能\n`);

  const result = reviewSkill(skillId, reviewerAgent, rating, comment);

  if (result.success) {
    console.log(`   ✅ ${result.message}`);
    console.log(`   评分: ${'⭐'.repeat(rating)}`);
    if (comment) {
      console.log(`   评论: ${comment}`);
    }
  } else {
    console.log(`   ❌ ${result.message}`);
  }
}

function handleMarket(): void {
  console.log(`\n🏪 技能市场统计\n`);

  const stats = getMarketplaceStats();

  console.log(`   📊 总发布数: ${stats.total_publications}`);
  console.log(`   📥 总订阅数: ${stats.total_downloads}`);
  console.log(`   ⭐ 平均评分: ${stats.avg_rating.toFixed(2)}`);

  if (stats.top_skills.length > 0) {
    console.log(`\n   🔥 热门技能:`);
    for (const s of stats.top_skills.slice(5)) {
      console.log(`      - ${s.name}: ${s.downloads} 订阅, ⭐ ${s.rating.toFixed(1)}`);
    }
  }

  if (stats.top_authors.length > 0) {
    console.log(`\n   🏆 热门作者:`);
    for (const a of stats.top_authors) {
      console.log(`      - ${a.agent}: ${a.publications} 技能, ⭐ ${a.avg_rating.toFixed(1)}`);
    }
  }
}

function handleRecommend(): void {
  const agentRole = (values.agent || 'builder') as AgentRole;
  const limit = parseInt(values.limit) || 5;

  const validRoles = ['inquisitor', 'builder', 'architect', 'explorer', 'creator', 'verifier'];
  if (!validRoles.includes(agentRole)) {
    console.error(`❌ 无效的牛马角色: ${agentRole}`);
    console.log(`   有效角色: ${validRoles.join(', ')}`);
    process.exit(1);
  }

  console.log(`\n💡 为 ${agentRole} 推荐技能\n`);

  const recommendations = getRecommendedSkills(agentRole, limit);

  if (recommendations.length === 0) {
    console.log(`   暂无推荐`);
    return;
  }

  for (const r of recommendations) {
    console.log(`   📌 ${r.name} (${r.skill_id})`);
    console.log(`      推荐分: ${r.score.toFixed(2)}`);
    console.log(`      ${r.description?.slice(0, 60)}...`);
    console.log('');
  }
}

function handleLibrary(): void {
  const agentRole = (values.agent || 'builder') as AgentRole;

  const validRoles = ['inquisitor', 'builder', 'architect', 'explorer', 'creator', 'verifier'];
  if (!validRoles.includes(agentRole)) {
    console.error(`❌ 无效的牛马角色: ${agentRole}`);
    console.log(`   有效角色: ${validRoles.join(', ')}`);
    process.exit(1);
  }

  console.log(`\n📚 ${agentRole} 的技能库\n`);

  const library = getAgentSkillLibrary(agentRole);

  console.log(`   📥 订阅的技能 (${library.subscribed.length}):`);
  if (library.subscribed.length === 0) {
    console.log(`      无`);
  } else {
    for (const s of library.subscribed) {
      console.log(`      - ${s.name}: 使用 ${s.usage_count} 次`);
    }
  }

  console.log(`\n   📤 发布的技能 (${library.owned.length}):`);
  if (library.owned.length === 0) {
    console.log(`      无`);
  } else {
    for (const s of library.owned) {
      console.log(`      - ${s.name}: ${s.downloads} 订阅`);
    }
  }
}

async function handleImprove(): Promise<void> {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  console.log(`\n🔧 触发技能改进: ${skill.name}\n`);

  const result = await triggerSkillImprovement(skillId);

  if (result.success) {
    console.log(`   ✅ ${result.message}`);
    if (result.new_skill_id) {
      console.log(`   新技能ID: ${result.new_skill_id}`);
      console.log(`   状态: pending_review (需要人工完善后审核)`);
    }
  } else {
    console.log(`   ❌ ${result.message}`);
  }
}

function handleReviews(): void {
  const skillId = positionals[1];

  if (!skillId) {
    console.error('❌ 缺少参数: skill_id');
    process.exit(1);
  }

  const skill = getSkill(skillId);
  if (!skill) {
    console.error(`❌ 技能不存在: ${skillId}`);
    process.exit(1);
  }

  console.log(`\n💬 ${skill.name} 的评价列表\n`);

  const reviews = getSkillReviews(skillId);

  if (reviews.length === 0) {
    console.log(`   暂无评价`);
    return;
  }

  for (const r of reviews) {
    console.log(`   ⭐ ${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)} by ${r.reviewer_agent}`);
    console.log(`      ${r.comment || '(无评论)'}`);
    console.log(`      ${r.created_at}`);
    console.log('');
  }
}
