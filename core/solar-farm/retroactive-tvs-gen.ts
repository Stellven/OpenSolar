#!/usr/bin/env bun
/**
 * 为历史洞察报告生成 TVS Dashboard
 * 从文件系统解析报告信息，生成 Web 版本
 */

import { existsSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';

interface ChapterInfo {
  id: number;
  title: string;
  author: string;
  reviewer: string;
  quality: number;
  wordCount: number;
  preview?: string;
}

interface ExpertReview {
  expert: string;
  score: number;
  comment: string;
}

function extractReportInfo(reportDir: string) {
  const finalReportPath = join(reportDir, 'final-report.md');
  if (!existsSync(finalReportPath)) {
    throw new Error('final-report.md not found');
  }

  const content = readFileSync(finalReportPath, 'utf-8');

  // 提取主题（从第一个 # 标题）
  const topicMatch = content.match(/^# (.+)$/m);
  const topic = topicMatch ? topicMatch[1].trim() : '未知主题';

  // 提取综合评分
  const scoreMatch = content.match(/综合评分[：:]\s*(\d+\.?\d*)\/10/);
  const avgScore = scoreMatch ? parseFloat(scoreMatch[1]) : 8.0;

  // 提取专家评论
  const expertReviews: ExpertReview[] = [];
  const reviewPattern = /###\s+(.+?)\s+\(权重[：:]\s*(\d+)%\)\s*评分[：:]\s*(\d+\.?\d*)\/10\s+关键发现[：:]\s+([\s\S]+?)(?=###|$)/g;
  let reviewMatch;
  while ((reviewMatch = reviewPattern.exec(content)) !== null) {
    expertReviews.push({
      expert: reviewMatch[1].trim(),
      score: parseFloat(reviewMatch[3]),
      comment: reviewMatch[4].trim()
        .replace(/(\d+\.)\s+/g, '$1\n')  // 在 "1. ", "2. " 等后面加换行
        .substring(0, 500)               // 截取字符
        .replace(/\n/g, '<br>')          // 转成 HTML 换行标签
        + '...'
    });
  }

  // 提取章节信息
  const chapters: ChapterInfo[] = [];
  const chapterFiles = readdirSync(reportDir)
    .filter(f => f.match(/^ch_\d+\.md$/))
    .sort();

  chapterFiles.forEach((file, idx) => {
    const chPath = join(reportDir, file);
    const chContent = readFileSync(chPath, 'utf-8');

    // 提取标题
    const titleMatch = chContent.match(/^##?\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1].trim() : `第 ${idx + 1} 章`;

    // 从章节内容开头提取作者（从"我就是XXX"模式）
    let author = '专家团队';
    let reviewer = '交响乐团';
    let quality = avgScore;

    const authorMatch = chContent.match(/我就是(千里马|鬼才码农|老实人|技术宅|思考驼|GLM-5|GLM-4|闪电侠)/);
    if (authorMatch) {
      author = authorMatch[1];
    }

    // 提取章节内容预览（过滤掉开头的角色扮演部分）
    let cleanContent = chContent;

    // 1. 先移除开头到第一个 --- 或 ## 之前的所有内容（牛马心声部分）
    const contentStart = chContent.search(/^(---|##)/m);
    if (contentStart > 0) {
      cleanContent = chContent.substring(contentStart);
    }

    // 2. 移除分隔符行
    cleanContent = cleanContent.replace(/^---+$/mg, '');

    // 3. 移除标题行
    cleanContent = cleanContent.replace(/^##?\s+.+$/mg, '');

    const contentPreview = cleanContent
      .trim()
      .split('\n')
      .filter(line => {
        const trimmed = line.trim();
        // 过滤短行、空行、以及残留的角色扮演内容
        return trimmed.length > 20
          && !trimmed.match(/好的[，,!！]/)
          && !trimmed.match(/Let's go/i)
          && !trimmed.match(/我就是|交给我|准备好|大展身手/)
          && !trimmed.match(/^[*-]+$/);
      })
      .slice(0, 5) // 取前5个有效段落
      .join('\n')
      .substring(0, 300) + '...';

    chapters.push({
      id: idx + 1,
      title,
      author,
      reviewer,
      quality,
      wordCount: chContent.length,
      preview: contentPreview
    });
  });

  // 提取专家团队（从内容中推断）
  const expertSet = new Set<string>();
  const expertMatches = content.matchAll(/(千里马|鬼才码农|老实人|技术宅|思考驼|GLM-5|GLM-4)/g);
  for (const match of expertMatches) {
    expertSet.add(match[1]);
  }

  return {
    topic,
    chapters,
    avgScore,
    experts: Array.from(expertSet),
    totalWords: content.length,
    timestamp: new Date().toISOString(),
    expertReviews
  };
}

function generateTVSDashboard(reportDir: string) {
  const info = extractReportInfo(reportDir);

  // 生成 HTML
  const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${info.topic} - TVS Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    @media print {
      body { background: white; color: black; }
      .card { border: 1px solid #ccc; page-break-inside: avoid; }
      .no-print { display: none; }
    }
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
          <div class="kv-item"><span class="kv-key">主题</span><span class="kv-value">${info.topic}</span></div>
          <div class="kv-item"><span class="kv-key">章节数</span><span class="kv-value">${info.chapters.length}</span></div>
          <div class="kv-item"><span class="kv-key">总字数</span><span class="kv-value">${info.totalWords}</span></div>
          <div class="kv-item"><span class="kv-key">专家团队</span><span class="kv-value">${info.experts.length} 位专家</span></div>
          <div class="kv-item"><span class="kv-key">生成时间</span><span class="kv-value">${new Date(info.timestamp).toLocaleString('zh-CN')}</span></div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">⭐ 质量评分</div>
        <div class="progress">
          <div class="progress-bar" style="width: ${info.avgScore * 10}%">
            ${info.avgScore.toFixed(1)}/10
          </div>
        </div>
        <div style="margin-top: 15px; color: #90caf9;">
          各章节质量: ${info.chapters.map(c => c.quality.toFixed(1)).join(', ')}
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
          ${info.chapters.map(ch => `
          <tr>
            <td>${ch.id}</td>
            <td>${ch.title}</td>
            <td>${ch.author}</td>
            <td>${ch.reviewer}</td>
            <td>${ch.quality.toFixed(1)}/10</td>
            <td>${ch.wordCount}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>

    ${info.expertReviews.length > 0 ? `
    <div class="card" style="margin-top: 20px;">
      <div class="card-title">👥 专家评审</div>
      ${info.expertReviews.map(review => `
      <div class="chapter">
        <div class="chapter-title">${review.expert} - ${review.score}/10</div>
        <div class="chapter-content" style="white-space: normal;">${review.comment}</div>
      </div>`).join('')}
    </div>` : ''}

    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📈 质量趋势</div>
      <canvas id="qualityChart" style="max-height: 300px;"></canvas>
    </div>

    <div class="card" style="margin-top: 20px;">
      <div class="card-title">📖 章节详情</div>
      ${info.chapters.map(ch => `
      <div class="chapter">
        <div class="chapter-title">第 ${ch.id} 章: ${ch.title}</div>
        <div class="chapter-meta">
          作者: ${ch.author} |
          审核: ${ch.reviewer} |
          质量: ${ch.quality.toFixed(1)}/10 |
          字数: ${ch.wordCount}
        </div>
        <div class="chapter-content" style="white-space: normal;">${ch.preview || '（完整内容请查看 final-report.md）'}</div>
      </div>`).join('')}
    </div>

    <div class="no-print" style="margin-top: 20px; text-align: center;">
      <button onclick="window.print()" style="
        background: #4fc3f7;
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 6px;
        font-size: 16px;
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      ">📄 导出 PDF</button>
    </div>

    <footer>
      <p>Powered by Solar InsightAgent v2.3 · TVS Web Dashboard</p>
      <p>完整报告请查看: final-report.md</p>
    </footer>
  </div>

  <script>
    // 质量趋势图
    const ctx = document.getElementById('qualityChart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ${JSON.stringify(info.chapters.map(ch => `第${ch.id}章`))},
        datasets: [{
          label: '章节质量评分',
          data: ${JSON.stringify(info.chapters.map(ch => ch.quality))},
          borderColor: '#4fc3f7',
          backgroundColor: 'rgba(79, 195, 247, 0.1)',
          tension: 0.3,
          fill: true,
          pointRadius: 6,
          pointHoverRadius: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#e0e0e0' }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 10,
            ticks: { color: '#90caf9' },
            grid: { color: '#2a3f5f' }
          },
          x: {
            ticks: { color: '#90caf9' },
            grid: { color: '#2a3f5f' }
          }
        }
      }
    });
  </script>
</body>
</html>`;

  const htmlPath = join(reportDir, 'index.html');
  writeFileSync(htmlPath, html, 'utf-8');

  console.log(`✅ TVS Dashboard 生成成功！`);
  console.log(`   📁 报告目录: ${reportDir}`);
  console.log(`   🌐 HTML 文件: ${htmlPath}`);
  console.log(`\n可以用浏览器打开查看：`);
  console.log(`   open ${htmlPath}`);
}

// Main
const reportDir = process.argv[2] || join(homedir(), '.solar/insight-reports/insight_1770866384788');

if (!existsSync(reportDir)) {
  console.error(`❌ 报告目录不存在: ${reportDir}`);
  process.exit(1);
}

generateTVSDashboard(reportDir);
