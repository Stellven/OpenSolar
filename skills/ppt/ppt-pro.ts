#!/usr/bin/env bun
/**
 * PPT Pro - 华为风格专业版
 *
 * 特点：
 * - 高密度内容布局
 * - 多区块网格系统
 * - CSS 数据可视化（进度条、柱状图、饼图）
 * - 图标系统
 * - 专业配色
 */

import * as fs from "fs";
import * as path from "path";

// ==================== 配置 ====================

const CONFIG = {
  colors: {
    primary: "#C7000B",      // 华为红
    secondary: "#0052D9",    // 科技蓝
    accent: "#F5A623",       // 金色强调
    success: "#00A854",      // 成功绿
    warning: "#FA8C16",      // 警告橙
    dark: "#1A1A1A",         // 深色
    gray: "#666666",         // 灰色
    lightGray: "#F5F7FA",    // 浅灰背景
    border: "#E0E0E0",       // 边框
  }
};

// ==================== 类型定义 ====================

interface Block {
  type: string;
  data: any;
  span?: number;  // 占几列
}

interface Slide {
  title: string;
  subtitle?: string;
  blocks: Block[];
  type: "title" | "content" | "section";
  layout?: string;  // "1" | "2" | "3" | "1-2" | "2-1" 等
  footer?: string;
  pageNum?: number;
}

interface Metadata {
  title: string;
  author?: string;
  date?: string;
  company?: string;
}

// ==================== 解析器 ====================

