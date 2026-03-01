#!/usr/bin/env bun
/**
 * Skill Indexer - 技能索引器和标签添加工具
 *
 * 功能：
 * 1. 扫描所有 SKILL.md 文件
 * 2. 根据 skill-tree.yaml 添加 category 和 tags
 * 3. 建立倒排索引
 * 4. 提供搜索函数
 */

import { readdirSync, readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { parse as parseYaml } from 'yaml';

// ============ 类型定义 ============

interface SkillMeta {
  name: string;
  description: string;
  category?: string;
  tags?: string[];
  [key: string]: any;
}

interface Skill {
  name: string;
  path: string;
  category: string;
  tags: string[];
  description: string;
  content: string;
}

interface SkillTree {
  categories: Record<string, {
    name: string;
    description: string;
    skills: string[];
  }>;
  tags: Record<string, string[]>;
  keywords: Record<string, string>;
}

interface SearchOptions {
  category?: string;
  tags?: string[];
  keyword?: string;
  limit?: number;
}

// ============ 配置 ============

const SKILLS_DIR = join(process.env.HOME!, '.claude/skills');
const SKILL_TREE_PATH = join(process.env.HOME!, '.claude/core/skill-tree.yaml');

// ============ 核心类 ============

export class SkillIndexer {
  private skills: Map<string, Skill> = new Map();
  private categoryIndex: Map<string, Set<string>> = new Map();
  private tagIndex: Map<string, Set<string>> = new Map();
  private skillTree: SkillTree | null = null;

  /**
   * 加载 skill-tree.yaml 配置
   */
  loadSkillTree(): SkillTree {
    if (this.skillTree) return this.skillTree;

    const content = readFileSync(SKILL_TREE_PATH, 'utf-8');
    this.skillTree = parseYaml(content) as SkillTree;
    return this.skillTree;
  }

  /**
   * 获取技能的分类
   */
  getCategory(skillName: string): string {
    const tree = this.loadSkillTree();

    for (const [category, data] of Object.entries(tree.categories)) {
      if (data.skills.includes(skillName)) {
        return category;
      }
    }
    return 'other';
  }

  /**
   * 推断技能的标签
   */
  inferTags(skillName: string, description: string): string[] {
    const tags: string[] = [];
    const desc = (skillName + ' ' + description).toLowerCase();

    // 基于关键词推断
    const tagKeywords: Record<string, string[]> = {
      git: ['git', 'commit', 'pr', 'branch', 'merge'],
      email: ['email', 'mail', '邮件'],
      apple: ['apple', 'mac', 'macos', 'shortcut', 'imessage'],
      browser: ['browser', 'playwright', '网页', 'web'],
      ai: ['ai', 'llm', 'gemini', 'claude', 'insight', 'analyze'],
      test: ['test', 'testing', 'spec'],
      docs: ['doc', '文档', 'report', '报告'],
      image: ['image', '图片', 'photo', 'imagen', 'selfie'],
      office: ['office', 'task', 'note', 'calendar'],
    };

    for (const [tag, keywords] of Object.entries(tagKeywords)) {
      if (keywords.some(kw => desc.includes(kw))) {
        tags.push(tag);
      }
    }

    return [...new Set(tags)].slice(0, 5);
  }

  /**
   * 解析 SKILL.md 的 frontmatter
   */
  parseFrontmatter(content: string): { meta: SkillMeta; body: string } {
    const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);

    if (!match) {
      return { meta: { name: '', description: '' }, body: content };
    }

    const frontmatter = match[1];
    const body = match[2];

    // 简单解析 YAML frontmatter
    const meta: SkillMeta = { name: '', description: '' };

    for (const line of frontmatter.split('\n')) {
      const colonIndex = line.indexOf(':');
      if (colonIndex === -1) continue;

      const key = line.slice(0, colonIndex).trim();
      let value: any = line.slice(colonIndex + 1).trim();

      // 处理数组
      if (value.startsWith('[') && value.endsWith(']')) {
        value = value.slice(1, -1).split(',').map(s => s.trim().replace(/['"]/g, ''));
      } else if (value === 'true') {
        value = true;
      } else if (value === 'false') {
        value = false;
      }

      meta[key] = value;
    }

    return { meta, body };
  }

  /**
   * 生成 frontmatter 字符串
   */
  generateFrontmatter(meta: SkillMeta): string {
    const lines: string[] = ['---'];

    for (const [key, value] of Object.entries(meta)) {
      if (value === undefined || value === null) continue;

      if (Array.isArray(value)) {
        lines.push(`${key}: [${value.map(v => `"${v}"`).join(', ')}]`);
      } else if (typeof value === 'boolean') {
        lines.push(`${key}: ${value}`);
      } else {
        lines.push(`${key}: ${value}`);
      }
    }

    lines.push('---');
    return lines.join('\n');
  }

  /**
   * 扫描所有技能
   */
  scanSkills(): Skill[] {
    const skills: Skill[] = [];
    const dirs = readdirSync(SKILLS_DIR, { withFileTypes: true });

    for (const dir of dirs) {
      if (!dir.isDirectory()) continue;

      const skillPath = join(SKILLS_DIR, dir.name, 'SKILL.md');
      if (!existsSync(skillPath)) continue;

      const content = readFileSync(skillPath, 'utf-8');
      const { meta, body } = this.parseFrontmatter(content);

      const skill: Skill = {
        name: meta.name || dir.name,
        path: skillPath,
        category: meta.category || this.getCategory(dir.name),
        tags: meta.tags || this.inferTags(dir.name, meta.description || ''),
        description: meta.description || '',
        content: body,
      };

      skills.push(skill);
    }

    return skills;
  }

  /**
   * 给 SKILL.md 添加 category 和 tags
   */
  async addCategoryAndTags(dryRun: boolean = false): Promise<{ updated: number; skipped: number }> {
    const tree = this.loadSkillTree();
    let updated = 0;
    let skipped = 0;

    const dirs = readdirSync(SKILLS_DIR, { withFileTypes: true });

    for (const dir of dirs) {
      if (!dir.isDirectory()) continue;

      const skillPath = join(SKILLS_DIR, dir.name, 'SKILL.md');
      if (!existsSync(skillPath)) continue;

      const content = readFileSync(skillPath, 'utf-8');
      const { meta, body } = this.parseFrontmatter(content);

      // 跳过已有 category 的
      if (meta.category) {
        skipped++;
        continue;
      }

      // 添加 category 和 tags
      meta.category = this.getCategory(dir.name);
      meta.tags = this.inferTags(dir.name, meta.description || '');

      // 重写文件
      const newContent = this.generateFrontmatter(meta) + '\n' + body;

      if (!dryRun) {
        writeFileSync(skillPath, newContent, 'utf-8');
      }

      updated++;
    }

    return { updated, skipped };
  }

  /**
   * 建立索引
   */
  buildIndex(): void {
    const skills = this.scanSkills();

    this.skills.clear();
    this.categoryIndex.clear();
    this.tagIndex.clear();

    for (const skill of skills) {
      // 技能映射
      this.skills.set(skill.name, skill);

      // 分类索引
      if (!this.categoryIndex.has(skill.category)) {
        this.categoryIndex.set(skill.category, new Set());
      }
      this.categoryIndex.get(skill.category)!.add(skill.name);

      // 标签索引
      for (const tag of skill.tags) {
        if (!this.tagIndex.has(tag)) {
          this.tagIndex.set(tag, new Set());
        }
        this.tagIndex.get(tag)!.add(skill.name);
      }
    }
  }

  /**
   * 搜索技能
   */
  search(options: SearchOptions): Skill[] {
    this.buildIndex();

    let candidates = new Set(this.skills.keys());

    // 按分类过滤
    if (options.category) {
      const categorySkills = this.categoryIndex.get(options.category);
      if (categorySkills) {
        candidates = new Set([...candidates].filter(s => categorySkills.has(s)));
      }
    }

    // 按标签过滤
    if (options.tags && options.tags.length > 0) {
      for (const tag of options.tags) {
        const tagSkills = this.tagIndex.get(tag);
        if (tagSkills) {
          candidates = new Set([...candidates].filter(s => tagSkills.has(s)));
        }
      }
    }

    // 关键词匹配
    if (options.keyword) {
      const tree = this.loadSkillTree();
      const keyword = options.keyword.toLowerCase();

      // 检查关键词映射
      const directMatch = tree.keywords[keyword];
      if (directMatch && this.skills.has(directMatch)) {
        return [this.skills.get(directMatch)!];
      }

      // 模糊匹配
      candidates = new Set([...candidates].filter(name => {
        const skill = this.skills.get(name);
        if (!skill) return false;
        return skill.name.includes(keyword) ||
               skill.description.toLowerCase().includes(keyword) ||
               skill.tags.some(t => t.includes(keyword));
      }));
    }

    // 转换并限制数量
    const results = [...candidates]
      .map(name => this.skills.get(name)!)
      .filter(Boolean)
      .slice(0, options.limit || 10);

    return results;
  }

  /**
   * 打印索引统计
   */
  printStats(): void {
    this.buildIndex();

    console.log('\n📊 Skill Indexer 统计');
    console.log('='.repeat(40));
    console.log(`总技能数: ${this.skills.size}`);
    console.log(`分类数: ${this.categoryIndex.size}`);
    console.log(`标签数: ${this.tagIndex.size}`);

    console.log('\n📁 分类分布:');
    for (const [category, skills] of this.categoryIndex) {
      console.log(`  ${category}: ${skills.size} 个技能`);
    }

    console.log('\n🏷️ 热门标签 (Top 10):');
    const sortedTags = [...this.tagIndex.entries()]
      .sort((a, b) => b[1].size - a[1].size)
      .slice(0, 10);
    for (const [tag, skills] of sortedTags) {
      console.log(`  ${tag}: ${skills.size} 个技能`);
    }
  }
}

// ============ CLI ============

async function main() {
  const indexer = new SkillIndexer();
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'add-tags': {
      const dryRun = args.includes('--dry-run');
      console.log(dryRun ? '🔍 干跑模式，不修改文件\n' : '📝 添加 category 和 tags...\n');
      const result = await indexer.addCategoryAndTags(dryRun);
      console.log(`✅ 更新: ${result.updated} 个技能`);
      console.log(`⏭️ 跳过: ${result.skipped} 个技能 (已有 category)`);
      break;
    }

    case 'stats': {
      indexer.printStats();
      break;
    }

    case 'search': {
      const keyword = args[1];
      if (!keyword) {
        console.log('用法: skill-indexer search <关键词>');
        process.exit(1);
      }

      const results = indexer.search({ keyword });
      console.log(`\n🔍 搜索 "${keyword}" 找到 ${results.length} 个技能:\n`);

      for (const skill of results) {
        console.log(`  ${skill.name}`);
        console.log(`    分类: ${skill.category}`);
        console.log(`    标签: ${skill.tags.join(', ')}`);
        console.log(`    描述: ${skill.description.slice(0, 50)}...`);
        console.log();
      }
      break;
    }

    case 'list': {
      const category = args[1];
      indexer.buildIndex();

      if (category) {
        const skills = indexer.search({ category });
        console.log(`\n📁 ${category} 分类下的技能 (${skills.length}):\n`);
        for (const skill of skills) {
          console.log(`  - ${skill.name}: ${skill.description.slice(0, 40)}`);
        }
      } else {
        indexer.printStats();
      }
      break;
    }

    default: {
      console.log(`
Skill Indexer - Solar 技能索引器

用法:
  skill-indexer add-tags       给所有 SKILL.md 添加 category 和 tags
  skill-indexer add-tags --dry-run  干跑模式，只显示会修改什么
  skill-indexer stats          显示索引统计
  skill-indexer search <关键词> 搜索技能
  skill-indexer list [分类]    列出技能
`);
    }
  }
}

main().catch(console.error);
