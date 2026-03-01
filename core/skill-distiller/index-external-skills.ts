#!/usr/bin/env bun
/**
 * 外部技能索引工具
 * 将 ~/.agents/skills/ 的技能索引到 Solar 技能库
 *
 * P0 改进：索引外部 1,497 个 skill
 */

import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import { Database } from 'bun:sqlite';

const SKILLS_DIR = join(homedir(), '.agents', 'skills');
const DB_PATH = join(homedir(), '.solar', 'solar.db');

// 技术领域分类
const TECH_DOMAINS: Record<string, string[]> = {
  python: ['python', 'django', 'flask', 'fastapi', 'pandas', 'numpy'],
  javascript: ['javascript', 'js', 'node', 'nodejs', 'typescript', 'ts'],
  react: ['react', 'reactjs', 'nextjs', 'next.js'],
  vue: ['vue', 'vuejs', 'nuxt'],
  kubernetes: ['kubernetes', 'k8s', 'helm', 'kustomize'],
  terraform: ['terraform', 'iac', 'infrastructure'],
  docker: ['docker', 'container', 'containerization'],
  rust: ['rust', 'rustlang', 'cargo'],
  go: ['golang', 'go ', ' golang'],
  database: ['sql', 'postgres', 'mysql', 'mongodb', 'database', 'redis'],
  api: ['api', 'rest', 'graphql', 'grpc'],
  security: ['security', 'auth', 'oauth', 'pentest', 'vulnerability'],
  testing: ['test', 'testing', 'e2e', 'unit', 'integration'],
  devops: ['ci', 'cd', 'cicd', 'pipeline', 'deploy', 'deployment'],
  git: ['git', 'github', 'gitlab', 'branch', 'commit'],
  cloud: ['aws', 'azure', 'gcp', 'cloud', 'serverless'],
  mobile: ['ios', 'android', 'flutter', 'react-native', 'mobile'],
  ai: ['ai', 'ml', 'machine-learning', 'llm', 'openai', 'embedding'],
};

// 从内容提取标签
function extractTags(name: string, description: string, content: string): string[] {
  const tags = new Set<string>();
  const text = `${name} ${description} ${content}`.toLowerCase();

  // 匹配技术领域
  for (const [domain, keywords] of Object.entries(TECH_DOMAINS)) {
    for (const kw of keywords) {
      if (text.includes(kw)) {
        tags.add(domain);
        break;
      }
    }
  }

  // 从名称提取
  const nameParts = name.split('-');
  for (const part of nameParts) {
    if (part.length >= 3 && !['the', 'and', 'for', 'with'].includes(part)) {
      tags.add(part);
    }
  }

  return Array.from(tags).slice(0, 10);
}

// 解析 SKILL.md
function parseSkillMd(filePath: string, dirName: string): {
  name: string;
  description: string;
  content: string;
} | null {
  try {
    const content = readFileSync(filePath, 'utf-8');

    // 解析 YAML frontmatter
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
    let name = dirName;
    let description = '';

    if (frontmatterMatch) {
      const fm = frontmatterMatch[1];
      const nameMatch = fm.match(/^name:\s*(.+)$/m);
      const descMatch = fm.match(/^description:\s*(.+)$/m);

      if (nameMatch) name = nameMatch[1].trim();
      if (descMatch) description = descMatch[1].trim();
    }

    return { name, description, content };
  } catch {
    return null;
  }
}

// 主函数
async function indexExternalSkills() {
  console.log('📦 外部技能索引工具\n');
  console.log(`源目录: ${SKILLS_DIR}`);
  console.log(`目标数据库: ${DB_PATH}\n`);

  const db = new Database(DB_PATH);

  // 扫描技能
  const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
  let indexed = 0;
  let skipped = 0;
  let errors = 0;

  console.log(`发现 ${entries.length} 个目录，开始索引...\n`);

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (entry.name === 'SKILL-INDEX.md') continue;

    const skillPath = join(SKILLS_DIR, entry.name, 'SKILL.md');
    if (!existsSync(skillPath)) {
      skipped++;
      continue;
    }

    const parsed = parseSkillMd(skillPath, entry.name);
    if (!parsed) {
      errors++;
      continue;
    }

    // 检查是否已存在
    const existing = db.prepare(
      "SELECT skill_id FROM sys_skill_bank WHERE skill_id = ?"
    ).get(`ext_${entry.name}`);

    if (existing) {
      skipped++;
      continue;
    }

    // 提取标签
    const tags = extractTags(parsed.name, parsed.description, parsed.content);

    // 插入数据库
    const skillId = `ext_${entry.name}`;
    const intentHash = skillId; // 简单使用 skill_id 作为 intent_hash

    try {
      db.run(`
        INSERT INTO sys_skill_bank (
          skill_id, intent_hash, name, description, skill_type, layer, scope, status,
          tags, source, source_ref, llm_prompt_template, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
      `, [
        skillId,
        intentHash,
        parsed.name,
        parsed.description,
        'template',
        'domain',
        'task_specific',
        'active',
        JSON.stringify(tags),
        'external_skill',
        skillPath,
        parsed.content.slice(0, 8000) // 截断内容
      ]);
      indexed++;
    } catch (e) {
      console.error(`  ❌ 插入失败: ${entry.name}`, e);
      errors++;
    }
  }

  db.close();

  // 统计
  console.log('─'.repeat(50));
  console.log('📊 索引结果\n');
  console.log(`  ✅ 索引成功: ${indexed}`);
  console.log(`  ⏭️  跳过: ${skipped}`);
  console.log(`  ❌ 错误: ${errors}`);

  // 验证
  const db2 = new Database(DB_PATH);
  const total = db2.prepare("SELECT COUNT(*) as cnt FROM sys_skill_bank").get() as { cnt: number };
  const bySource = db2.prepare(`
    SELECT source, COUNT(*) as cnt FROM sys_skill_bank GROUP BY source ORDER BY cnt DESC
  `).all() as { source: string; cnt: number }[];
  db2.close();

  console.log(`\n📈 技能库统计`);
  console.log(`  总计: ${total.cnt}`);
  for (const s of bySource) {
    console.log(`  - ${s.source}: ${s.cnt}`);
  }
}

indexExternalSkills();
