#!/usr/bin/env bun
/**
 * Embedding Service - 多后端嵌入服务
 *
 * 支持的后端:
 *   - openai: OpenAI text-embedding-3-small/large
 *   - zhipu: 智谱 AI embedding (GLM)
 *   - voyage: Voyage AI
 *   - huggingface: HuggingFace Inference API (免费)
 *   - ollama: 本地 Ollama 服务
 *   - mock: 伪嵌入 (开发/测试用)
 *
 * Usage:
 *   bun embedding-service.ts embed "your text"
 *   bun embedding-service.ts batch file.txt
 *   bun embedding-service.ts test
 */

import { homedir } from "os";
import { existsSync, readFileSync } from "fs";
import { join } from "path";

// ============================================================
// Types
// ============================================================

export interface EmbeddingConfig {
  backend: "openai" | "zhipu" | "voyage" | "huggingface" | "ollama" | "mock";
  model?: string;
  dimensions?: number;
  apiKey?: string;
  baseUrl?: string;
  batchSize?: number;
}

export interface EmbeddingResult {
  embedding: number[];
  tokens: number;
  model: string;
  backend: string;
}

// ============================================================
// Configuration
// ============================================================

const DEFAULT_CONFIG: EmbeddingConfig = {
  backend: "mock",
  model: "default",
  dimensions: 128,
  batchSize: 10,
};

function loadConfig(): EmbeddingConfig {
  const configPath = join(homedir(), ".solar/cortex/.embedding.yaml");

  // 从环境变量读取
  const envConfig: Partial<EmbeddingConfig> = {};

  if (process.env.OPENAI_API_KEY) {
    envConfig.backend = "openai";
    envConfig.apiKey = process.env.OPENAI_API_KEY;
    envConfig.model = process.env.EMBEDDING_MODEL || "text-embedding-3-small";
  } else if (process.env.ZHIPU_API_KEY) {
    envConfig.backend = "zhipu";
    envConfig.apiKey = process.env.ZHIPU_API_KEY;
    envConfig.model = "embedding-2";
  } else if (process.env.VOYAGE_API_KEY) {
    envConfig.backend = "voyage";
    envConfig.apiKey = process.env.VOYAGE_API_KEY;
    envConfig.model = "voyage-3-lite";
  } else if (process.env.HF_TOKEN) {
    envConfig.backend = "huggingface";
    envConfig.apiKey = process.env.HF_TOKEN;
  }

  // 检查本地服务
  if (!envConfig.backend) {
    // 检查 Ollama
    try {
      const response = fetch("http://localhost:11434/api/tags", {
        method: "GET",
        signal: AbortSignal.timeout(1000),
      });
      // 同步检查不可行，使用 fallback
    } catch (e) {
      // Ollama 不可用
    }
  }

  return { ...DEFAULT_CONFIG, ...envConfig };
}

// ============================================================
// Embedding Backends
// ============================================================

/**
 * OpenAI Embedding API
 */
async function embedWithOpenAI(
  text: string,
  config: EmbeddingConfig
): Promise<EmbeddingResult> {
  const model = config.model || "text-embedding-3-small";

  const response = await fetch("https://api.openai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify({
      input: text,
      model: model,
      dimensions: config.dimensions,
    }),
  });

  if (!response.ok) {
    throw new Error(`OpenAI API error: ${response.status}`);
  }

  const data = (await response.json()) as any;
  return {
    embedding: data.data[0].embedding,
    tokens: data.usage.total_tokens,
    model: model,
    backend: "openai",
  };
}

/**
 * 智谱 AI Embedding API
 */
async function embedWithZhipu(
  text: string,
  config: EmbeddingConfig
): Promise<EmbeddingResult> {
  const response = await fetch(
    "https://open.bigmodel.cn/api/paas/v4/embeddings",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        input: text,
        model: config.model || "embedding-2",
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Zhipu API error: ${response.status}`);
  }

  const data = (await response.json()) as any;
  return {
    embedding: data.data[0].embedding,
    tokens: data.usage.total_tokens,
    model: config.model || "embedding-2",
    backend: "zhipu",
  };
}

/**
 * Voyage AI Embedding API
 */
async function embedWithVoyage(
  text: string,
  config: EmbeddingConfig
): Promise<EmbeddingResult> {
  const model = config.model || "voyage-3-lite";

  const response = await fetch("https://api.voyageai.com/v1/embeddings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`,
    },
    body: JSON.stringify({
      input: text,
      model: model,
    }),
  });

  if (!response.ok) {
    throw new Error(`Voyage API error: ${response.status}`);
  }

  const data = (await response.json()) as any;
  return {
    embedding: data.data[0].embedding,
    tokens: data.usage.total_tokens,
    model: model,
    backend: "voyage",
  };
}

