/**
 * Agentic Runtime Engine (ARE) - Core Types
 *
 * Plan IR + Execution Types for efficient agent task execution
 */

// ============================================
// Plan IR (Intermediate Representation)
// ============================================

export interface PlanIR {
  meta: PlanMeta;
  vars: Record<string, PlanVariable>;
  tasks: PlanTask[];
  constraints: PlanConstraints;
}

export interface PlanMeta {
  plan_id: string;
  version: string;
  created_at: string;
  intent_hash: string;      // For plan cache matching
  intent_text?: string;     // Original user intent
  estimated_cost?: number;
  estimated_latency_ms?: number;
}

export interface PlanVariable {
  type: 'input' | 'computed' | 'constant';
  value?: any;
  source_task?: string;     // For computed vars
  schema?: string;          // Type hint
}

export interface PlanTask {
  task_id: string;
  name: string;
  description?: string;

  // Action definition
  action: TaskAction;

  // Dependencies
  depends_on: string[];

  // Output
  output: TaskOutput;

  // Task-level constraints
  constraints?: TaskConstraints;
}

export interface TaskAction {
  type: 'primitive' | 'script' | 'mcp' | 'agent' | 'code' | 'shortcut';
  target: string;           // primitive name / script_id / mcp tool / agent name
  params: Record<string, any>;
}

export interface TaskOutput {
  var_name: string;
  type?: string;
}

export interface TaskConstraints {
  timeout_ms?: number;
  retry?: RetryPolicy;
  cache_ttl_s?: number;
  idempotent?: boolean;
  sandbox?: 'bun' | 'wasm' | 'openclaw' | 'docker';
}

export interface RetryPolicy {
  max_attempts: number;
  backoff_ms: number;
  backoff_multiplier: number;
}

export interface PlanConstraints {
  timeout_ms: number;
  max_parallel: number;
  retry_policy: RetryPolicy;
  rollback_on_failure: boolean;
}

// ============================================
// Execution Types
// ============================================

export interface ExecutionContext {
  plan: PlanIR;
  state: ExecutionState;
  capabilities: CapabilitySet;
  telemetry: TelemetryCollector;
}

export interface ExecutionState {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  completed: Set<string>;
  failed: Set<string>;
  running: Set<string>;
  vars: Record<string, any>;
  checkpoints: Checkpoint[];
  start_time?: number;
  end_time?: number;
}

export interface Checkpoint {
  checkpoint_id: string;
  task_id: string;
  state_snapshot: Record<string, any>;
  created_at: Date;
}

export interface CapabilitySet {
  fs: { read: string[]; write: string[] };
  net: { allowed_hosts: string[]; max_requests: number };
  exec: { timeout_ms: number; memory_mb: number };
  db: { read: boolean; write: boolean };
}

// ============================================
// Task Execution Result
// ============================================

export interface TaskResult {
  task_id: string;
  status: 'success' | 'failed' | 'skipped' | 'cached';
  output?: any;
  error?: TaskError;
  metrics: TaskMetrics;
  cached: boolean;
  cache_key?: string;
}

export interface TaskError {
  code: string;
  message: string;
  retryable: boolean;
  stack?: string;
}

export interface TaskMetrics {
  start_time: number;
  end_time: number;
  duration_ms: number;
  input_bytes: number;
  output_bytes: number;
  tier: 'cache' | 'primitive' | 'script' | 'sandbox';
}

// ============================================
// Plan Execution Result
// ============================================

export interface PlanResult {
  plan_id: string;
  status: 'success' | 'partial' | 'failed';
  outputs: Record<string, any>;
  task_results: TaskResult[];
  metrics: PlanMetrics;
}

export interface PlanMetrics {
  total_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  cached_tasks: number;
  total_duration_ms: number;
  parallel_efficiency: number;  // actual_time / sequential_time
}

// ============================================
// Telemetry Types
// ============================================

export interface TelemetryCollector {
  record(event: TelemetryEvent): void;
  flush(): Promise<void>;
}

export interface TelemetryEvent {
  event_type: 'task_start' | 'task_end' | 'cache_hit' | 'cache_miss' | 'error' | 'optimization';
  timestamp: number;
  task_id?: string;
  plan_id: string;
  data: Record<string, any>;
}

// ============================================
// Primitive Definitions
// ============================================

export interface PrimitiveDefinition {
  name: string;
  params: Record<string, { type: string; required?: boolean; default?: any }>;
  returns: string;
  capabilities: string[];
  idempotent: boolean;
  cacheable: boolean;
}