function parseMarkdown(content: string): { slides: Slide[]; metadata: Metadata } {
  const lines = content.split("\n");
  const slides: Slide[] = [];
  let metadata: Metadata = { title: "" };
  let currentSlide: Slide | null = null;
  let inFrontmatter = false;
  let frontmatterLines: string[] = [];
  let inBlock = "";
  let blockLines: string[] = [];
  let blockParams: any = {};

  function flushBlock() {
    if (inBlock && currentSlide && blockLines.length > 0) {
      const block = parseBlock(inBlock, blockLines, blockParams);
      if (block) currentSlide.blocks.push(block);
    }
    inBlock = "";
    blockLines = [];
    blockParams = {};
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Frontmatter
    if (i === 0 && line.trim() === "---") {
      inFrontmatter = true;
      continue;
    }
    if (inFrontmatter) {
      if (line.trim() === "---") {
        inFrontmatter = false;
        for (const fl of frontmatterLines) {
          const [key, ...vals] = fl.split(":");
          const value = vals.join(":").trim();
          const k = key.trim().toLowerCase();
          if (k === "title") metadata.title = value;
          if (k === "author") metadata.author = value;
          if (k === "date") metadata.date = value;
          if (k === "company") metadata.company = value;
        }
        continue;
      }
      frontmatterLines.push(line);
      continue;
    }

    // 块开始 ::: 或 ```
    if (line.trim().startsWith(":::") || line.trim().startsWith("```")) {
      const isCode = line.trim().startsWith("```");
      const marker = isCode ? "```" : ":::";
      const rest = line.trim().slice(marker.length).trim();

      if (rest && !inBlock) {
        // 开始新块
        flushBlock();
        const parts = rest.split(/\s+/);
        inBlock = isCode ? "code:" + parts[0] : parts[0];
        // 解析参数 key=value
        for (let j = 1; j < parts.length; j++) {
          const [k, v] = parts[j].split("=");
          if (k && v) blockParams[k] = v;
        }
        continue;
      } else if (inBlock) {
        // 结束块
        flushBlock();
        continue;
      }
    }

    if (inBlock) {
      blockLines.push(line);
      continue;
    }

    // 分页符
    if (line.trim() === "---" && !inFrontmatter) {
      flushBlock();
      if (currentSlide) {
        slides.push(currentSlide);
        currentSlide = null;
      }
      continue;
    }

    // # 主标题
    if (line.startsWith("# ") && !line.startsWith("## ")) {
      flushBlock();
      if (currentSlide) slides.push(currentSlide);
      const title = line.replace(/^#\s+/, "").trim();
      if (!metadata.title) metadata.title = title;
      currentSlide = { title, blocks: [], type: "title" };
      continue;
    }

    // ## 章节
    if (line.startsWith("## ")) {
      flushBlock();
      if (currentSlide) slides.push(currentSlide);
      currentSlide = {
        title: line.replace(/^##\s+/, "").trim(),
        blocks: [],
        type: "section",
      };
      continue;
    }

    // ### 内容页
    if (line.startsWith("### ")) {
      flushBlock();
      if (currentSlide) slides.push(currentSlide);
      currentSlide = {
        title: line.replace(/^###\s+/, "").trim(),
        blocks: [],
        type: "content",
      };
      continue;
    }

    // @layout 指令
    if (line.trim().startsWith("@layout")) {
      if (currentSlide) {
        currentSlide.layout = line.trim().split(/\s+/)[1] || "1";
      }
      continue;
    }

    // @footer 指令
    if (line.trim().startsWith("@footer")) {
      if (currentSlide) {
        currentSlide.footer = line.trim().replace(/^@footer\s*/, "");
      }
      continue;
    }

    // 普通内容 - 自动识别类型
    if (line.trim() && currentSlide) {
      // 表格
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        const tableLines: string[] = [line];
        let j = i + 1;
        while (j < lines.length && lines[j].trim().startsWith("|")) {
          tableLines.push(lines[j]);
          j++;
        }
        i = j - 1;
        currentSlide.blocks.push(parseBlock("table", tableLines, {}));
        continue;
      }

      // 列表
      if (line.match(/^[\-\*\+]\s+/) || line.match(/^\d+\.\s+/)) {
        const listLines: string[] = [line];
        let j = i + 1;
        while (j < lines.length && (lines[j].match(/^[\s]*[\-\*\+]\s+/) || lines[j].match(/^[\s]*\d+\.\s+/) || lines[j].match(/^\s+\S/))) {
          listLines.push(lines[j]);
          j++;
        }
        i = j - 1;
        currentSlide.blocks.push(parseBlock("list", listLines, {}));
        continue;
      }

      // 引用
      if (line.startsWith(">")) {
        const quoteLines: string[] = [line];
        let j = i + 1;
        while (j < lines.length && lines[j].startsWith(">")) {
          quoteLines.push(lines[j]);
          j++;
        }
        i = j - 1;
        currentSlide.blocks.push(parseBlock("quote", quoteLines, {}));
        continue;
      }

      // 普通段落
      currentSlide.blocks.push({
        type: "text",
        data: { content: line.trim() }
      });
    }
  }

  flushBlock();
  if (currentSlide) slides.push(currentSlide);

  return { slides, metadata };
}

function parseBlock(type: string, lines: string[], params: any): Block {
  switch (type) {
    case "metrics":
    case "kpi":
      return { type: "metrics", data: parseMetrics(lines), span: params.span ? parseInt(params.span) : undefined };

    case "chart":
    case "bar":
      return { type: "bar-chart", data: parseBarChart(lines), span: params.span ? parseInt(params.span) : undefined };

    case "progress":
      return { type: "progress", data: parseProgress(lines), span: params.span ? parseInt(params.span) : undefined };

    case "timeline":
    case "roadmap":
      return { type: "timeline", data: parseTimeline(lines), span: params.span ? parseInt(params.span) : undefined };

    case "cards":
    case "features":
      return { type: "cards", data: parseCards(lines), span: params.span ? parseInt(params.span) : undefined };

    case "conclusion":
    case "summary":
      return { type: "conclusion", data: { content: lines.join("\n").trim(), style: type }, span: params.span ? parseInt(params.span) : undefined };

    case "suggestion":
    case "recommendation":
      return { type: "suggestion", data: { content: lines.join("\n").trim() }, span: params.span ? parseInt(params.span) : undefined };

    case "comparison":
    case "vs":
      return { type: "comparison", data: parseComparison(lines), span: params.span ? parseInt(params.span) : undefined };

    case "list":
      return { type: "list", data: parseList(lines), span: params.span ? parseInt(params.span) : undefined };

    case "table":
      return { type: "table", data: parseTable(lines), span: params.span ? parseInt(params.span) : undefined };

    case "quote":
      return { type: "quote", data: { content: lines.map(l => l.replace(/^>\s*/, "")).join("\n").trim() } };

    case "code:architecture":
    case "code:diagram":
    case "code:ascii":
      return { type: "diagram", data: { content: lines.join("\n") }, span: params.span ? parseInt(params.span) : undefined };

    default:
      if (type.startsWith("code:")) {
        return { type: "code", data: { lang: type.slice(5), content: lines.join("\n") } };
      }
      return { type: "text", data: { content: lines.join("\n").trim() } };
  }
}

function parseMetrics(lines: string[]): any[] {
  const items: any[] = [];
  for (const line of lines) {
    // 格式: 40% | 成本降低 | ↓ | #00A854
    // 或: - 40%: 成本降低 ↓
    const pipeMatch = line.match(/^\s*([^\|]+)\|([^\|]+)(?:\|([^\|]*))?(?:\|([^\|]*))?/);
    if (pipeMatch) {
      items.push({
        value: pipeMatch[1].trim(),
        label: pipeMatch[2].trim(),
        trend: pipeMatch[3]?.trim() || "",
        color: pipeMatch[4]?.trim() || ""
      });
      continue;
    }
    const match = line.match(/^[\-\*]?\s*\*?\*?([^\:]+)\*?\*?\s*[:\-]\s*(.+)/);
    if (match) {
      const value = match[1].trim().replace(/\*\*/g, "");
      const rest = match[2].trim();
      const trend = rest.includes("↑") ? "up" : rest.includes("↓") ? "down" : "";
      items.push({
        value,
        label: rest.replace(/[↑↓]/g, "").trim(),
        trend
      });
    }
  }
  return items;
}

function parseBarChart(lines: string[]): any[] {
  const items: any[] = [];
  for (const line of lines) {
    // 格式: 产品A | 85 | #C7000B
    // 或: - 产品A: 85%
    const pipeMatch = line.match(/^\s*([^\|]+)\|([^\|]+)(?:\|([^\|]*))?/);
    if (pipeMatch) {
      items.push({
        label: pipeMatch[1].trim(),
        value: parseFloat(pipeMatch[2].trim()) || 0,
        color: pipeMatch[3]?.trim() || ""
      });
      continue;
    }
    const match = line.match(/^[\-\*]?\s*([^:\d]+)[:\s]+(\d+\.?\d*)%?/);
    if (match) {
      items.push({
        label: match[1].trim(),
        value: parseFloat(match[2]) || 0
      });
    }
  }
  return items;
}

function parseProgress(lines: string[]): any[] {
  return parseBarChart(lines);  // 同样格式
}

function parseTimeline(lines: string[]): any[] {
  const items: any[] = [];
  let current: any = null;

  for (const line of lines) {
    // 主节点: - 2024-Q1: 标题
    const mainMatch = line.match(/^[\-\*]\s*(\d{4}(?:[-\/]Q?\d{1,2})?)\s*[:\-]\s*(.+)/);
    if (mainMatch) {
      if (current) items.push(current);
      current = {
        time: mainMatch[1],
        title: mainMatch[2].trim(),
        details: []
      };
      continue;
    }
    // 子项: - 详细说明
    const subMatch = line.match(/^\s+[\-\*]\s*(.+)/);
    if (subMatch && current) {
      current.details.push(subMatch[1].trim());
    }
  }
  if (current) items.push(current);
  return items;
}

function parseCards(lines: string[]): any[] {
  const items: any[] = [];
  let current: any = null;

  for (const line of lines) {
    // 卡片标题: - 🚀 标题
    const titleMatch = line.match(/^[\-\*]\s*([\u{1F300}-\u{1F9FF}]|[^\s])\s*(.+)/u);
    if (titleMatch && !line.match(/^\s+/)) {
      if (current) items.push(current);
      current = {
        icon: titleMatch[1],
        title: titleMatch[2].trim(),
        desc: ""
      };
      continue;
    }
    // 卡片描述
    if (line.trim() && current && line.match(/^\s+/)) {
      current.desc += (current.desc ? " " : "") + line.trim();
    }
  }
  if (current) items.push(current);
  return items;
}

function parseComparison(lines: string[]): any {
  const before: string[] = [];
  const after: string[] = [];
  let section = "before";

  for (const line of lines) {
    if (line.toLowerCase().includes("before") || line.includes("优化前") || line.includes("改进前")) {
      section = "before";
      continue;
    }
    if (line.toLowerCase().includes("after") || line.includes("优化后") || line.includes("改进后")) {
      section = "after";
      continue;
    }
    const match = line.match(/^[\-\*]\s*(.+)/);
    if (match) {
      if (section === "before") before.push(match[1].trim());
      else after.push(match[1].trim());
    }
  }
  return { before, after };
}

function parseList(lines: string[]): any[] {
  const items: any[] = [];
  for (const line of lines) {
    const match = line.match(/^(\s*)([\-\*\+]|\d+\.)\s+(.+)/);
    if (match) {
      const indent = match[1].length;
      const level = Math.floor(indent / 2);
      items.push({
        text: match[3].trim(),
        level
      });
    }
  }
  return items;
}

function parseTable(lines: string[]): { headers: string[]; rows: string[][]; alignments?: string[] } {
  const headers: string[] = [];
  const rows: string[][] = [];
  let alignments: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const cells = lines[i].split("|").map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1 || c);

    if (i === 0) {
      headers.push(...cells);
    } else if (i === 1 && lines[i].includes("-")) {
      // 对齐行
      alignments = cells.map(c => {
        if (c.startsWith(":") && c.endsWith(":")) return "center";
        if (c.endsWith(":")) return "right";
        return "left";
      });
    } else {
      rows.push(cells);
    }
  }
  return { headers, rows, alignments };
}

