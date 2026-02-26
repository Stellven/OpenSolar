/**
 * MEMRL Skill Importer - 技能导入器
 *
 * 从多个来源导入技能到 sys_skill_bank:
 * 1. ~/.claude/skills/ 目录 (现有 91 个)
 * 2. SkillsMP (skillsmp.com)
 */

import { Database } from 'bun:sqlite';
import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';

const db = new Database(`${process.env.HOME}/.solar/solar.db`);

// SKILL.md frontmatter 类型
interface SkillFrontmatter {
  name: string;
  description: string;
  user_invocable?: boolean;
  disable_model_invocation?: boolean;
  context?: string;
  agent?: string;
  argument_hint?: string;
}

// 解析 SKILL.md frontmatter
function parseFrontmatter(content: string, dirName: string): { frontmatter: SkillFrontmatter; body: string } {
  const match = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);

  if (!match) {
    // 无 frontmatter，使用目录名作为名称
    // 尝试从内容第一行提取标题
    const titleMatch = content.match(/^#\s+(.+)$/m);
    const name = titleMatch ? titleMatch[1].trim() : dirName.replace(/-/g, ' ');

    // 提取描述（第一段非标题内容）
    const descMatch = content.match(/^[^#\n][^\n]*/m);
    const description = descMatch ? descMatch[0].trim().slice(0, 200) : '';

    return {
      frontmatter: { name, description },
      body: content
    };
  }

  const frontmatterLines = match[1].split('\n');
  const frontmatter: Record<string, any> = {};

  for (const line of frontmatterLines) {
    const colonIndex = line.indexOf(':');
    if (colonIndex > 0) {
      const key = line.slice(0, colonIndex).trim().replace(/-/g, '_');
      let value = line.slice(colonIndex + 1).trim();

      // 移除引号
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
      }

      frontmatter[key] = value;
    }
  }

  // 如果没有 name，使用目录名
  if (!frontmatter.name) {
    frontmatter.name = dirName.replace(/-/g, ' ');
  }

  return {
    frontmatter: frontmatter as SkillFrontmatter,
    body: match[2]
  };
}

// 从内容提取关键词
function extractKeywords(name: string, description: string, body: string): string[] {
  const keywords = new Set<string>();

  // 1. 从名称提取
  const nameWords = name.toLowerCase().split(/[\s_-]+/);
  nameWords.forEach(w => { if (w.length > 2) keywords.add(w); });

  // 2. 中英文关键词映射
  const keywordPatterns: [RegExp, string[]][] = [
    [/\b(git|commit|push|pull|branch|merge)\b/gi, ['git', '提交', 'commit']],
    [/\b(review|审查|检查)\b/gi, ['review', '审查', '检查']],
    [/\b(test|测试)\b/gi, ['test', '测试']],
    [/\b(build|构建|编译)\b/gi, ['build', '构建', '编译']],
    [/\b(deploy|部署)\b/gi, ['deploy', '部署']],
    [/\b(email|邮件|mail)\b/gi, ['email', '邮件']],
    [/\b(notion|trello|calendar|日历|日程)\b/gi, ['notion', 'trello', '日历']],
    [/\b(api|接口)\b/gi, ['api', '接口']],
    [/\b(debug|调试|报错|错误|排查)\b/gi, ['debug', '调试', '报错']],
    [/\b(perf|性能|优化|慢)\b/gi, ['perf', '性能', '优化']],
    [/\b(doc|文档)\b/gi, ['doc', '文档']],
    [/\b(benchmark|基准)\b/gi, ['benchmark', '基准']],
    [/\b(shortcut|快捷|快捷键)\b/gi, ['shortcut', '快捷']],
    [/\b(browser|浏览器)\b/gi, ['browser', '浏览器']],
    [/\b(search|搜索|查找)\b/gi, ['search', '搜索']],
    [/\b(memory|记忆)\b/gi, ['memory', '记忆']],
    [/\b(report|报告)\b/gi, ['report', '报告']],
    [/\b(notebook|笔记)\b/gi, ['notebook', '笔记']],
    [/\b(reminder|提醒)\b/gi, ['reminder', '提醒']],
    [/\b(task|任务)\b/gi, ['task', '任务']],
    [/\b(image|图片|图像)\b/gi, ['image', '图片']],
    [/\b(office|办公)\b/gi, ['office', '办公']],
    [/\b(skin|皮肤)\b/gi, ['skin', '皮肤']],
    [/\b(restore|恢复)\b/gi, ['restore', '恢复']],
    [/\b(save|保存)\b/gi, ['save', '保存']],
    [/\b(theme|主题|风格)\b/gi, ['theme', '主题']],
    [/\b(log|日志)\b/gi, ['log', '日志']],
    [/\b(queue|队列)\b/gi, ['queue', '队列']],
    [/\b(http|网络)\b/gi, ['http', '网络']],
    [/\b(pr|pull request)\b/gi, ['pr', 'pull request']],
    [/\b(vercel|部署)\b/gi, ['vercel', '部署']],
  ];

  const fullText = `${name} ${description} ${body}`.toLowerCase();

  for (const [pattern, words] of keywordPatterns) {
    if (pattern.test(fullText)) {
      words.forEach(w => keywords.add(w));
    }
  }

  // 重置正则 lastIndex
  for (const [pattern] of keywordPatterns) {
    pattern.lastIndex = 0;
  }

  return Array.from(keywords).slice(0, 15);
}

// 推断技能类型
function inferSkillType(name: string, body: string): 'template' | 'workflow' | 'api_call' {
  const lowerName = name.toLowerCase();
  const lowerBody = body.toLowerCase();

  if (lowerBody.includes('agent:') || lowerBody.includes('@agent')) {
    return 'workflow';
  }

  if (lowerBody.includes('api') || lowerBody.includes('fetch') || lowerBody.includes('request')) {
    return 'api_call';
  }

  return 'template';
}

// 推断适用上下文
function inferContexts(name: string, body: string): string[] {
  const contexts = new Set<string>();
  const lowerText = `${name} ${body}`.toLowerCase();

  if (lowerText.includes('代码') || lowerText.includes('code') || lowerText.includes('review')) {
    contexts.add('coding');
  }
  if (lowerText.includes('测试') || lowerText.includes('test')) {
    contexts.add('testing');
  }
  if (lowerText.includes('文档') || lowerText.includes('doc')) {
    contexts.add('docs');
  }
  if (lowerText.includes('git') || lowerText.includes('commit')) {
    contexts.add('git');
  }
  if (lowerText.includes('部署') || lowerText.includes('deploy')) {
    contexts.add('ops');
  }
  if (lowerText.includes('分析') || lowerText.includes('analyze')) {
    contexts.add('analysis');
  }

  if (contexts.size === 0) {
    contexts.add('general');
  }

  return Array.from(contexts);
}

// 生成 Intent Hash
function generateIntentHash(name: string, description: string): string {
  const content = `${name}:${description}`.toLowerCase();
  // 简单哈希
  let hash = 0;
  for (let i = 0; i < content.length; i++) {
    const char = content.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `intent_${Math.abs(hash).toString(16).padStart(8, '0')}`;
}

// 导入单个技能
function importSkill(skillDir: string, skillPath: string): { imported: boolean; skill_id: string; name: string } | null {
  const skillMdPath = join(skillPath, 'SKILL.md');

  if (!existsSync(skillMdPath)) {
    return null;
  }

  try {
    const content = readFileSync(skillMdPath, 'utf-8');
    const { frontmatter, body } = parseFrontmatter(content, skillDir);

    if (!frontmatter.name) {
      return null;
    }

    const skillId = `skill_solar_${skillDir}`;
    const keywords = extractKeywords(frontmatter.name, frontmatter.description || '', body);
    const skillType = inferSkillType(frontmatter.name, body);
    const contexts = inferContexts(frontmatter.name, body);
    const intentHash = generateIntentHash(frontmatter.name, frontmatter.description || '');

    // 生成 LLM Prompt 模板
    const llmPromptTemplate = `你是 ${frontmatter.name} 专家。

${frontmatter.description || ''}

${body.slice(0, 2000)}

请根据以上指南执行任务。`;

    // 参数定义
    const parameters = frontmatter.argument_hint
      ? [{ name: 'input', type: 'string', description: '用户输入', required: true }]
      : [];

    // 标签
    const tags = keywords.slice(0, 5);

    // 插入数据库
    const stmt = db.prepare(`
      INSERT OR REPLACE INTO sys_skill_bank (
        skill_id, name, description, skill_type, intent_hash, q_value,
        llm_prompt_template, parameters, trigger_keywords, applicable_contexts,
        tags, source, validated
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    `);

    stmt.run(
      skillId,
      frontmatter.name,
      frontmatter.description || body.slice(0, 200),
      skillType,
      intentHash,
      0.7, // 初始 Q 值
      llmPromptTemplate,
      JSON.stringify(parameters),
      JSON.stringify(keywords),
      JSON.stringify(contexts),
      JSON.stringify(tags),
      'solar_existing'
    );

    return { imported: true, skill_id: skillId, name: frontmatter.name };
  } catch (error) {
    console.error(`  ❌ ${skillDir}: ${error}`);
    return null;
  }
}

// 导入所有现有技能
function importAllSolarSkills(): { success: number; failed: number; skills: string[] } {
  const skillsDir = `${process.env.HOME}/.claude/skills`;
  const dirs = readdirSync(skillsDir, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name);

  const skills: string[] = [];
  let success = 0;
  let failed = 0;

  console.log(`📂 发现 ${dirs.length} 个技能目录\n`);

  for (const dir of dirs) {
    const result = importSkill(dir, join(skillsDir, dir));
    if (result) {
      success++;
      skills.push(result.name);
      console.log(`✅ ${result.name}`);
    } else {
      failed++;
    }
  }

  return { success, failed, skills };
}

// 从 SkillsMP API 获取热门技能
async function fetchFromSkillsMP(limit: number = 50): Promise<any[]> {
  try {
    // SkillsMP 没有公开 API，这里用搜索页面解析
    // 实际实现需要调用他们的 API 或爬取页面
    console.log('⚠️ SkillsMP API 尚未公开，需要手动导入');
    return [];
  } catch (error) {
    console.error('SkillsMP 获取失败:', error);
    return [];
  }
}

// 主入口
async function main() {
  const command = process.argv[2] || 'import';

  if (command === 'import') {
    console.log('🚀 导入 Solar 现有技能到 sys_skill_bank\n');
    console.log('=' .repeat(50) + '\n');

    const result = importAllSolarSkills();

    console.log('\n' + '='.repeat(50));
    console.log(`\n📊 导入结果:`);
    console.log(`   成功: ${result.success}`);
    console.log(`   失败: ${result.failed}`);
    console.log(`   总计: ${result.success + result.failed}`);

    // 显示数据库统计
    const stats = db.prepare(`
      SELECT
        COUNT(*) as total,
        AVG(q_value) as avg_q,
        COUNT(CASE WHEN source = 'solar_existing' THEN 1 END) as solar_skills,
        COUNT(CASE WHEN source = 'manual' THEN 1 END) as manual_skills
      FROM sys_skill_bank
    `).get() as any;

    console.log(`\n📈 数据库统计:`);
    console.log(`   总技能数: ${stats.total}`);
    console.log(`   平均 Q 值: ${stats.avg_q?.toFixed(2)}`);
    console.log(`   Solar 现有: ${stats.solar_skills}`);
    console.log(`   手动添加: ${stats.manual_skills}`);
  }

  if (command === 'list') {
    const skills = db.prepare(`
      SELECT skill_id, name, trigger_keywords, q_value
      FROM sys_skill_bank
      ORDER BY q_value DESC
    `).all() as any[];

    console.log(`📋 技能列表 (${skills.length} 个):\n`);

    for (let i = 0; i < skills.length; i++) {
      const s = skills[i];
      const keywords = JSON.parse(s.trigger_keywords || '[]').slice(0, 3).join(', ');
      console.log(`${i + 1}. [Q=${s.q_value.toFixed(2)}] ${s.name}`);
      console.log(`   关键词: ${keywords}`);
    }
  }

  if (command === 'search') {
    const query = process.argv[3] || '';

    // 使用 SkillRetriever
    const { SkillRetriever } = await import('./skill-retriever');
    const retriever = new SkillRetriever();

    const results = retriever.retrieve(query);

    console.log(`🔍 搜索 "${query}":\n`);

    if (results.length === 0) {
      console.log('❌ 无匹配技能');
    } else {
      for (let i = 0; i < results.length; i++) {
        const s = results[i];
        console.log(`${i + 1}. [Q=${s.q_value.toFixed(2)}] ${s.name}`);
        console.log(`   描述: ${s.description}`);
        console.log(`   匹配: ${s.matched_keywords.join(', ') || '(无)'}`);
        console.log(`   分数: ${s.combined_score.toFixed(3)}`);
        console.log();
      }
    }

    retriever.close();
  }

  db.close();
}

main();
