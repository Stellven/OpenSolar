/**
 * Solar Skill System - 模块导出
 *
 * 使用方式:
 *   import { ... } from '~/.claude/core/skill-distiller';
 */

// 类型定义
export type {
  Skill,
  SkillLayer,
  SkillScope,
  SkillStatus,
  SkillType,
  SkillParameter,
  EmbeddedTestCase,
  TestCase,
  DistillationRequest,
  DistillationResult,
  RetrievalRequest,
  RetrievalResult,
  SkillFeedback
} from './schema';

// 数据库操作
export {
  createSkill,
  getSkill,
  updateSkillStatus,
  recordSkillUsage,
  retrieveSkills,
  getPendingSkills,
  getSkillStats,
  getFavoriteForDistillation
} from './db';

// 蒸馏功能
export {
  distillFromFavorite,
  createSkillManually,
  batchDistillFavorites
} from './distiller';

// 检索功能
export {
  retrieveSkillsForAgent,
  getSkillForExecution,
  reportSkillExecution,
  formatSkillForPrompt,
  formatSkillsAsContext,
  injectSkillsToPrompt
} from './retriever';

// P1: 语义搜索
export {
  generateEmbedding,
  cosineSimilarity,
  semanticSearch
} from './embeddings';

// P1: 技能进化
export {
  calculateGeneralityScore,
  shouldPromote,
  shouldDegrade,
  shouldArchive,
  evolveSkills,
  updateQValue,
  getEvolutionReport
} from './evolution';

// P2: 失败分析
export type {
  FailureCategory,
  FailureAnalysis,
  FailurePattern
} from './failure-analyzer';
export {
  analyzeFailure,
  getFailurePatterns,
  triggerSkillImprovement,
  batchAnalyzeFailures
} from './failure-analyzer';

// P2: 回归测试
export type {
  PersistedTestCase,
  TestCase,
  TestResult,
  RegressionReport
} from './regression-tester';
export {
  ensureTestTables,
  createTestCase,
  getTestCases,
  executeTest,
  runRegressionTests,
  compareVersions,
  generateTestCases
} from './regression-tester';

// P2: 技能市场
export type {
  AgentRole,
  SkillPublication,
  SkillReview,
  SkillSubscription,
  MarketplaceStats
} from './marketplace';
export {
  ensureMarketTables,
  publishSkill,
  subscribeSkill,
  recordUsage,
  reviewSkill,
  getMarketplaceStats,
  getRecommendedSkills,
  getAgentSkillLibrary,
  getSkillReviews
} from './marketplace';
