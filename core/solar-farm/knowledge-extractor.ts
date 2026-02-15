#!/usr/bin/env bun
/**
 * Knowledge Extractor - 知识提取器
 *
 * 从 Solar 各个数据源提取知识，导入到 Cortex 知识库
 *
 * 数据源:
 * - sys_favorites (65条收藏)
 * - rules/*.md (68个铁律)
 * - skills/文档 (78个技能)
 * - web/pages/*.html (项目文档)
 * - Git history (开发历程)
 */

import { Cortex } from '../cortex/index';
import { Database } from 'bun:sqlite';
import { homedir } from 'os';
import { existsSync, readFileSync, readdirSync } from 'fs';
import { join } from 'path';

const DB_PATH = `${homedir()}/.solar/solar.db`;
const CLAUDE_DIR = `${homedir()}/.claude`;

interface KnowledgeEntry {
  source: string;         // 来源 (favorites/rules/skills/projects/git)
  category: string;       // 类别 (architecture/optimization/rule/skill/lesson)
  project?: string;       // 关联项目 (ThunderDuck/ThunderMLX/Solar/...)
  title: string;          // 标题
  content: string;        // 内容
  tags: string[];         // 标签
  credibility: number;    // 可信度 (0.7-0.95)
  metadata?: Record<string, any>; // 额外元数据
}

class KnowledgeExtractor {
  private cortex: Cortex;
  private db: Database;
  private stats = {
    favorites: 0,
    rules: 0,
    skills: 0,
    projects: 0,
    total: 0
  };

  constructor() {
    this.cortex = new Cortex();
    this.db = new Database(DB_PATH);
  }

  /**
   * 执行完整的知识提取流程
   */
  async extract(options: {
    favorites?: boolean;
    rules?: boolean;
    skills?: boolean;
    projects?: boolean;
  } = {}) {
    console.log('🔍 开始提取 Solar 知识库...\n');

    // 默认全部提取
    const opts = {
      favorites: true,
      rules: true,
      skills: true,
      projects: true,
      ...options
    };

    if (opts.favorites) await this.extractFavorites();
    if (opts.rules) await this.extractRules();
    if (opts.skills) await this.extractSkills();
    if (opts.projects) await this.extractProjects();

    this.printStats();
  }

  /**
   * 1. 提取 sys_favorites 收藏
   */
  private async extractFavorites() {
    console.log('\n📚 提取 sys_favorites...');

    const favorites = this.db.query(`
      SELECT favorite_id, title, question, answer, tags, importance, created_at
      FROM sys_favorites
      ORDER BY importance DESC, created_at DESC
    `).all() as any[];

    console.log(`   找到 ${favorites.length} 条收藏`);

    for (const fav of favorites) {
      const entry: KnowledgeEntry = {
        source: 'favorites',
        category: this.categorizeFavorite(fav.title, fav.answer),
        title: fav.title,
        content: `${fav.question}\n\n${fav.answer}`,
        tags: this.parseTags(fav.tags),
        credibility: 0.9, // 收藏内容都是高质量的
        metadata: {
          favorite_id: fav.favorite_id,
          importance: fav.importance,
          created_at: fav.created_at
        }
      };

      await this.importToCortex(entry);
      this.stats.favorites++;
    }

    console.log(`   ✅ 导入 ${this.stats.favorites} 条收藏知识`);
  }

