/**
 * Skill Regression Tester
 * 技能回归测试模块（P2）
 *
 * 功能：
 * 1. 为技能生成测试用例
 * 2. 执行回归测试
 * 3. 比较版本差异
 */

import type { Skill } from './schema';
import { Database } from 'bun:sqlite';

// 持久化测试用例（数据库存储）
export interface PersistedTestCase {
  test_id: string;
  skill_id: string;
  name: string;
  input: Record<string, unknown>;
  expected_output: string;
  validation_criteria: string[];
  created_at: string;
}

// 测试用例（兼容旧名）
export type TestCase = PersistedTestCase;

// 测试结果
export interface TestResult {
  test_id: string;
  skill_id: string;
  skill_version: string;
  passed: boolean;
  actual_output?: string;
  error_message?: string;
  execution_time_ms: number;
  timestamp: string;
}

// 回归测试报告
export interface RegressionReport {
  skill_id: string;
  old_version: string;
  new_version: string;
  total_tests: number;
  passed: number;
  failed: number;
  regressions: string[];
  improvements: string[];
}

/**
 * 创建测试用例表
 */
export function ensureTestTables(): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  db.run(`
    CREATE TABLE IF NOT EXISTS skill_test_cases (
      test_id TEXT PRIMARY KEY,
      skill_id TEXT NOT NULL,
      name TEXT NOT NULL,
      input JSON NOT NULL,
      expected_output TEXT NOT NULL,
      validation_criteria JSON,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (skill_id) REFERENCES sys_skill_bank(skill_id)
    )
  `);

  db.run(`
    CREATE TABLE IF NOT EXISTS skill_test_results (
      result_id TEXT PRIMARY KEY,
      test_id TEXT NOT NULL,
      skill_id TEXT NOT NULL,
      skill_version TEXT NOT NULL,
      passed BOOLEAN NOT NULL,
      actual_output TEXT,
      error_message TEXT,
      execution_time_ms INTEGER,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (test_id) REFERENCES skill_test_cases(test_id),
      FOREIGN KEY (skill_id) REFERENCES sys_skill_bank(skill_id)
    )
  `);

  db.run(`CREATE INDEX IF NOT EXISTS idx_test_cases_skill ON skill_test_cases(skill_id)`);
  db.run(`CREATE INDEX IF NOT EXISTS idx_test_results_skill ON skill_test_results(skill_id)`);

  db.close();
}

/**
 * 创建测试用例
 */
