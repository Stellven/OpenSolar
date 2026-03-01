/**
 * Skill Distiller Schema Definitions
 * 基于 SkillRL 论文设计的技能系统数据结构
 */

// 技能层级
export type SkillLayer = 'core' | 'domain' | 'utility';

// 技能范围
export type SkillScope = 'general' | 'task_specific';

// 技能状态
export type SkillStatus = 'pending_review' | 'active' | 'deprecated' | 'archived';

// 技能类型
export type SkillType = 'template' | 'workflow' | 'api_call' | 'anti_pattern';

// 技能定义
export interface Skill {
  skill_id: string;
  name: string;
  description: string;
  skill_type: SkillType;
  layer: SkillLayer;
  scope: SkillScope;
  status: SkillStatus;

  // 执行配置
  llm_prompt_template?: string;
  parameters?: SkillParameter[];
  timeout_ms?: number;
  max_retries?: number;

  // 上下文匹配
  trigger_keywords?: string[];
  applicable_contexts?: string[];
  preconditions?: string[];
  prerequisites?: string[];

  // 统计
  success_count: number;
  failure_count: number;
  q_value: number;
  avg_execution_time_ms?: number;

  // 元数据
  tags?: string[];
  version: string;
  source: string;
  source_ref?: string;
  author_agent?: string;
  parent_id?: string;

  // 时间
  created_at: string;
  updated_at: string;
  last_used_at?: string;

  // 验证
  validated: boolean;
  test_cases?: TestCase[];
  skill_metadata?: Record<string, unknown>;
}

// 技能参数定义
export interface SkillParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  description: string;
  required: boolean;
  default?: unknown;
}

// 嵌入式测试用例（存储在技能 JSON 中）
export interface EmbeddedTestCase {
  input: Record<string, unknown>;
  expected_output: string;
  validation_criteria?: string[];
}

// 向后兼容别名
export type TestCase = EmbeddedTestCase;

// 蒸馏请求
export interface DistillationRequest {
  source_type: 'favorite' | 'conversation' | 'trajectory';
  source_id: string;
  source_content: {
    question?: string;
    answer?: string;
    context?: string;
    tags?: string[];
  };
  target_layer?: SkillLayer;
  author_agent?: string;
}

// 蒸馏结果
export interface DistillationResult {
  success: boolean;
  skill?: Partial<Skill>;
  error?: string;
  confidence: number;
}

// 检索请求
export interface RetrievalRequest {
  query: string;
  context?: {
    task_type?: string;
    tags?: string[];
    layer?: SkillLayer;
  };
  top_k?: number;
}

// 检索结果
export interface RetrievalResult {
  skills: Skill[];
  total: number;
  query_time_ms: number;
}

// 反馈记录
export interface SkillFeedback {
  feedback_id: string;
  skill_id: string;
  skill_version: string;
  session_id?: string;
  task_description?: string;
  user_agent?: string;
  outcome: 'success' | 'failure' | 'partial';
  execution_time_ms?: number;
  user_rating?: number;
  user_comment?: string;
  created_at: string;
}
