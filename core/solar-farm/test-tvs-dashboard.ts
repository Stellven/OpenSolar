/**
 * 测试 TVS Dashboard 生成
 */
import { ReportStructure } from './report-template-writer';
import { writeFileSync } from 'fs';
import { join } from 'path';

const sessionId = 'test_tvs_demo';
const report = new ReportStructure(sessionId);

// 模拟章节数据
const mockChapters = [
  {
    chapterId: 'ch1',
    title: '记忆架构演进',
    authorModel: 'gemini-3-pro-preview',
    reviewerModel: 'deepseek-r1',
    qualityScore: 8.5,
    content: '本章探讨了 AI Agent 记忆系统的演进历程...\n\n从早期的简单键值存储到现代的多层次记忆架构，我们见证了显著的进步。',
    status: 'done'
  },
  {
    chapterId: 'ch2',
    title: 'Zettelkasten 卡片盒方法',
    authorModel: 'deepseek-v3',
    reviewerModel: 'gemini-2.5-pro',
    qualityScore: 9.2,
    content: 'Zettelkasten 方法起源于德国社会学家 Niklas Luhmann 的笔记系统...\n\n这种方法强调知识的关联性和涌现性。',
    status: 'done'
  },
  {
    chapterId: 'ch3',
    title: '实践案例分析',
    authorModel: 'glm-5',
    reviewerModel: 'gemini-3-pro-preview',
    qualityScore: 7.8,
    content: '本章分析三个实践案例：Mem0、A-MEM、以及 Solar 的记忆系统...\n\n通过对比可以看出不同系统的设计权衡。',
    status: 'done'
  }
];

// 计算统计
const avgScore = mockChapters.reduce((sum, ch) => sum + ch.qualityScore, 0) / mockChapters.length;
const totalWords = mockChapters.reduce((sum, ch) => sum + (ch.content?.length || 0), 0);

console.log('📊 生成 TVS Dashboard 测试...\n');
console.log(`   主题: AI Agent 记忆机制深度洞察`);
console.log(`   章节数: ${mockChapters.length}`);
console.log(`   平均质量: ${avgScore.toFixed(1)}/10`);
console.log(`   总字数: ${totalWords}\n`);

// 生成 HTML
const getModelNickname = (model: string | undefined): string => {
  if (!model) return '未知';
  const nicknames: Record<string, string> = {
    'glm-5': '老实人 GLM-5',
    'gemini-2.5-pro': '技术宅',
    'gemini-3-pro-preview': '千里马',
    'deepseek-v3': '鬼才码农',
    'deepseek-r1': '思考驼'
  };
  return nicknames[model] || model;
};

const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Agent 记忆机制深度洞察 - TVS Dashboard</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0a0e27;
      color: #e0e0e0;
      line-height: 1.6;
      padding: 20px;
    }
    .container { max-width: 1400px; margin: 0 auto; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
    .card {
      background: #1a1f3a;
      border: 1px solid #2a3f5f;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .card-title {
      font-size: 1.5em;
      font-weight: bold;
      margin-bottom: 15px;
      color: #4fc3f7;
      border-bottom: 2px solid #2a3f5f;
      padding-bottom: 10px;
    }
    .kv-grid { display: grid; gap: 10px; }
    .kv-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a3f5f; }
    .kv-key { color: #90caf9; font-weight: 500; }
    .kv-value { color: #e0e0e0; }
    .progress {
      width: 100%;
      height: 30px;
      background: #2a3f5f;
      border-radius: 15px;
      overflow: hidden;
      margin: 10px 0;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, #4fc3f7, #00bcd4);
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
    }
    th, td {
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #2a3f5f;
    }
    th {
      background: #2a3f5f;
      color: #4fc3f7;
      font-weight: 600;
    }
    tr:hover { background: #1e2942; }
    .chapter {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 1px solid #2a3f5f;
    }
    .chapter-title {
      color: #4fc3f7;
      font-size: 1.2em;
      font-weight: bold;
      margin-bottom: 10px;
    }
    .chapter-meta {
      color: #90caf9;
      font-size: 0.9em;
      margin-bottom: 10px;
    }
    .chapter-content {
      background: #0f1420;
      padding: 15px;
      border-radius: 4px;
      margin-top: 10px;
      white-space: pre-wrap;
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 0.9em;
      line-height: 1.5;
    }
    footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 2px solid #2a3f5f;
      text-align: center;
      color: #90caf9;
      font-size: 0.9em;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1 style="color: #4fc3f7; margin-bottom: 30px; font-size: 2.5em;">📊 深度洞察报告</h1>

    <div class="grid">
      <div class="card">
        <div class="card-title">📊 报告元数据</div>
        <div class="kv-grid">
          <div class="kv-item"><span class="kv-key">主题</span><span class="kv-value">AI Agent 记忆机制深度洞察</span></div>
          <div class="kv-item"><span class="kv-key">章节数</span><span class="kv-value">${mockChapters.length}</span></div>
          <div class="kv-item"><span class="kv-key">总字数</span><span class="kv-value">${totalWords.toLocaleString()}</span></div>
          <div class="kv-item"><span class="kv-key">专家团队</span><span class="kv-value">4 位专家</span></div>
          <div class="kv-item"><span class="kv-key">生成时间</span><span class="kv-value">${new Date().toLocaleString('zh-CN')}</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">⭐ 质量评分</div>
        <div class="progress">
          <div class="progress-bar" style="width: ${avgScore * 10}%">
            ${avgScore.toFixed(1)}/10
          </div>
        </div>
        <div style="margin-top: 15px; color: #90caf9;">
          各章节质量: ${mockChapters.map(c => c.qualityScore.toFixed(1)).join(', ')}
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📑 章节目录</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>章节标题</th>
            <th>作者</th>
            <th>审核</th>
            <th>质量</th>
            <th>字数</th>
          </tr>
        </thead>
        <tbody>
${mockChapters.map((ch, idx) => `          <tr>
            <td>${idx + 1}</td>
            <td>${ch.title}</td>
            <td>${getModelNickname(ch.authorModel)}</td>
            <td>${getModelNickname(ch.reviewerModel)}</td>
            <td>${ch.qualityScore.toFixed(1)}/10</td>
            <td>${(ch.content?.length || 0).toLocaleString()}</td>
          </tr>`).join('\n')}
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📖 章节详情</div>
${mockChapters.map((ch, idx) => `      <div class="chapter">
        <div class="chapter-title">第 ${idx + 1} 章: ${ch.title}</div>
        <div class="chapter-meta">
          作者: ${getModelNickname(ch.authorModel)} |
          审核: ${getModelNickname(ch.reviewerModel)} |
          质量: ${ch.qualityScore.toFixed(1)}/10 |
          字数: ${(ch.content?.length || 0).toLocaleString()}
        </div>
        <div class="chapter-content">${ch.content || '(内容缺失)'}</div>
      </div>`).join('\n')}
    </div>

    <footer>
      <p>Powered by Solar InsightAgent v2.3 · TVS Web Dashboard</p>
      <p>完整报告请查看: final-report.md</p>
    </footer>
  </div>
</body>
</html>`;

const baseDir = report.getBaseDir();
const htmlPath = join(baseDir, 'index.html');
writeFileSync(htmlPath, html, 'utf-8');

console.log('✅ TVS Dashboard 生成成功！\n');
console.log(`   📁 报告目录: ${baseDir}`);
console.log(`   🌐 HTML 文件: ${htmlPath}`);
console.log(`\n   在浏览器中打开: file://${htmlPath}\n`);