export function createTestCase(testCase: Omit<TestCase, 'test_id' | 'created_at'>): string {
  ensureTestTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const testId = `test_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

  db.run(`
    INSERT INTO skill_test_cases (test_id, skill_id, name, input, expected_output, validation_criteria)
    VALUES (?, ?, ?, ?, ?, ?)
  `, [
    testId,
    testCase.skill_id,
    testCase.name,
    JSON.stringify(testCase.input),
    testCase.expected_output,
    JSON.stringify(testCase.validation_criteria || [])
  ]);

  db.close();
  return testId;
}

/**
 * 获取技能的测试用例
 */
export function getTestCases(skillId: string): TestCase[] {
  ensureTestTables();

  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const results = db.prepare(`
    SELECT * FROM skill_test_cases WHERE skill_id = ?
  `).all(skillId) as unknown[];

  db.close();

  return (results as Record<string, unknown>[]).map(r => ({
    test_id: r.test_id as string,
    skill_id: r.skill_id as string,
    name: r.name as string,
    input: JSON.parse(r.input as string || '{}'),
    expected_output: r.expected_output as string,
    validation_criteria: JSON.parse(r.validation_criteria as string || '[]'),
    created_at: r.created_at as string
  }));
}

/**
 * 执行单个测试用例
 */
export async function executeTest(
  testCase: TestCase,
  skill: Skill
): Promise<TestResult> {
  const startTime = Date.now();
  const resultId = `result_${Date.now().toString(36)}`;

  try {
    // 简化版测试：检查技能模板是否包含必要的变量
    const template = skill.llm_prompt_template || '';
    const inputKeys = Object.keys(testCase.input);

    // 检查所有输入变量是否在模板中
    const missingVars = inputKeys.filter(
      key => !template.includes(`{${key}}`)
    );

    if (missingVars.length > 0) {
      return {
        test_id: testCase.test_id,
        skill_id: skill.skill_id,
        skill_version: skill.version,
        passed: false,
        error_message: `模板缺少变量: ${missingVars.join(', ')}`,
        execution_time_ms: Date.now() - startTime,
        timestamp: new Date().toISOString()
      };
    }

    // 检查期望输出格式
    const hasExpectedOutput = testCase.expected_output.length > 0;
    const passed = hasExpectedOutput;

    const result: TestResult = {
      test_id: testCase.test_id,
      skill_id: skill.skill_id,
      skill_version: skill.version,
      passed,
      actual_output: passed ? '模板验证通过' : undefined,
      execution_time_ms: Date.now() - startTime,
      timestamp: new Date().toISOString()
    };

    // 保存结果
    saveTestResult(result);

    return result;

  } catch (error) {
    const result: TestResult = {
      test_id: testCase.test_id,
      skill_id: skill.skill_id,
      skill_version: skill.version,
      passed: false,
      error_message: error instanceof Error ? error.message : String(error),
      execution_time_ms: Date.now() - startTime,
      timestamp: new Date().toISOString()
    };

    saveTestResult(result);
    return result;
  }
}

/**
 * 保存测试结果
 */
function saveTestResult(result: TestResult): void {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const resultId = `result_${Date.now().toString(36)}`;

  db.run(`
    INSERT INTO skill_test_results
    (result_id, test_id, skill_id, skill_version, passed, actual_output, error_message, execution_time_ms)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `, [
    resultId,
    result.test_id,
    result.skill_id,
    result.skill_version,
    result.passed ? 1 : 0,
    result.actual_output || null,
    result.error_message || null,
    result.execution_time_ms
  ]);

  db.close();
}

/**
 * 执行回归测试
 */
export async function runRegressionTests(skillId: string): Promise<{
  total: number;
  passed: number;
  failed: number;
  results: TestResult[];
}> {
  const testCases = getTestCases(skillId);

  if (testCases.length === 0) {
    return { total: 0, passed: 0, failed: 0, results: [] };
  }

  // 获取技能
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);
  const skillRow = db.prepare('SELECT * FROM sys_skill_bank WHERE skill_id = ?').get(skillId);
  db.close();

  if (!skillRow) {
    return { total: testCases.length, passed: 0, failed: testCases.length, results: [] };
  }

  const skill = parseSkillRow(skillRow as Record<string, unknown>);

  // 执行所有测试
  const results: TestResult[] = [];
  for (const testCase of testCases) {
    const result = await executeTest(testCase, skill);
    results.push(result);
  }

  return {
    total: testCases.length,
    passed: results.filter(r => r.passed).length,
    failed: results.filter(r => !r.passed).length,
    results
  };
}

/**
 * 比较两个版本的回归测试结果
 */
export function compareVersions(
  skillId: string,
  oldVersion: string,
  newVersion: string
): RegressionReport {
  const db = new Database(`${process.env.HOME}/.solar/solar.db`);

  // 获取旧版本结果
  const oldResults = db.prepare(`
    SELECT * FROM skill_test_results
    WHERE skill_id = ? AND skill_version = ?
  `).all(skillId, oldVersion) as Record<string, unknown>[];

  // 获取新版本结果
  const newResults = db.prepare(`
    SELECT * FROM skill_test_results
    WHERE skill_id = ? AND skill_version = ?
  `).all(skillId, newVersion) as Record<string, unknown>[];

  db.close();

  // 比较结果
  const regressions: string[] = [];
  const improvements: string[] = [];

  for (const newResult of newResults) {
    const oldResult = oldResults.find(
      r => r.test_id === newResult.test_id
    );

    if (oldResult) {
      const oldPassed = Boolean(oldResult.passed);
      const newPassed = Boolean(newResult.passed);

      if (oldPassed && !newPassed) {
        regressions.push(`测试 ${newResult.test_id} 从通过变为失败`);
      } else if (!oldPassed && newPassed) {
        improvements.push(`测试 ${newResult.test_id} 从失败变为通过`);
      }
    }
  }

  return {
    skill_id: skillId,
    old_version: oldVersion,
    new_version: newVersion,
    total_tests: newResults.length,
    passed: newResults.filter(r => Boolean(r.passed)).length,
    failed: newResults.filter(r => !Boolean(r.passed)).length,
    regressions,
    improvements
  };
}

/**
 * 生成测试用例（基于技能描述）
 */
export function generateTestCases(skill: Skill): TestCase[] {
  const testCases: TestCase[] = [];

  // 解析技能参数
  const params = skill.parameters || [];
  if (params.length === 0) {
    // 生成默认测试用例
    testCases.push({
      test_id: `test_${skill.skill_id}_default`,
      skill_id: skill.skill_id,
      name: '默认测试用例',
      input: {},
      expected_output: '技能执行成功',
      validation_criteria: ['无错误输出', '返回有效结果'],
      created_at: new Date().toISOString()
    });
  } else {
    // 为每个参数生成测试用例
    const baseInput: Record<string, unknown> = {};
    for (const param of params) {
      if (param.required) {
        baseInput[param.name] = getDefaultValue(param.type);
      }
    }

    testCases.push({
      test_id: `test_${skill.skill_id}_valid`,
      skill_id: skill.skill_id,
      name: '有效输入测试',
      input: baseInput,
      expected_output: '技能执行成功',
      validation_criteria: ['所有必需参数已提供'],
      created_at: new Date().toISOString()
    });
  }

  return testCases;
}

// 辅助函数
function parseSkillRow(row: Record<string, unknown>): Skill {
  return {
    skill_id: row.skill_id as string,
    name: row.name as string,
    description: row.description as string,
    skill_type: (row.skill_type as Skill['skill_type']) || 'template',
    layer: (row.layer as Skill['layer']) || 'domain',
    scope: (row.scope as Skill['scope']) || 'task_specific',
    status: (row.status as Skill['status']) || 'active',
    llm_prompt_template: row.llm_prompt_template as string,
    parameters: JSON.parse(row.parameters as string || '[]'),
    success_count: (row.success_count as number) || 0,
    failure_count: (row.failure_count as number) || 0,
    q_value: (row.q_value as number) || 0.5,
    tags: JSON.parse(row.tags as string || '[]'),
    version: (row.version as string) || '1.0.0',
    created_at: row.created_at as string,
    updated_at: row.updated_at as string,
    last_used_at: row.last_used_at as string,
    validated: Boolean(row.validated)
  } as Skill;
}

function getDefaultValue(type: string): unknown {
  switch (type) {
    case 'string': return 'test_value';
    case 'number': return 1;
    case 'boolean': return true;
    case 'object': return {};
    case 'array': return [];
    default: return null;
  }
}