/**
 * HuggingFace Inference API (免费)
 */
async function embedWithHuggingFace(
  text: string,
  config: EmbeddingConfig
): Promise<EmbeddingResult> {
  const model = config.model || "sentence-transformers/all-MiniLM-L6-v2";

  const response = await fetch(
    `https://api-inference.huggingface.co/pipeline/feature-extraction/${model}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({ inputs: text }),
    }
  );

  if (!response.ok) {
    throw new Error(`HuggingFace API error: ${response.status}`);
  }

  const embedding = (await response.json()) as number[];

  return {
    embedding: Array.isArray(embedding[0]) ? embedding[0] : embedding,
    tokens: Math.ceil(text.length / 4), // 估算
    model: model,
    backend: "huggingface",
  };
}

/**
 * Ollama 本地嵌入
 */
async function embedWithOllama(
  text: string,
  config: EmbeddingConfig
): Promise<EmbeddingResult> {
  const model = config.model || "nomic-embed-text";
  const baseUrl = config.baseUrl || "http://localhost:11434";

  const response = await fetch(`${baseUrl}/api/embeddings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: model,
      prompt: text,
    }),
  });

  if (!response.ok) {
    throw new Error(`Ollama API error: ${response.status}`);
  }

  const data = (await response.json()) as any;
  return {
    embedding: data.embedding,
    tokens: Math.ceil(text.length / 4), // 估算
    model: model,
    backend: "ollama",
  };
}

/**
 * Mock 嵌入 (开发/测试用)
 * 使用确定性哈希生成伪嵌入向量
 */
function embedWithMock(text: string, config: EmbeddingConfig): EmbeddingResult {
  const dimensions = config.dimensions || 128;

  // 使用简单哈希生成确定性嵌入
  const hash = simpleHash(text);
  const embedding = new Array(dimensions).fill(0);

  for (let i = 0; i < dimensions; i++) {
    // 使用哈希值和索引生成伪随机但确定性的值
    const seed = hash.charCodeAt(i % hash.length) + i;
    embedding[i] = (Math.sin(seed) * 10000) % 1;
    if (embedding[i] < 0) embedding[i] += 1;
  }

  return {
    embedding,
    tokens: Math.ceil(text.length / 4),
    model: "mock-v1",
    backend: "mock",
  };
}

function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

// ============================================================
// Main API
// ============================================================

/**
 * 生成单个文本的嵌入向量
 */
export async function generateEmbedding(
  text: string,
  config?: Partial<EmbeddingConfig>
): Promise<EmbeddingResult | null> {
  const fullConfig = { ...loadConfig(), ...config };

  try {
    switch (fullConfig.backend) {
      case "openai":
        return await embedWithOpenAI(text, fullConfig);
      case "zhipu":
        return await embedWithZhipu(text, fullConfig);
      case "voyage":
        return await embedWithVoyage(text, fullConfig);
      case "huggingface":
        return await embedWithHuggingFace(text, fullConfig);
      case "ollama":
        return await embedWithOllama(text, fullConfig);
      case "mock":
      default:
        return embedWithMock(text, fullConfig);
    }
  } catch (e) {
    console.error(`Embedding error (${fullConfig.backend}):`, e);
    // Fallback to mock
    return embedWithMock(text, fullConfig);
  }
}

/**
 * 批量生成嵌入向量
 */
