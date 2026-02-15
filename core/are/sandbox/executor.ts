/**
 * ARE Code Executor
 *
 * High-level interface for sandboxed code execution
 */

import {
  Sandbox,
  SandboxConfig,
  CodeExecutionRequest,
  CodeExecutionResult,
  LANGUAGE_IMAGES,
} from './types';
import { DockerSandbox } from './docker';
import { Database } from 'bun:sqlite';

const DB_PATH = `${process.env.HOME}/.solar/solar.db`;

// ============================================
// Process Sandbox (fallback, less secure)
// ============================================

class ProcessSandbox implements Sandbox {
  name = 'process';
  type: SandboxConfig['type'] = 'process';

  async init(): Promise<void> {}

  async isAvailable(): Promise<boolean> {
    return true; // Always available
  }

  async execute(request: CodeExecutionRequest): Promise<CodeExecutionResult> {
    const startTime = Date.now();
    const config = request.config || {};
    const timeoutMs = config.timeout_ms || 30000;

    // Create temp file
    const tempFile = `/tmp/are_code_${Date.now()}.${this.getExtension(request.language)}`;
    await Bun.write(tempFile, request.code);

    try {
      const cmd = this.getCommand(request.language, tempFile, request.args);
      const proc = Bun.spawn(cmd, {
        stdout: 'pipe',
        stderr: 'pipe',
        stdin: request.stdin ? new Blob([request.stdin]).stream() : undefined,
        env: { ...process.env, ...config.env },
      });

      // Handle timeout
      const timeoutPromise = new Promise<'timeout'>((resolve) =>
        setTimeout(() => resolve('timeout'), timeoutMs)
      );

      const exitPromise = proc.exited;
      const raceResult = await Promise.race([exitPromise, timeoutPromise]);

      if (raceResult === 'timeout') {
        proc.kill();
        return {
          status: 'timeout',
          exit_code: -1,
          stdout: '',
          stderr: `Execution timed out after ${timeoutMs}ms`,
          metrics: { duration_ms: timeoutMs },
        };
      }

      const exitCode = raceResult as number;
      const stdout = await new Response(proc.stdout).text();
      const stderr = await new Response(proc.stderr).text();

      return {
        status: exitCode === 0 ? 'success' : 'error',
        exit_code: exitCode,
        stdout,
        stderr,
        metrics: { duration_ms: Date.now() - startTime },
      };
    } finally {
      // Cleanup temp file
      try {
        await Bun.spawn(['rm', '-f', tempFile]).exited;
      } catch {}
    }
  }

  async cleanup(): Promise<void> {}

  private getExtension(language: string): string {
    const extensions: Record<string, string> = {
      python: 'py',
      javascript: 'js',
      typescript: 'ts',
      bash: 'sh',
      rust: 'rs',
      go: 'go',
    };
    return extensions[language] || 'txt';
  }

  private getCommand(language: string, file: string, args?: string[]): string[] {
    const cmds: Record<string, string[]> = {
      python: ['python3', file],
      javascript: ['node', file],
      typescript: ['bun', 'run', file],
      bash: ['bash', file],
      rust: ['rustc', file, '-o', '/tmp/out', '&&', '/tmp/out'],
      go: ['go', 'run', file],
    };
    const cmd = cmds[language] || ['sh', '-c', `cat ${file}`];
    return args ? [...cmd, ...args] : cmd;
  }
}

// ============================================
// Code Executor
// ============================================

export class CodeExecutor {
  private db: Database;
  private dockerSandbox: DockerSandbox;
  private processSandbox: ProcessSandbox;
  private preferDocker: boolean = true;

  constructor() {
    this.db = new Database(DB_PATH);
    this.dockerSandbox = new DockerSandbox();
    this.processSandbox = new ProcessSandbox();
  }

  /**
   * Execute code with automatic sandbox selection
   */
  async execute(request: CodeExecutionRequest): Promise<CodeExecutionResult> {
    const startTime = Date.now();

    // Try Docker first if preferred and available
    if (this.preferDocker) {
      const dockerAvailable = await this.dockerSandbox.isAvailable();
      if (dockerAvailable) {
        try {
          const result = await this.dockerSandbox.execute(request);
          this.logExecution(request, result, 'docker');
          return result;
        } catch (error: any) {
          // Fallback to process sandbox
          console.error('Docker execution failed, falling back to process:', error.message);
        }
      }
    }

    // Fallback to process sandbox
    const result = await this.processSandbox.execute(request);
    this.logExecution(request, result, 'process');
    return result;
  }

  /**
   * Execute with specific sandbox type
   */
  async executeWith(
    sandbox: 'docker' | 'process',
    request: CodeExecutionRequest
  ): Promise<CodeExecutionResult> {
    const s = sandbox === 'docker' ? this.dockerSandbox : this.processSandbox;
    const result = await s.execute(request);
    this.logExecution(request, result, sandbox);
    return result;
  }

  /**
   * Check Docker availability
   */
  async isDockerAvailable(): Promise<boolean> {
    return this.dockerSandbox.isAvailable();
  }

  /**
   * Set sandbox preference
   */
  setPreferDocker(prefer: boolean): void {
    this.preferDocker = prefer;
  }

  /**
   * Execute Python code
   */
  async python(code: string, options?: Partial<CodeExecutionRequest>): Promise<CodeExecutionResult> {
    return this.execute({
      code,
      language: 'python',
      ...options,
    });
  }

  /**
   * Execute JavaScript code
   */
  async javascript(code: string, options?: Partial<CodeExecutionRequest>): Promise<CodeExecutionResult> {
    return this.execute({
      code,
      language: 'javascript',
      ...options,
    });
  }

  /**
   * Execute TypeScript code
   */
  async typescript(code: string, options?: Partial<CodeExecutionRequest>): Promise<CodeExecutionResult> {
    return this.execute({
      code,
      language: 'typescript',
      ...options,
    });
  }

  /**
   * Execute Bash code
   */
  async bash(code: string, options?: Partial<CodeExecutionRequest>): Promise<CodeExecutionResult> {
    return this.execute({
      code,
      language: 'bash',
      ...options,
    });
  }

  /**
   * Log execution to telemetry
   */
  private logExecution(
    request: CodeExecutionRequest,
    result: CodeExecutionResult,
    sandbox: string
  ): void {
    try {
      this.db.run(
        `INSERT INTO tel_operations (
           category, operation, duration_ms, success,
           input_bytes, output_bytes, metadata
         ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          'sandbox',
          `${sandbox}:${request.language}`,
          result.metrics.duration_ms,
          result.status === 'success',
          request.code.length,
          result.stdout.length + result.stderr.length,
          JSON.stringify({
            exit_code: result.exit_code,
            status: result.status,
          }),
        ]
      );
    } catch {
      // Ignore telemetry errors
    }
  }

  /**
   * Cleanup all sandboxes
   */
  async cleanup(): Promise<void> {
    await this.dockerSandbox.cleanup();
    await this.processSandbox.cleanup();
  }
}

// ============================================
// Export
// ============================================

export const codeExecutor = new CodeExecutor();
