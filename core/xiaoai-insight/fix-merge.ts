import Database from 'bun:sqlite';
import { join } from 'path';
import { mkdirSync, writeFileSync, existsSync } from 'fs';

const taskId = 'insight_1771238363627_1yak34';
const topic = '自我进化智能体';
const artifactDir = join(process.env.HOME!, '.solar', 'cortex', 'artifacts', taskId);

// 打开数据库
const db = new Database(join(process.env.HOME!, '.solar', 'solar.db'));

// 获取大纲
const outlineRows = db.query(`
  SELECT section_id, section_order, section_title
  FROM cortex_outline
  WHERE task_id = ?
  ORDER BY section_order
`).all(taskId) as any[];

console.log('大纲章节:', outlineRows.map(s => s.section_order + '. ' + s.section_title).join(', '));

// 获取最终版本的章节
const finalDrafts = db.query(`
  SELECT draft_id, section_id, content
  FROM cortex_draft_sections
  WHERE task_id = ? AND is_final = 1 AND content != ''
`).all(taskId) as any[];

console.log('最终草稿数:', finalDrafts.length);

// 检查每个章节
for (const section of outlineRows) {
  const draft = finalDrafts.find(d => d.section_id === section.section_id);
  console.log('章节', section.section_order, ':', draft ? '✅ 有内容(' + draft.content.length + '字)' : '❌ 缺失');
}

// 组装完整报告
let fullReport = '# ' + topic + '\n\n';
fullReport += '> 生成时间: ' + new Date().toISOString() + '\n';
fullReport += '> 任务ID: ' + taskId + '\n\n';
fullReport += '---\n\n';

// 添加目录
fullReport += '## 目录\n\n';
for (const section of outlineRows) {
  fullReport += section.section_order + '. ' + section.section_title + '\n';
}
fullReport += '\n---\n\n';

// 添加各章节
for (const section of outlineRows) {
  const draft = finalDrafts.find(d => d.section_id === section.section_id);
  fullReport += '## ' + section.section_order + '. ' + section.section_title + '\n\n';
  if (draft) {
    fullReport += draft.content + '\n\n';
  } else {
    fullReport += '*该章节内容待补充*\n\n';
  }
}

// 保存
const timestamp = Date.now();
const fileName = 'phase6_full_report_' + timestamp + '.md';
const filePath = join(artifactDir, fileName);

if (!existsSync(artifactDir)) {
  mkdirSync(artifactDir, { recursive: true });
}

writeFileSync(filePath, fullReport);

console.log('\n✅ 报告已重新生成');
console.log('📁', filePath);
console.log('📏 总长度:', fullReport.length, '字符');

// 更新之前的空报告（如果有的话）
const emptyReportCheck = db.query(`
  SELECT file_path FROM cortex_artifacts
  WHERE task_id = ? AND phase = 6 AND artifact_type = 'full_report'
`).get(taskId) as any;

db.close();