export const PRIMITIVES: Record<string, PrimitiveDefinition> = {
  // File System
  'fs.read': {
    name: 'fs.read',
    params: { path: { type: 'string', required: true }, encoding: { type: 'string', default: 'utf-8' } },
    returns: 'string',
    capabilities: ['fs.read'],
    idempotent: true,
    cacheable: true,
  },
  'fs.write': {
    name: 'fs.write',
    params: { path: { type: 'string', required: true }, content: { type: 'string', required: true } },
    returns: 'void',
    capabilities: ['fs.write'],
    idempotent: false,
    cacheable: false,
  },
  'fs.exists': {
    name: 'fs.exists',
    params: { path: { type: 'string', required: true } },
    returns: 'boolean',
    capabilities: ['fs.read'],
    idempotent: true,
    cacheable: true,
  },
  'fs.list': {
    name: 'fs.list',
    params: { path: { type: 'string', required: true }, pattern: { type: 'string' } },
    returns: 'string[]',
    capabilities: ['fs.read'],
    idempotent: true,
    cacheable: true,
  },

  // Database
  'db.query': {
    name: 'db.query',
    params: { sql: { type: 'string', required: true }, params: { type: 'any[]' } },
    returns: 'any[]',
    capabilities: ['db.read'],
    idempotent: true,
    cacheable: true,
  },
  'db.exec': {
    name: 'db.exec',
    params: { sql: { type: 'string', required: true }, params: { type: 'any[]' } },
    returns: 'void',
    capabilities: ['db.write'],
    idempotent: false,
    cacheable: false,
  },

  // Network
  'net.fetch': {
    name: 'net.fetch',
    params: { url: { type: 'string', required: true }, options: { type: 'object' } },
    returns: 'Response',
    capabilities: ['net.http'],
    idempotent: true,  // GET is idempotent
    cacheable: true,
  },

  // JSON
  'json.parse': {
    name: 'json.parse',
    params: { text: { type: 'string', required: true } },
    returns: 'any',
    capabilities: [],
    idempotent: true,
    cacheable: true,
  },
  'json.stringify': {
    name: 'json.stringify',
    params: { value: { type: 'any', required: true }, pretty: { type: 'boolean', default: false } },
    returns: 'string',
    capabilities: [],
    idempotent: true,
    cacheable: true,
  },
  'json.path': {
    name: 'json.path',
    params: { obj: { type: 'any', required: true }, path: { type: 'string', required: true } },
    returns: 'any',
    capabilities: [],
    idempotent: true,
    cacheable: true,
  },

  // Text
  'text.regex': {
    name: 'text.regex',
    params: { text: { type: 'string', required: true }, pattern: { type: 'string', required: true } },
    returns: 'string[]',
    capabilities: [],
    idempotent: true,
    cacheable: true,
  },
  'text.template': {
    name: 'text.template',
    params: { template: { type: 'string', required: true }, vars: { type: 'object', required: true } },
    returns: 'string',
    capabilities: [],
    idempotent: true,
    cacheable: true,
  },

  // System
  'sys.exec': {
    name: 'sys.exec',
    params: { cmd: { type: 'string', required: true }, args: { type: 'string[]' }, cwd: { type: 'string' } },
    returns: '{ stdout: string, stderr: string, code: number }',
    capabilities: ['sys.exec'],
    idempotent: false,
    cacheable: false,
  },
  'sys.env': {
    name: 'sys.env',
    params: { name: { type: 'string', required: true } },
    returns: 'string',
    capabilities: ['sys.env'],
    idempotent: true,
    cacheable: true,
  },

  // LLM
  'llm.complete': {
    name: 'llm.complete',
    params: { prompt: { type: 'string', required: true }, model: { type: 'string' }, max_tokens: { type: 'number' } },
    returns: 'string',
    capabilities: ['llm'],
    idempotent: false,  // LLM outputs vary
    cacheable: false,
  },
  'llm.embed': {
    name: 'llm.embed',
    params: { text: { type: 'string', required: true } },
    returns: 'number[]',
    capabilities: ['llm'],
    idempotent: true,
    cacheable: true,
  },
};

// ============================================
// Cache Types
// ============================================

export interface CacheEntry {
  key: string;
  value: any;
  created_at: number;
  expires_at: number;
  hit_count: number;
  last_hit: number;
  size_bytes: number;
}

export interface PlanCacheEntry {
  plan_id: string;
  intent_hash: string;
  intent_embedding?: number[];
  plan_ir: PlanIR;
  success_count: number;
  fail_count: number;
  avg_latency_ms: number;
  created_at: Date;
  last_used_at: Date;
}

// ============================================
// Optimization Types
// ============================================

export interface OptimizationSuggestion {
  type: 'cache_ttl' | 'parallel_degree' | 'timeout' | 'jit_to_aot' | 'sandbox_selection';
  target: string;
  current_value: any;
  suggested_value: any;
  expected_improvement: number;
  confidence: number;
  evidence: string;
}

export interface HotspotAnalysis {
  task_pattern: string;
  frequency: number;
  avg_latency_ms: number;
  cache_hit_rate: number;
  suggestion: 'promote_to_aot' | 'increase_cache_ttl' | 'parallelize' | 'none';
}
