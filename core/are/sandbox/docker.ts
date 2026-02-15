/**
 * ARE Docker Sandbox
 *
 * Execute code in isolated Docker containers
 */

import {
  Sandbox,
  SandboxConfig,
  CodeExecutionRequest,
  CodeExecutionResult,
  DEFAULT_SANDBOX_CONFIG,
  LANGUAGE_IMAGES,
  LANGUAGE_COMMANDS,
} from './types';

// ============================================
// Docker Sandbox
// ============================================

export class DockerSandbox implements Sandbox {
  name = 'docker';
  type: SandboxConfig['type'] = 'docker';
  private config: SandboxConfig;

  constructor(config?: Partial<SandboxConfig>) {
    this.config = { ...DEFAULT_SANDBOX_CONFIG, ...config };
  }

  async init(): Promise<void> {
    // Check if Docker is available
    if (!(await this.isAvailable())) {
      throw new Error('Docker is not available');
    }
  }

  async isAvailable(): Promise<boolean> {
    try {
      const proc = Bun.spawn(['docker', 'version'], {
        stdout: 'pipe',
        stderr: 'pipe',
      });
      const code = await proc.exited;
      return code === 0;
    } catch {
      return false;
    }
  }

  async execute(request: CodeExecutionRequest): Promise<CodeExecutionResult> {
    const startTime = Date.now();
    const config = { ...this.config, ...request.config };
    const image = config.image || LANGUAGE_IMAGES[request.language] || 'alpine:latest';

    // Create temp directory for code and files
    const tempDir = `/tmp/are_sandbox_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    await Bun.spawn(['mkdir', '-p', tempDir]).exited;

    try {
      // Write code to file
      const codeFile = `${tempDir}/code.${this.getExtension(request.language)}`;
      await Bun.write(codeFile, request.code);

      // Write additional files
      if (request.files) {
        for (const [filename, content] of Object.entries(request.files)) {
          await Bun.write(`${tempDir}/${filename}`, content);
        }
      }

      // Build docker command
      const dockerArgs = this.buildDockerArgs(config, tempDir, image, request);

      // Execute
      const proc = Bun.spawn(['docker', ...dockerArgs], {
        stdout: 'pipe',
        stderr: 'pipe',
        stdin: request.stdin ? new Blob([request.stdin]).stream() : undefined,
      });

      // Handle timeout
      const timeoutMs = config.timeout_ms || 30000;
      const timeoutPromise = new Promise<'timeout'>((resolve) =>
        setTimeout(() => resolve('timeout'), timeoutMs)
      );

      const exitPromise = proc.exited;
      const raceResult = await Promise.race([exitPromise, timeoutPromise]);

      if (raceResult === 'timeout') {
        // Kill container
        proc.kill();
        return {
          status: 'timeout',
          exit_code: -1,
          stdout: '',
          stderr: `Execution timed out after ${timeoutMs}ms`,
          metrics: {
            duration_ms: timeoutMs,
          },
        };
      }

      const exitCode = raceResult as number;
      const stdout = await new Response(proc.stdout).text();
      const stderr = await new Response(proc.stderr).text();

      // Check for OOM
      if (stderr.includes('OOMKilled') || stderr.includes('out of memory')) {
        return {
          status: 'oom',
          exit_code: exitCode,
          stdout,
          stderr,
          metrics: {
            duration_ms: Date.now() - startTime,
          },
        };
      }

      // Collect output files if any
      const outputFiles: Record<string, string> = {};
      if (config.filesystem?.writable_paths) {
        // Read output files from temp dir
        const outputDir = `${tempDir}/output`;
        try {
          const files = await this.readDir(outputDir);
          for (const file of files) {
            outputFiles[file] = await Bun.file(`${outputDir}/${file}`).text();
          }
        } catch {
          // No output files
        }
      }

      return {
        status: exitCode === 0 ? 'success' : 'error',
        exit_code: exitCode,
        stdout,
        stderr,
        files: Object.keys(outputFiles).length > 0 ? outputFiles : undefined,
        metrics: {
          duration_ms: Date.now() - startTime,
        },
      };
    } finally {
      // Cleanup temp directory
      await Bun.spawn(['rm', '-rf', tempDir]).exited;
    }
  }

  async cleanup(): Promise<void> {
    // Cleanup dangling containers
    try {
      await Bun.spawn([
        'docker', 'container', 'prune', '-f',
        '--filter', 'label=are_sandbox=true',
      ]).exited;
    } catch {
      // Ignore cleanup errors
    }
  }

  /**
   * Build docker run arguments
   */
  private buildDockerArgs(
    config: SandboxConfig,
    tempDir: string,
    image: string,
    request: CodeExecutionRequest
  ): string[] {
    const args: string[] = ['run', '--rm'];

    // Labels for cleanup
    args.push('--label', 'are_sandbox=true');

    // Memory limit
    if (config.memory_mb) {
      args.push('--memory', `${config.memory_mb}m`);
      args.push('--memory-swap', `${config.memory_mb}m`); // No swap
    }

    // CPU limit
    if (config.cpu_limit) {
      args.push('--cpus', `${config.cpu_limit}`);
    }

    // Network
    if (!config.network) {
      args.push('--network', 'none');
    }

    // Mount temp directory
    args.push('-v', `${tempDir}:/workspace:ro`);

    // Create output directory
    args.push('-v', `${tempDir}/output:/output:rw`);

    // Working directory
    args.push('-w', '/workspace');

    // Environment variables
    if (config.env) {
      for (const [key, value] of Object.entries(config.env)) {
        args.push('-e', `${key}=${value}`);
      }
    }

    // Image
    args.push(image);

    // Command based on language
    const langCmd = LANGUAGE_COMMANDS[request.language];
    if (langCmd) {
      if (request.language === 'typescript' || request.language === 'javascript') {
        // For JS/TS, run the file directly
        args.push(...langCmd.slice(0, -1), `/workspace/code.${this.getExtension(request.language)}`);
      } else if (request.language === 'python') {
        args.push('python', `/workspace/code.py`);
      } else if (request.language === 'bash') {
        args.push('sh', `/workspace/code.sh`);
      } else {
        args.push(...langCmd, request.code);
      }
    } else {
      args.push('sh', '-c', request.code);
    }

    // Additional args
    if (request.args) {
      args.push(...request.args);
    }

    return args;
  }

  /**
   * Get file extension for language
   */
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

  /**
   * Read directory contents
   */
  private async readDir(dir: string): Promise<string[]> {
    const proc = Bun.spawn(['ls', dir], {
      stdout: 'pipe',
      stderr: 'pipe',
    });
    const code = await proc.exited;
    if (code !== 0) return [];
    const stdout = await new Response(proc.stdout).text();
    return stdout.trim().split('\n').filter(f => f);
  }
}

// ============================================
// Export
// ============================================

export const dockerSandbox = new DockerSandbox();