export async function generateEmbeddingsBatch(
  texts: string[],
  config?: Partial<EmbeddingConfig>,
  concurrency: number = 5
): Promise<Map<string, EmbeddingResult>> {
  const results = new Map<string, EmbeddingResult>();
  const fullConfig = { ...loadConfig(), ...config };

  for (let i = 0; i < texts.length; i += concurrency) {
    const batch = texts.slice(i, i + concurrency);

    const batchResults = await Promise.all(
      batch.map(async (text, idx) => {
        const result = await generateEmbedding(text, fullConfig);
        return { idx: i + idx, result };
      })
    );

    for (const { idx, result } of batchResults) {
      if (result) {
        results.set(`text-${idx}`, result);
      }
    }

    // 显示进度
    process.stdout.write(
      `\r   📊 嵌入进度: ${Math.min(i + concurrency, texts.length)}/${texts.length}`
    );
  }

  console.log();
  return results;
}

/**
 * 检测可用的嵌入服务
 */
export async function detectAvailableBackends(): Promise<string[]> {
  const available: string[] = [];

  // 检查环境变量
  if (process.env.OPENAI_API_KEY) available.push("openai");
  if (process.env.ZHIPU_API_KEY) available.push("zhipu");
  if (process.env.VOYAGE_API_KEY) available.push("voyage");
  if (process.env.HF_TOKEN) available.push("huggingface");

  // 检查 Ollama
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);

    const response = await fetch("http://localhost:11434/api/tags", {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (response.ok) {
      available.push("ollama");
    }
  } catch (e) {
    // Ollama 不可用
  }

  // Mock 始终可用
  available.push("mock");

  return available;
}

// ============================================================
// CLI
// ============================================================

async function main() {
  const args = Bun.argv.slice(2);
  const command = args[0] || "help";

  switch (command) {
    case "embed": {
      const text = args[1];
      if (!text) {
        console.error("Usage: bun embedding-service.ts embed <text>");
        process.exit(1);
      }

      const result = await generateEmbedding(text);
      if (result) {
        console.log(`\n✓ Backend: ${result.backend}`);
        console.log(`✓ Model: ${result.model}`);
        console.log(`✓ Dimensions: ${result.embedding.length}`);
        console.log(`✓ Tokens: ${result.tokens}`);
        console.log(`✓ Preview: [${result.embedding.slice(0, 5).map(n => n.toFixed(4)).join(", ")}, ...]`);
      }
      break;
    }

    case "test": {
      console.log("\n🔍 检测可用嵌入服务...\n");
      const backends = await detectAvailableBackends();

      console.log("可用后端:");
      for (const backend of backends) {
        const icon = backend === "mock" ? "⚠️" : "✓";
        console.log(`  ${icon} ${backend}`);
      }

      if (!backends.includes("mock") || backends.length === 1) {
        console.log("\n💡 提示: 设置以下环境变量启用真实嵌入:");
        console.log("   - OPENAI_API_KEY");
        console.log("   - ZHIPU_API_KEY");
        console.log("   - VOYAGE_API_KEY");
        console.log("   - HF_TOKEN");
        console.log("   或安装 Ollama: ollama pull nomic-embed-text");
      }

      // 测试嵌入
      console.log("\n🧪 测试嵌入...");
      const result = await generateEmbedding("Hello, world!");
      if (result) {
        console.log(`✓ 生成成功: ${result.embedding.length} 维`);
      }
      break;
    }

    case "status": {
      const config = loadConfig();
      console.log("\n📊 当前配置\n");
      console.log(`  Backend: ${config.backend}`);
      console.log(`  Model: ${config.model || "default"}`);
      console.log(`  Dimensions: ${config.dimensions}`);
      console.log(`  API Key: ${config.apiKey ? "已设置" : "未设置"}`);
      break;
    }

    default:
      console.log(`
Usage:
  bun embedding-service.ts embed <text>   # 生成嵌入向量
  bun embedding-service.ts test           # 测试可用服务
  bun embedding-service.ts status         # 查看当前配置

环境变量:
  OPENAI_API_KEY     - OpenAI embedding API
  ZHIPU_API_KEY      - 智谱 AI embedding
  VOYAGE_API_KEY     - Voyage AI embedding
  HF_TOKEN           - HuggingFace Inference API
  EMBEDDING_MODEL    - 指定模型名称
      `);
  }
}

// 只在直接执行时运行 main()
if (import.meta.main) {
  main();
}