  /**
   * 2. 提取 rules/ 铁律规则
   */
  private async extractRules() {
    console.log('\n📜 提取 rules/ 铁律...');

    const rulesDir = join(CLAUDE_DIR, 'rules');
    if (!existsSync(rulesDir)) {
      console.log('   ⚠️  rules/ 目录不存在');
      return;
    }

    const files = readdirSync(rulesDir).filter(f => f.endsWith('.md'));
    console.log(`   找到 ${files.length} 个规则文件`);

    for (const file of files) {
      const filePath = join(rulesDir, file);
      const content = readFileSync(filePath, 'utf-8');

      // 提取标题（第一个 # 标题）
      const titleMatch = content.match(/^#\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1] : file.replace('.md', '');

      const entry: KnowledgeEntry = {
        source: 'rules',
        category: 'rule',
        title: `Solar 铁律: ${title}`,
        content: content,
        tags: this.extractTagsFromMarkdown(content),
        credibility: 0.95, // 铁律是核心规范
        metadata: {
          file: file,
          path: filePath
        }
      };

      await this.importToCortex(entry);
      this.stats.rules++;
    }

    console.log(`   ✅ 导入 ${this.stats.rules} 条铁律知识`);
  }

  /**
   * 3. 提取 skills/ 技能经验
   */
  private async extractSkills() {
    console.log('\n🛠️  提取 skills/ 技能...');

    const skillsDir = join(CLAUDE_DIR, 'skills');
    if (!existsSync(skillsDir)) {
      console.log('   ⚠️  skills/ 目录不存在');
      return;
    }

    const skillDirs = readdirSync(skillsDir, { withFileTypes: true })
      .filter(d => d.isDirectory())
      .map(d => d.name);

    console.log(`   找到 ${skillDirs.length} 个技能目录`);

    for (const skillName of skillDirs) {
      const skillPath = join(skillsDir, skillName);
      const skillMd = join(skillPath, 'SKILL.md');

      if (!existsSync(skillMd)) continue;

      const content = readFileSync(skillMd, 'utf-8');
      const titleMatch = content.match(/^#\s+(.+)$/m);
      const title = titleMatch ? titleMatch[1] : skillName;

      const entry: KnowledgeEntry = {
        source: 'skills',
        category: 'skill',
        title: `Skill: ${title}`,
        content: content,
        tags: [skillName, 'skill', ...this.extractTagsFromMarkdown(content)],
        credibility: 0.85,
        metadata: {
          skill_name: skillName,
          path: skillPath
        }
      };

      await this.importToCortex(entry);
      this.stats.skills++;
    }

    console.log(`   ✅ 导入 ${this.stats.skills} 条技能知识`);
  }

  /**
   * 4. 提取项目优化经验 (ThunderDuck, ThunderMLX 等)
   */
  private async extractProjects() {
    console.log('\n🚀 提取项目优化经验...');

    const webPagesDir = join(CLAUDE_DIR, 'web/pages');
    if (!existsSync(webPagesDir)) {
      console.log('   ⚠️  web/pages/ 目录不存在');
      return;
    }

    // ThunderDuck GPU 优化
    await this.extractThunderDuck();

    // ThunderMLX MLX 优化
    await this.extractThunderMLX();

    // 其他项目文档
    const projectDocs = [
      'RESOURCE_EXECUTION_ENGINE_DESIGN.html',
      'solar-intro.html'
    ];

    for (const doc of projectDocs) {
      const docPath = join(webPagesDir, doc);
      if (!existsSync(docPath)) continue;

      const content = readFileSync(docPath, 'utf-8');
      const title = this.extractHTMLTitle(content) || doc;

      const entry: KnowledgeEntry = {
        source: 'projects',
        category: 'architecture',
        project: 'Solar',
        title: title,
        content: this.cleanHTML(content),
        tags: ['Solar', 'architecture', 'design'],
        credibility: 0.9,
        metadata: {
          file: doc
        }
      };

      await this.importToCortex(entry);
      this.stats.projects++;
    }

    console.log(`   ✅ 导入 ${this.stats.projects} 条项目知识`);
  }

  /**
   * 提取 ThunderDuck GPU 优化经验
   */
  private async extractThunderDuck() {
    const gpuOptPath = join(CLAUDE_DIR, 'web/pages/gpu-optimization.html');
    if (!existsSync(gpuOptPath)) {
      console.log('   ⚠️  gpu-optimization.html 不存在');
      return;
    }

    const content = readFileSync(gpuOptPath, 'utf-8');

    // 创建 ThunderDuck 主任务
    const taskId = this.cortex.createTask(
      'project_experience',
      'ThunderDuck GPU 优化',
      'solar',
      {
        project: 'ThunderDuck',
        domain: 'GPU优化',
        tech_stack: ['Apple Silicon', 'Metal', 'SIMD', 'UMA']
      }
    );

    // 提取核心知识点
    const knowledgePoints = [
      {
        key: 'uma_architecture',
        title: 'Apple Silicon UMA 架构优势',
        finding: '统一内存架构(UMA)允许 CPU 和 GPU 共享内存，实现零拷贝访问，减少数据传输开销。ThunderDuck 利用此特性实现高效的数据处理。',
        credibility: 0.95
      },
      {
        key: 'simd_reduce',
        title: 'GPU SIMD Reduce 优化',
        finding: 'Q6 (Simple Aggregation) 性能从 2.08x 提升到 5-10x。使用 Metal SIMD 指令加速聚合计算，充分利用 GPU 并行能力。',
        credibility: 0.95
      },
      {
        key: 'bitmap_anti_join',
        title: 'GPU Bitmap Anti-Join',
        finding: 'Q22 (Global Sales Opportunity Query) 性能从 8.49x 提升到 10-15x。使用位图索引加速反连接操作。',
        credibility: 0.95
      },
      {
        key: 'fused_filter_aggregate',
        title: 'Fused Filter+Aggregate',
        finding: '将过滤和聚合操作融合到单个 GPU kernel，减少内存往返，提升效率。适用于 Q1, Q12 等查询。',
        credibility: 0.9
      },
      {
        key: 'zero_copy_storage',
        title: 'GPU Zero-copy Storage',
        finding: '直接在 GPU 内存中存储列数据，避免 CPU-GPU 数据传输。结合 UMA 架构，实现真正的零拷贝访问。',
        credibility: 0.9
      },
      {
        key: 'implementation_strategy',
        title: 'ThunderDuck 实现策略',
        finding: 'Phase 1: 高收益查询 (Q6/Q1/Q12/Q22)。Phase 2: 中等收益 (Q3/Q5/Q10/Q19)。Phase 3: 复杂查询 (Q7/Q8/Q9)。优先实现 ROI 最高的优化。',
        credibility: 0.9
      }
    ];

    for (const kp of knowledgePoints) {
      await this.cortex.addSource(taskId, {
        citation_key: `thunderduck_${kp.key}`,
        title: kp.title,
        url: undefined,
        finding: kp.finding,
        credibility: kp.credibility
      }, 'project_experience');
    }

    this.stats.projects += knowledgePoints.length;
    console.log(`   ✅ ThunderDuck: 导入 ${knowledgePoints.length} 个核心知识点`);
  }

  /**
   * 提取 ThunderMLX 优化经验
   */
  private async extractThunderMLX() {
    console.log('   🚀 提取 ThunderMLX 优化经验...');

    // 创建 ThunderMLX 主任务
    const taskId = this.cortex.createTask(
      'project_experience',
      'ThunderMLX 优化',
      'solar',
      {
        project: 'ThunderMLX',
        domain: 'MLX优化',
        tech_stack: ['Apple Silicon', 'MLX', 'Metal', 'M4']
      }
    );

    // 提取核心知识点
    const knowledgePoints = [
      {
        key: 'mlx_ttft_layered_routing',
        title: 'MLX TTFT 分层路由优化',
        finding: '基于 prompt 长度的 L1/L2/L3 分层路由策略。短 prompt (≤512) +1.7%，中 prompt (512-2048) +3%+1.7%，长 prompt (>2048) +4%+1.7%。引用 exp_rules 规则确保一致性。',
        credibility: 0.95
      },
      {
        key: 'flashattention_metal',
        title: 'FlashAttention on Metal 评估',
        finding: 'Tiling + Online Softmax 减少 HBM 读写。实现复杂度高 (2-4个月)，预期长序列 2-5x 加速。当前短期用 Prompt Cache (15-23x) 已足够高效。',
        credibility: 0.9
      },
      {
        key: 'kernel_fusion_mlx_compile',
        title: 'MLX Kernel Fusion 实测',
        finding: '@mlx.compile 装饰器在 FFN 层效果甚微 (+0.9%)，因为 MLX 已使用 mx.fast.scaled_dot_product_attention 优化关键路径。不推荐额外折腾 compile。',
        credibility: 0.95
      },
      {
        key: 'kv_cache_optimization',
        title: 'KV Cache 优化方案',
        finding: 'MLX array 不可变，concatenate 每次分配新内存。方案：预分配 max_seq_len 连续内存 (复杂度低，收益高) > KV Cache int8 量化 (复杂度中) > Paged KV Cache (复杂度极高，不推荐)。',
        credibility: 0.9
      },
      {
        key: 'quantization_benchmark',
        title: 'MLX 量化基准测试 - 4bit vs 8bit',
        finding: 'Qwen2.5-3B: 4-bit TTFT 67.1ms, TPS 47.8 vs 8-bit TTFT 73.8ms, TPS 26.9。4-bit TTFT 快 10%, TPS 快 78%。4-bit 是 Coding LLM 最佳选择。',
        credibility: 0.95
      },
      {
        key: 'optimization_priority',
        title: 'MLX 优化优先级排序',
        finding: '已实现: RadixAttention 8-21x, Prompt Cache 15-23x, 4-bit Quant TTFT 67ms。推荐优先级: P1 Kernel Fusion, P2 KV Cache 预分配, P3 KV Cache 量化, P4 FlashAttention (高复杂度), P5 Paged KV Cache (不推荐)。',
        credibility: 0.95
      },
      {
        key: 'gpu_vs_ane',
        title: 'GPU vs ANE 混合推理结论',
        finding: '当前不推荐 GPU+ANE 混合用于 LLM。Apple 官方推荐 GPU (内存带宽优势)，ANE 优势是功耗 (降低 3x) 而非速度。ANE 适用小模型 (<1B) 低功耗场景，不适用大模型推理。',
        credibility: 0.95
      },
      {
        key: 'speculative_decoding',
        title: 'MLX 投机解码 (Speculative Decoding)',
        finding: 'M4 16GB, Qwen2.5-7B-4bit: draft_tokens=2 最优，23.6→40.6 tok/s (+72%)，内存仅增 0.4GB。Draft Model 用 Qwen2.5-0.5B-4bit。',
        credibility: 0.95
      },
      {
        key: 'prompt_cache_benchmark',
        title: 'MLX Prompt Cache 性能实测',
        finding: 'M4 16GB, Qwen2.5-7B-4bit: 431 tokens 系统提示节省 1.5s TTFT (+39%)。适用固定系统提示的多轮对话、API 服务。',
        credibility: 0.95
      },
      {
        key: 'fused_qkv_projection',
        title: 'Fused QKV Projection 实现',
        finding: '将 q_proj/k_proj/v_proj 合并为单个 qkv_proj，3 次矩阵乘法→1 次。减少内存访问和 kernel launch 开销。100 tokens +2.2%, 200 tokens +4.7%。',
        credibility: 0.95
      }
    ];

    for (const kp of knowledgePoints) {
      await this.cortex.addSource(taskId, {
        citation_key: `thundermlx_${kp.key}`,
        title: kp.title,
        url: undefined,
        finding: kp.finding,
        credibility: kp.credibility
      }, 'project_experience');
    }

    this.stats.projects += knowledgePoints.length;
    console.log(`   ✅ ThunderMLX: 导入 ${knowledgePoints.length} 个核心知识点`);
  }

  /**
   * 导入单条知识到 Cortex
   */
  private async importToCortex(entry: KnowledgeEntry) {
    // 创建任务
    const taskId = this.cortex.createTask(
      'knowledge_base',
      entry.title,
      'solar',
      {
        source: entry.source,
        category: entry.category,
        project: entry.project,
        ...entry.metadata
      }
    );

    // 存储为 source
    await this.cortex.addSource(taskId, {
      citation_key: this.generateCitationKey(entry),
      title: entry.title,
      url: undefined,
      finding: this.truncateContent(entry.content),
      credibility: entry.credibility
    }, entry.source);

    this.stats.total++;
  }

  /**
   * 工具方法
   */

  private categorizeFavorite(title: string, content: string): string {
    const text = `${title} ${content}`.toLowerCase();

    if (text.includes('architecture') || text.includes('架构')) return 'architecture';
    if (text.includes('optimization') || text.includes('优化')) return 'optimization';
    if (text.includes('rule') || text.includes('铁律')) return 'rule';
    if (text.includes('lesson') || text.includes('教训')) return 'lesson';

    return 'general';
  }

  private parseTags(tagsJson: string | null): string[] {
    if (!tagsJson) return [];
    try {
      return JSON.parse(tagsJson);
    } catch {
      return [];
    }
  }

  private extractTagsFromMarkdown(content: string): string[] {
    const tags: string[] = [];

    // 提取常见技术术语
    const keywords = ['GPU', 'SIMD', 'Metal', 'UMA', 'TPC-H', 'Cortex', 'TVS', 'REE'];
    for (const kw of keywords) {
      if (content.includes(kw)) tags.push(kw);
    }

    return tags;
  }

  private extractHTMLTitle(html: string): string | null {
    const match = html.match(/<title>(.+?)<\/title>/i);
    return match ? match[1] : null;
  }

  private cleanHTML(html: string): string {
    // 简单的 HTML 清理，保留文本内容
    return html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 5000); // 限制长度
  }

  private generateCitationKey(entry: KnowledgeEntry): string {
    const prefix = entry.source.substring(0, 3);
    const slug = entry.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .substring(0, 40);
    return `${prefix}_${slug}`;
  }

  private truncateContent(content: string, maxLen: number = 5000): string {
    if (content.length <= maxLen) return content;
    return content.substring(0, maxLen) + '...';
  }

  private printStats() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 知识提取统计\n');
    console.log(`   Favorites  : ${this.stats.favorites} 条`);
    console.log(`   Rules      : ${this.stats.rules} 条`);
    console.log(`   Skills     : ${this.stats.skills} 条`);
    console.log(`   Projects   : ${this.stats.projects} 条`);
    console.log(`   ────────────────────────────`);
    console.log(`   总计       : ${this.stats.total} 条`);
    console.log('='.repeat(60));
  }
}

// CLI 执行
if (import.meta.main) {
  const extractor = new KnowledgeExtractor();

  const args = process.argv.slice(2);
  const options: any = {};

  if (args.includes('--favorites-only')) {
    options.favorites = true;
    options.rules = false;
    options.skills = false;
    options.projects = false;
  } else if (args.includes('--rules-only')) {
    options.favorites = false;
    options.rules = true;
    options.skills = false;
    options.projects = false;
  } else if (args.includes('--skills-only')) {
    options.favorites = false;
    options.rules = false;
    options.skills = true;
    options.projects = false;
  } else if (args.includes('--projects-only')) {
    options.favorites = false;
    options.rules = false;
    options.skills = false;
    options.projects = true;
  }

  await extractor.extract(options);
}

export { KnowledgeExtractor, KnowledgeEntry };
