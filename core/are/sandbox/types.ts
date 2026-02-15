/**
 * ARE Sandbox Types
 *
 * Type definitions for sandboxed code execution
 */

// ============================================
// Sandbox Configuration
// ============================================

export interface SandboxConfig {
  type: 'docker' | 'wasm' | 'process' | 'e2b';
  image?: string;           // Docker image
  memory_mb?: number;       // Memory limit
  cpu_limit?: number;       // CPU cores limit
  timeout_ms?: number;      // Execution timeout
  network?: boolean;        // Network access
  filesystem?: {
    readonly_paths?: string[];   // Mounted read-only
    writable_paths?: string[];   // Mounted read-write
    temp_dir?: boolean;          // Create temp dir
  };
  env?: Record<string, string>;  // Environment variables
}

// ============================================
// Execution Request
// ============================================

export interface CodeExecutionRequest {
  code: string;
  language: 'python' | 'javascript' | 'typescript' | 'bash' | 'rust' | 'go';
  stdin?: string;
  args?: string[];
  files?: Record<string, string>;  // filename -> content
  config?: Partial<SandboxConfig>;
}

// ============================================
// Execution Result
// ============================================

export interface CodeExecutionResult {
  status: 'success' | 'error' | 'timeout' | 'oom';
  exit_code: number;
  stdout: string;
  stderr: string;
  files?: Record<string, string>;  // Output files
  metrics: {
    duration_ms: number;
    memory_peak_mb?: number;
    cpu_time_ms?: number;
  };
}

// ============================================
// Sandbox Interface
// ============================================

export interface Sandbox {
  name: string;
  type: SandboxConfig['type'];

  /**
   * Initialize sandbox
   */
  init(): Promise<void>;

  /**
   * Execute code in sandbox
   */
  execute(request: CodeExecutionRequest): Promise<CodeExecutionResult>;

  /**
   * Check if sandbox is available
   */
  isAvailable(): Promise<boolean>;

  /**
   * Cleanup sandbox resources
   */
  cleanup(): Promise<void>;
}

// ============================================
// Default Configurations
// ============================================

export const DEFAULT_SANDBOX_CONFIG: SandboxConfig = {
  type: 'docker',
  image: 'python:3.11-slim',
  memory_mb: 256,
  cpu_limit: 0.5,
  timeout_ms: 30000,
  network: false,
  filesystem: {
    temp_dir: true,
  },
};

export const LANGUAGE_IMAGES: Record<string, string> = {
  python: 'python:3.11-slim',
  javascript: 'node:20-slim',
  typescript: 'oven/bun:1',
  bash: 'alpine:latest',
  rust: 'rust:slim',
  go: 'golang:1.21-alpine',
};

export const LANGUAGE_COMMANDS: Record<string, string[]> = {
  python: ['python', '-c'],
  javascript: ['node', '-e'],
  typescript: ['bun', 'run'],
  bash: ['sh', '-c'],
  rust: ['rustc', '--edition=2021', '-o', '/tmp/out', '-', '&&', '/tmp/out'],
  go: ['go', 'run', '-'],
};