// ==================== HTML 生成 ====================

function generateHTML(slides: Slide[], metadata: Metadata): string {
  slides.forEach((slide, idx) => { slide.pageNum = idx + 1; });
  const total = slides.length;

  const slidesHTML = slides.map((slide, idx) => {
    if (slide.type === "title") return renderTitleSlide(slide, metadata, idx, total);
    if (slide.type === "section") return renderSectionSlide(slide, idx, total);
    return renderContentSlide(slide, idx, total);
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(metadata.title || "Presentation")}</title>
  <style>${getStyles()}</style>
</head>
<body>
  <div class="progress-bar" id="progress"></div>
  ${slidesHTML}
  <script>${getScript()}</script>
</body>
</html>`;
}

function renderTitleSlide(slide: Slide, metadata: Metadata, idx: number, total: number): string {
  return `
  <div class="slide slide-title" id="slide-${idx + 1}">
    <div class="title-content">
      <h1>${escapeHtml(slide.title)}</h1>
      ${metadata.author || metadata.date ? `
        <div class="title-meta">
          ${metadata.author ? `<span class="author">${escapeHtml(metadata.author)}</span>` : ""}
          ${metadata.date ? `<span class="date">${escapeHtml(metadata.date)}</span>` : ""}
        </div>
      ` : ""}
    </div>
    <div class="title-decoration">
      <div class="dec-line"></div>
      <div class="dec-dot"></div>
    </div>
    <div class="slide-footer">
      <span class="company">${escapeHtml(metadata.company || "")}</span>
      <span class="page-num">${idx + 1} / ${total}</span>
    </div>
  </div>`;
}

function renderSectionSlide(slide: Slide, idx: number, total: number): string {
  return `
  <div class="slide slide-section" id="slide-${idx + 1}">
    <div class="section-content">
      <div class="section-num">${String(idx).padStart(2, "0")}</div>
      <h2>${escapeHtml(slide.title)}</h2>
    </div>
    <div class="slide-footer"><span class="page-num">${idx + 1} / ${total}</span></div>
  </div>`;
}

function renderContentSlide(slide: Slide, idx: number, total: number): string {
  const layout = slide.layout || (slide.blocks.length > 1 ? "auto" : "1");

  return `
  <div class="slide" id="slide-${idx + 1}">
    <div class="slide-header">
      <h2>${escapeHtml(slide.title)}</h2>
      ${slide.subtitle ? `<p class="subtitle">${escapeHtml(slide.subtitle)}</p>` : ""}
    </div>
    <div class="slide-body layout-${layout}">
      ${slide.blocks.map(b => renderBlock(b)).join("\n")}
    </div>
    <div class="slide-footer">
      ${slide.footer ? `<span class="footer-note">${escapeHtml(slide.footer)}</span>` : ""}
      <span class="page-num">${idx + 1} / ${total}</span>
    </div>
  </div>`;
}

function renderBlock(block: Block): string {
  const spanClass = block.span ? `span-${block.span}` : "";

  switch (block.type) {
    case "metrics":
      return `<div class="block block-metrics ${spanClass}">${renderMetrics(block.data)}</div>`;
    case "bar-chart":
      return `<div class="block block-chart ${spanClass}">${renderBarChart(block.data)}</div>`;
    case "progress":
      return `<div class="block block-progress ${spanClass}">${renderProgress(block.data)}</div>`;
    case "timeline":
      return `<div class="block block-timeline ${spanClass}">${renderTimeline(block.data)}</div>`;
    case "cards":
      return `<div class="block block-cards ${spanClass}">${renderCards(block.data)}</div>`;
    case "conclusion":
      return `<div class="block block-conclusion ${spanClass}">${renderConclusion(block.data)}</div>`;
    case "suggestion":
      return `<div class="block block-suggestion ${spanClass}">${renderSuggestion(block.data)}</div>`;
    case "comparison":
      return `<div class="block block-comparison ${spanClass}">${renderComparison(block.data)}</div>`;
    case "list":
      return `<div class="block block-list ${spanClass}">${renderList(block.data)}</div>`;
    case "table":
      return `<div class="block block-table ${spanClass}">${renderTable(block.data)}</div>`;
    case "diagram":
      return `<div class="block block-diagram ${spanClass}"><pre>${escapeHtml(block.data.content)}</pre></div>`;
    case "quote":
      return `<div class="block block-quote ${spanClass}"><blockquote>${formatText(block.data.content)}</blockquote></div>`;
    case "text":
      return `<div class="block block-text ${spanClass}"><p>${formatText(block.data.content)}</p></div>`;
    default:
      return "";
  }
}

function renderMetrics(data: any[]): string {
  return `<div class="metrics-grid">${data.map(m => {
    const trendClass = m.trend === "up" || m.trend === "↑" ? "trend-up" : m.trend === "down" || m.trend === "↓" ? "trend-down" : "";
    const colorStyle = m.color ? `style="color: ${m.color}"` : "";
    return `
      <div class="metric-card ${trendClass}">
        <div class="metric-value" ${colorStyle}>${escapeHtml(m.value)}</div>
        <div class="metric-label">${escapeHtml(m.label)}</div>
        ${m.trend ? `<div class="metric-trend">${m.trend === "up" || m.trend === "↑" ? "↑" : "↓"}</div>` : ""}
      </div>`;
  }).join("")}</div>`;
}

function renderBarChart(data: any[]): string {
  const max = Math.max(...data.map(d => d.value), 100);
  return `<div class="bar-chart">${data.map(d => {
    const width = (d.value / max * 100).toFixed(1);
    const color = d.color || CONFIG.colors.primary;
    return `
      <div class="bar-item">
        <span class="bar-label">${escapeHtml(d.label)}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${width}%; background: ${color}"></div>
        </div>
        <span class="bar-value">${d.value}%</span>
      </div>`;
  }).join("")}</div>`;
}

function renderProgress(data: any[]): string {
  return renderBarChart(data);  // 使用相同渲染
}

function renderTimeline(data: any[]): string {
  return `<div class="timeline">${data.map((item, idx) => `
    <div class="timeline-node">
      <div class="timeline-marker">
        <div class="marker-dot"></div>
        ${idx < data.length - 1 ? '<div class="marker-line"></div>' : ""}
      </div>
      <div class="timeline-content">
        <div class="timeline-time">${escapeHtml(item.time)}</div>
        <div class="timeline-title">${escapeHtml(item.title)}</div>
        ${item.details.length > 0 ? `
          <ul class="timeline-details">
            ${item.details.map((d: string) => `<li>${escapeHtml(d)}</li>`).join("")}
          </ul>
        ` : ""}
      </div>
    </div>
  `).join("")}</div>`;
}

function renderCards(data: any[]): string {
  return `<div class="cards-grid">${data.map(card => `
    <div class="feature-card">
      <div class="card-icon">${card.icon}</div>
      <div class="card-title">${escapeHtml(card.title)}</div>
      ${card.desc ? `<div class="card-desc">${escapeHtml(card.desc)}</div>` : ""}
    </div>
  `).join("")}</div>`;
}

function renderConclusion(data: any): string {
  return `
    <div class="conclusion-box">
      <div class="conclusion-icon">📌</div>
      <div class="conclusion-title">核心结论</div>
      <div class="conclusion-content">${formatText(data.content)}</div>
    </div>`;
}

function renderSuggestion(data: any): string {
  return `
    <div class="suggestion-box">
      <div class="suggestion-icon">💡</div>
      <div class="suggestion-title">建议</div>
      <div class="suggestion-content">${formatText(data.content)}</div>
    </div>`;
}

function renderComparison(data: any): string {
  return `
    <div class="comparison-grid">
      <div class="comparison-col comparison-before">
        <div class="comparison-header">❌ 优化前</div>
        <ul>${data.before.map((item: string) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div class="comparison-col comparison-after">
        <div class="comparison-header">✅ 优化后</div>
        <ul>${data.after.map((item: string) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
    </div>`;
}

function renderList(data: any[]): string {
  return `<ul class="rich-list">${data.map(item => {
    const levelClass = `level-${item.level || 0}`;
    return `<li class="${levelClass}">${formatText(item.text)}</li>`;
  }).join("")}</ul>`;
}

function renderTable(data: any): string {
  const alignStyle = (idx: number) => data.alignments?.[idx] ? `text-align: ${data.alignments[idx]}` : "";
  return `
    <table class="data-table">
      <thead><tr>${data.headers.map((h: string, i: number) => `<th style="${alignStyle(i)}">${formatText(h)}</th>`).join("")}</tr></thead>
      <tbody>${data.rows.map((row: string[]) => `<tr>${row.map((cell: string, i: number) => `<td style="${alignStyle(i)}">${formatText(cell)}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>`;
}

function formatText(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ==================== 样式 ====================

function getStyles(): string {
  return `
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #1a1a1a;
      color: #333;
      line-height: 1.6;
    }

    /* Slide 基础 */
    .slide {
      width: 100vw;
      height: 100vh;
      padding: 40px 60px;
      background: linear-gradient(180deg, #fff 0%, #fafbfc 100%);
      display: none;
      flex-direction: column;
      position: relative;
    }
    .slide.active { display: flex; }

    /* 封面页 */
    .slide-title {
      background: linear-gradient(135deg, ${CONFIG.colors.primary} 0%, #e31937 100%);
      color: white;
      justify-content: center;
      align-items: center;
    }
    .title-content { text-align: center; z-index: 1; }
    .slide-title h1 {
      font-size: 3rem;
      font-weight: 700;
      letter-spacing: 2px;
      margin-bottom: 20px;
    }
    .title-meta { font-size: 1.1rem; opacity: 0.9; }
    .title-meta .author { margin-right: 30px; }
    .title-decoration {
      position: absolute;
      bottom: 100px;
      left: 50%;
      transform: translateX(-50%);
    }
    .dec-line { width: 100px; height: 2px; background: rgba(255,255,255,0.5); }
    .dec-dot { width: 8px; height: 8px; background: white; border-radius: 50%; margin: 10px auto 0; }

    /* 章节页 */
    .slide-section {
      background: linear-gradient(135deg, ${CONFIG.colors.secondary} 0%, #0066ff 100%);
      color: white;
      justify-content: center;
      padding-left: 100px;
    }
    .section-num {
      font-size: 8rem;
      font-weight: 800;
      opacity: 0.1;
      position: absolute;
      right: 80px;
      top: 50%;
      transform: translateY(-50%);
    }
    .slide-section h2 { font-size: 2.5rem; font-weight: 600; }

    /* 内容页 */
    .slide-header {
      margin-bottom: 25px;
      border-bottom: 3px solid ${CONFIG.colors.primary};
      padding-bottom: 15px;
    }
    .slide-header h2 { font-size: 1.7rem; font-weight: 600; color: #333; }
    .slide-header .subtitle { font-size: 1rem; color: #666; margin-top: 5px; }

    .slide-body {
      flex: 1;
      display: grid;
      gap: 20px;
      overflow: hidden;
    }
    .layout-1 { grid-template-columns: 1fr; }
    .layout-2 { grid-template-columns: 1fr 1fr; }
    .layout-3 { grid-template-columns: 1fr 1fr 1fr; }
    .layout-auto { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
    .layout-1-2 { grid-template-columns: 1fr 2fr; }
    .layout-2-1 { grid-template-columns: 2fr 1fr; }

    .block { min-height: 0; overflow: hidden; }
    .span-2 { grid-column: span 2; }
    .span-3 { grid-column: span 3; }

    /* 指标卡片 */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 15px;
    }
    .metric-card {
      background: linear-gradient(135deg, #f8f9fa 0%, #fff 100%);
      border-radius: 10px;
      padding: 20px 15px;
      text-align: center;
      box-shadow: 0 2px 10px rgba(0,0,0,0.06);
      position: relative;
    }
    .metric-value {
      font-size: 2.2rem;
      font-weight: 700;
      color: ${CONFIG.colors.primary};
      line-height: 1.2;
    }
    .metric-label { font-size: 0.9rem; color: #666; margin-top: 8px; }
    .metric-trend {
      position: absolute;
      top: 10px;
      right: 10px;
      font-size: 1rem;
    }
    .metric-card.trend-up .metric-value { color: ${CONFIG.colors.success}; }
    .metric-card.trend-up .metric-trend { color: ${CONFIG.colors.success}; }
    .metric-card.trend-down .metric-value { color: ${CONFIG.colors.primary}; }
    .metric-card.trend-down .metric-trend { color: ${CONFIG.colors.primary}; }

    /* 柱状图 */
    .bar-chart { display: flex; flex-direction: column; gap: 12px; }
    .bar-item { display: flex; align-items: center; gap: 10px; }
    .bar-label { width: 80px; font-size: 0.9rem; color: #333; text-align: right; flex-shrink: 0; }
    .bar-track {
      flex: 1;
      height: 24px;
      background: #f0f2f5;
      border-radius: 4px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 4px;
      transition: width 0.5s ease;
    }
    .bar-value { width: 50px; font-size: 0.9rem; font-weight: 600; color: #333; }

    /* 时间轴 */
    .timeline { display: flex; flex-direction: column; }
    .timeline-node { display: flex; gap: 20px; }
    .timeline-marker {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 20px;
    }
    .marker-dot {
      width: 14px;
      height: 14px;
      background: ${CONFIG.colors.primary};
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 0 0 2px ${CONFIG.colors.primary};
      flex-shrink: 0;
    }
    .marker-line {
      width: 2px;
      flex: 1;
      background: linear-gradient(180deg, ${CONFIG.colors.primary}, ${CONFIG.colors.secondary});
      margin: 5px 0;
    }
    .timeline-content { flex: 1; padding-bottom: 20px; }
    .timeline-time {
      font-size: 0.85rem;
      font-weight: 600;
      color: ${CONFIG.colors.primary};
      margin-bottom: 3px;
    }
    .timeline-title { font-size: 1.1rem; font-weight: 600; color: #333; }
    .timeline-details {
      margin-top: 8px;
      padding-left: 18px;
      font-size: 0.9rem;
      color: #666;
    }
    .timeline-details li { margin: 4px 0; }

    /* 特性卡片 */
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 15px;
    }
    .feature-card {
      background: #fff;
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      padding: 20px;
      transition: box-shadow 0.2s;
    }
    .feature-card:hover { box-shadow: 0 4px 15px rgba(0,0,0,0.08); }
    .card-icon { font-size: 1.8rem; margin-bottom: 10px; }
    .card-title { font-size: 1rem; font-weight: 600; color: #333; margin-bottom: 6px; }
    .card-desc { font-size: 0.85rem; color: #666; line-height: 1.5; }

    /* 结论/建议框 */
    .conclusion-box, .suggestion-box {
      background: linear-gradient(135deg, #fffbe6 0%, #fff 100%);
      border-left: 4px solid ${CONFIG.colors.accent};
      border-radius: 0 8px 8px 0;
      padding: 18px 22px;
      display: flex;
      flex-wrap: wrap;
      align-items: flex-start;
      gap: 12px;
    }
    .suggestion-box {
      background: linear-gradient(135deg, #e6f7ff 0%, #fff 100%);
      border-left-color: ${CONFIG.colors.secondary};
    }
    .conclusion-icon, .suggestion-icon { font-size: 1.3rem; }
    .conclusion-title, .suggestion-title {
      font-size: 1rem;
      font-weight: 600;
      color: #333;
      flex-basis: calc(100% - 40px);
    }
    .conclusion-content, .suggestion-content {
      font-size: 1rem;
      color: #555;
      line-height: 1.7;
      flex-basis: 100%;
    }

    /* 对比 */
    .comparison-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    .comparison-col {
      background: #f8f9fa;
      border-radius: 8px;
      padding: 18px;
    }
    .comparison-before { border-top: 3px solid #ff4d4f; }
    .comparison-after { border-top: 3px solid ${CONFIG.colors.success}; }
    .comparison-header {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 12px;
    }
    .comparison-col ul { padding-left: 20px; }
    .comparison-col li { margin: 8px 0; font-size: 0.95rem; color: #555; }

    /* 列表 */
    .rich-list { list-style: none; padding: 0; }
    .rich-list li {
      font-size: 1.1rem;
      line-height: 1.6;
      margin: 10px 0;
      padding-left: 28px;
      position: relative;
      color: #444;
    }
    .rich-list li::before {
      content: "";
      position: absolute;
      left: 0;
      top: 8px;
      width: 8px;
      height: 8px;
      background: ${CONFIG.colors.primary};
      border-radius: 2px;
    }
    .rich-list li.level-1 { padding-left: 50px; font-size: 1rem; color: #666; }
    .rich-list li.level-1::before { left: 28px; width: 6px; height: 6px; background: ${CONFIG.colors.secondary}; border-radius: 50%; }

    /* 表格 */
    .data-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    .data-table th {
      background: ${CONFIG.colors.primary};
      color: white;
      padding: 12px 15px;
      font-weight: 600;
      text-align: left;
    }
    .data-table td { padding: 10px 15px; border-bottom: 1px solid #e8e8e8; }
    .data-table tr:nth-child(even) { background: #fafbfc; }
    .data-table tr:hover { background: #f0f4f8; }

    /* 架构图 */
    .block-diagram pre {
      background: #f5f7fa;
      border: 1px solid #e0e0e0;
      border-radius: 6px;
      padding: 15px;
      font-family: "SF Mono", "Fira Code", monospace;
      font-size: 0.8rem;
      line-height: 1.3;
      overflow-x: auto;
    }

    /* 引用 */
    .block-quote blockquote {
      font-size: 1.1rem;
      font-style: italic;
      color: #555;
      padding: 15px 25px;
      border-left: 4px solid ${CONFIG.colors.secondary};
      background: #f8f9fa;
    }

    /* 页脚 */
    .slide-footer {
      position: absolute;
      bottom: 20px;
      left: 60px;
      right: 60px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      color: #999;
    }
    .slide-title .slide-footer, .slide-section .slide-footer {
      color: rgba(255,255,255,0.6);
    }
    .footer-note { font-style: italic; }

    /* 进度条 */
    .progress-bar {
      position: fixed;
      top: 0;
      left: 0;
      height: 3px;
      background: ${CONFIG.colors.primary};
      z-index: 1000;
      transition: width 0.3s;
    }

    @media print {
      .slide { display: flex !important; page-break-after: always; }
      .progress-bar { display: none; }
    }
  `;
}

function getScript(): string {
  return `
    (function() {
      const slides = document.querySelectorAll('.slide');
      const progress = document.getElementById('progress');
      let current = 0;

      function showSlide(n) {
        current = Math.max(0, Math.min(n, slides.length - 1));
        slides.forEach((s, i) => s.classList.toggle('active', i === current));
        progress.style.width = ((current + 1) / slides.length * 100) + '%';
        location.hash = 'slide-' + (current + 1);
      }

      document.addEventListener('keydown', (e) => {
        switch(e.key) {
          case 'ArrowRight': case 'ArrowDown': case ' ': case 'PageDown':
            showSlide(current + 1); e.preventDefault(); break;
          case 'ArrowLeft': case 'ArrowUp': case 'PageUp':
            showSlide(current - 1); e.preventDefault(); break;
          case 'Home': showSlide(0); break;
          case 'End': showSlide(slides.length - 1); break;
          case 'f': case 'F': document.documentElement.requestFullscreen?.(); break;
          case 'p': case 'P': window.print(); break;
          case 'g': case 'G':
            const p = prompt('页码 (1-' + slides.length + '):');
            if (p) showSlide(parseInt(p) - 1);
            break;
        }
      });

      // 双击导航，避免误触
      document.addEventListener('dblclick', (e) => {
        if (e.target.closest('a,button,input')) return;
        e.clientX > window.innerWidth / 2 ? showSlide(current + 1) : showSlide(current - 1);
      });

      const hash = location.hash.match(/slide-(\\d+)/);
      showSlide(hash ? parseInt(hash[1]) - 1 : 0);
    })();
  `;
}

// ==================== 主程序 ====================

async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args.includes("-h") || args.includes("--help")) {
    console.log(`
PPT Pro - 华为风格专业版

Usage: bun run ppt-pro.ts <input.md> [output.html]

语法:
  # 标题            封面页
  ## 章节           章节页
  ### 内容页标题    内容页
  @layout 2         2列布局 (1/2/3/auto/1-2/2-1)
  @footer 来源说明  页脚注释

区块:
  :::metrics        关键指标
  :::chart/bar      柱状图
  :::timeline       时间轴
  :::cards          特性卡片
  :::conclusion     结论框
  :::suggestion     建议框
  :::comparison     对比框
  \`\`\`architecture  架构图
`);
    return;
  }

  const input = args[0];
  const output = args[1] || input.replace(/\.md$/, ".html");

  if (!fs.existsSync(input)) {
    console.error("File not found:", input);
    return;
  }

  const content = fs.readFileSync(input, "utf-8");
  const { slides, metadata } = parseMarkdown(content);
  const html = generateHTML(slides, metadata);
  fs.writeFileSync(output, html);

  console.log(`
┌─ ✅ PPT Pro Generated ──────────────────────────┐
│  Input    ${input.slice(-42).padEnd(42)}│
│  Output   ${output.slice(-42).padEnd(42)}│
│  Slides   ${String(slides.length).padEnd(42)}│
└─────────────────────────────────────────────────┘
`);
}

main();
