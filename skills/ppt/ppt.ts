#!/usr/bin/env bun
/**
 * PPT Skill v2 - Markdown to Huawei-style HTML Presentation
 *
 * 华为风格增强版：
 * - 表格支持
 * - 架构图 (代码块)
 * - 多栏布局 (:::columns)
 * - 关键数字突出 (**数字**)
 * - 结论/建议框 (:::conclusion / :::suggestion)
 * - 二级列表
 * - 路标/时间轴
 */

import * as fs from "fs";
import * as path from "path";

// ==================== 配置 ====================

const CONFIG = {
  maxPointsPerSlide: 6,
  stateFile: ".solar/ppt-state.json",
  colors: {
    huaweiRed: "#C7000B",
    huaweiBlue: "#0052D9",
    huaweiGray: "#333333",
    huaweiLightGray: "#666666",
    accentGold: "#F5A623",
    bgLight: "#FFFFFF",
    bgSection: "#F8F9FA",
  },
};

// ==================== 类型定义 ====================

interface SlideContent {
  type: "text" | "list" | "table" | "code" | "columns" | "metrics" | "conclusion" | "timeline" | "quote";
  data: any;
}

interface Slide {
  title: string;
  subtitle?: string;
  contents: SlideContent[];
  type: "title" | "content" | "section" | "summary";
  layout?: "default" | "two-column" | "metrics" | "timeline";
  pageNum?: number;
}

interface TaskState {
  inputFile: string;
  outputFile: string;
  totalSlides: number;
  processedSlides: number;
  status: "pending" | "processing" | "completed" | "error";
  startedAt: string;
  updatedAt: string;
  error?: string;
}

interface ParseResult {
  slides: Slide[];
  metadata: {
    title: string;
    author?: string;
    date?: string;
    theme?: string;
  };
}

// ==================== MD 解析器 (增强版) ====================

function parseMarkdown(content: string): ParseResult {
  const lines = content.split("\n");
  const slides: Slide[] = [];
  let metadata: any = { title: "" };
  let currentSlide: Slide | null = null;
  let inFrontmatter = false;
  let inCodeBlock = false;
  let inSpecialBlock = "";  // columns, conclusion, suggestion, timeline
  let codeBlockContent: string[] = [];
  let codeBlockLang = "";
  let specialBlockContent: string[] = [];
  let frontmatterLines: string[] = [];
  let currentList: { level: number; items: any[] }[] = [];

  function flushList() {
    if (currentList.length > 0 && currentSlide) {
      const rootItems = buildNestedList(currentList);
      currentSlide.contents.push({ type: "list", data: rootItems });
      currentList = [];
    }
  }

  function buildNestedList(list: { level: number; items: any[] }[]): any[] {
    // 简化：直接返回扁平结构，保留缩进信息
    return list.map(item => ({
      text: item.items[0],
      level: item.level,
      children: item.items.slice(1)
    }));
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
          if (k === "theme") metadata.theme = value;
        }
        continue;
      }
      frontmatterLines.push(line);
      continue;
    }

    // 代码块
    if (line.trim().startsWith("```")) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeBlockLang = line.trim().slice(3).trim();
        codeBlockContent = [];
      } else {
        inCodeBlock = false;
        if (currentSlide) {
          currentSlide.contents.push({
            type: "code",
            data: { lang: codeBlockLang, content: codeBlockContent.join("\n") }
          });
        }
      }
      continue;
    }
    if (inCodeBlock) {
      codeBlockContent.push(line);
      continue;
    }

    // 特殊块 :::columns, :::conclusion, :::suggestion, :::timeline, :::metrics
    if (line.trim().startsWith(":::")) {
      const blockType = line.trim().slice(3).trim().toLowerCase();
      if (blockType && !inSpecialBlock) {
        flushList();
        inSpecialBlock = blockType;
        specialBlockContent = [];
        continue;
      } else if (!blockType || blockType === "end") {
        // 结束特殊块
        if (currentSlide && inSpecialBlock) {
          if (inSpecialBlock === "columns") {
            currentSlide.contents.push({
              type: "columns",
              data: parseColumns(specialBlockContent.join("\n"))
            });
            currentSlide.layout = "two-column";
          } else if (inSpecialBlock === "conclusion" || inSpecialBlock === "suggestion") {
            currentSlide.contents.push({
              type: "conclusion",
              data: { type: inSpecialBlock, content: specialBlockContent.join("\n").trim() }
            });
          } else if (inSpecialBlock === "timeline") {
            currentSlide.contents.push({
              type: "timeline",
              data: parseTimeline(specialBlockContent)
            });
          } else if (inSpecialBlock === "metrics") {
            currentSlide.contents.push({
              type: "metrics",
              data: parseMetrics(specialBlockContent)
            });
            currentSlide.layout = "metrics";
          }
        }
        inSpecialBlock = "";
        continue;
      }
    }
    if (inSpecialBlock) {
      specialBlockContent.push(line);
      continue;
    }

    // 分页符 ---
    if (line.trim() === "---") {
      flushList();
      if (currentSlide) {
        slides.push(currentSlide);
        currentSlide = null;
      }
      continue;
    }

    // # 主标题 (封面页)
    if (line.startsWith("# ") && !line.startsWith("## ")) {
      flushList();
      if (currentSlide) slides.push(currentSlide);
      const title = line.replace(/^#\s+/, "").trim();
      if (!metadata.title) metadata.title = title;
      currentSlide = { title, contents: [], type: "title" };
      continue;
    }

    // ## 章节标题 (新页)
    if (line.startsWith("## ")) {
      flushList();
      if (currentSlide) slides.push(currentSlide);
      currentSlide = {
        title: line.replace(/^##\s+/, "").trim(),
        contents: [],
        type: "section",
      };
      continue;
    }

    // ### 子标题 (内容页标题)
    if (line.startsWith("### ")) {
      flushList();
      if (currentSlide && currentSlide.type !== "title" && currentSlide.type !== "section") {
        if (currentSlide.contents.length > 0) {
          slides.push(currentSlide);
        }
      }
      if (currentSlide?.type === "section") {
        slides.push(currentSlide);
      }
      currentSlide = {
        title: line.replace(/^###\s+/, "").trim(),
        contents: [],
        type: "content",
      };
      continue;
    }

    // #### 更小的标题 → 作为内容区块标题
    if (line.startsWith("#### ")) {
      flushList();
      if (!currentSlide) {
        currentSlide = { title: "", contents: [], type: "content" };
      }
      currentSlide.contents.push({
        type: "text",
        data: { tag: "h4", content: line.replace(/^####\s+/, "").trim() }
      });
      continue;
    }

    // 表格
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      flushList();
      const tableLines: string[] = [line];
      let j = i + 1;
      while (j < lines.length && lines[j].trim().startsWith("|")) {
        tableLines.push(lines[j]);
        j++;
      }
      i = j - 1;
      if (currentSlide) {
        currentSlide.contents.push({
          type: "table",
          data: parseTable(tableLines)
        });
      }
      continue;
    }

    // 引用块 >
    if (line.startsWith("> ")) {
      flushList();
      const quoteLines: string[] = [line.slice(2)];
      let j = i + 1;
      while (j < lines.length && lines[j].startsWith("> ")) {
        quoteLines.push(lines[j].slice(2));
        j++;
      }
      i = j - 1;
      if (!currentSlide) {
        currentSlide = { title: "", contents: [], type: "content" };
      }
      currentSlide.contents.push({
        type: "quote",
        data: quoteLines.join("\n")
      });
      continue;
    }

    // 列表项 (支持多级)
    const listMatch = line.match(/^(\s*)([\-\*\+]|\d+\.)\s+(.+)/);
    if (listMatch) {
      if (!currentSlide) {
        currentSlide = { title: "", contents: [], type: "content" };
      }
      if (currentSlide.type === "section" || currentSlide.type === "title") {
        const sectionTitle = currentSlide.title;
        slides.push(currentSlide);
        currentSlide = { title: sectionTitle, contents: [], type: "content" };
      }
      const indent = listMatch[1].length;
      const level = Math.floor(indent / 2);
      const text = listMatch[3].trim();
      currentList.push({ level, items: [text] });
      continue;
    }

    // 普通文本段落
    if (line.trim()) {
      flushList();
      if (!currentSlide) {
        currentSlide = { title: "", contents: [], type: "content" };
      }
      // 检查是否是关键数字 (如 **40%** 降低成本)
      if (line.match(/\*\*[\d\.%+\-]+\*\*/)) {
        currentSlide.contents.push({
          type: "metrics",
          data: parseInlineMetrics(line)
        });
      } else {
        currentSlide.contents.push({
          type: "text",
          data: { tag: "p", content: line.trim() }
        });
      }
    }
  }

  flushList();
  if (currentSlide) slides.push(currentSlide);

  return { slides, metadata };
}

// ==================== 辅助解析函数 ====================

function parseTable(lines: string[]): { headers: string[]; rows: string[][] } {
  const headers: string[] = [];
  const rows: string[][] = [];

  for (let i = 0; i < lines.length; i++) {
    const cells = lines[i].split("|").map(c => c.trim()).filter(c => c);
    if (i === 0) {
      headers.push(...cells);
    } else if (i === 1 && lines[i].includes("---")) {
      continue; // 分隔行
    } else {
      rows.push(cells);
    }
  }
  return { headers, rows };
}

function parseColumns(content: string): { left: string; right: string } {
  const parts = content.split(/\|\|\||\-\-\-/);
  return {
    left: parts[0]?.trim() || "",
    right: parts[1]?.trim() || ""
  };
}

function parseTimeline(lines: string[]): { year: string; title: string; desc?: string }[] {
  const items: { year: string; title: string; desc?: string }[] = [];
  for (const line of lines) {
    const match = line.match(/^[\-\*]?\s*(\d{4}(?:[-\/Q]\d{1,2})?)\s*[:\-]\s*(.+)/);
    if (match) {
      const [, year, rest] = match;
      const [title, desc] = rest.split(/[:\-]/).map(s => s.trim());
      items.push({ year, title, desc });
    }
  }
  return items;
}

function parseMetrics(lines: string[]): { value: string; label: string; trend?: string }[] {
  const items: { value: string; label: string; trend?: string }[] = [];
  for (const line of lines) {
    const match = line.match(/^[\-\*]?\s*\*?\*?([\d\.%+\-]+[KMB]?)\*?\*?\s*[:\-]?\s*(.+)/);
    if (match) {
      const [, value, label] = match;
      const trend = label.includes("↑") ? "up" : label.includes("↓") ? "down" : undefined;
      items.push({ value, label: label.replace(/[↑↓]/g, "").trim(), trend });
    }
  }
  return items;
}

function parseInlineMetrics(line: string): { value: string; label: string; trend?: string }[] {
  const items: { value: string; label: string; trend?: string }[] = [];
  const matches = line.matchAll(/\*\*([\d\.%+\-]+[KMB]?)\*\*\s*([^*]+?)(?=\*\*|$)/g);
  for (const match of matches) {
    const value = match[1];
    const label = match[2].trim();
    const trend = label.includes("↑") ? "up" : label.includes("↓") ? "down" : undefined;
    items.push({ value, label: label.replace(/[↑↓]/g, "").trim(), trend });
  }
  if (items.length === 0) {
    // 单个数字的情况
    const single = line.match(/\*\*([\d\.%+\-]+[KMB]?)\*\*/);
    if (single) {
      items.push({ value: single[1], label: line.replace(/\*\*[\d\.%+\-]+[KMB]?\*\*/, "").trim() });
    }
  }
  return items;
}

// ==================== HTML 生成 (华为风格增强版) ====================

function generateHTML(result: ParseResult): string {
  const { slides, metadata } = result;

  // 添加页码
  slides.forEach((slide, idx) => {
    slide.pageNum = idx + 1;
  });

  const totalSlides = slides.length;

  const slidesHTML = slides.map((slide, idx) => {
    if (slide.type === "title") {
      return generateTitleSlide(slide, idx, totalSlides, metadata);
    }
    if (slide.type === "section") {
      return generateSectionSlide(slide, idx, totalSlides);
    }
    return generateContentSlide(slide, idx, totalSlides);
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(metadata.title || "Presentation")}</title>
  <style>
    ${getStyles()}
  </style>
</head>
<body>
  <div class="progress-bar" id="progress"></div>
  <div class="help-tip" id="help">← → 翻页 | F 全屏 | P 打印 | G 跳页</div>

  ${slidesHTML}

  <script>
    ${getScript()}
  </script>
</body>
</html>`;
}

function generateTitleSlide(slide: Slide, idx: number, total: number, metadata: any): string {
  return `
    <div class="slide slide-title" id="slide-${idx + 1}">
      <div class="slide-content">
        <h1>${escapeHtml(slide.title)}</h1>
        ${metadata.author ? `<p class="author">${escapeHtml(metadata.author)}</p>` : ""}
        ${metadata.date ? `<p class="date">${escapeHtml(metadata.date)}</p>` : ""}
      </div>
      <div class="slide-footer">
        <div class="footer-logo">HUAWEI STYLE</div>
        <span class="page-num">${idx + 1} / ${total}</span>
      </div>
    </div>`;
}

function generateSectionSlide(slide: Slide, idx: number, total: number): string {
  return `
    <div class="slide slide-section" id="slide-${idx + 1}">
      <div class="slide-content">
        <div class="section-number">${String(idx).padStart(2, "0")}</div>
        <h2>${escapeHtml(slide.title)}</h2>
      </div>
      <div class="slide-footer">
        <span class="page-num">${idx + 1} / ${total}</span>
      </div>
    </div>`;
}

function generateContentSlide(slide: Slide, idx: number, total: number): string {
  const layoutClass = slide.layout ? `layout-${slide.layout}` : "";

  return `
    <div class="slide ${layoutClass}" id="slide-${idx + 1}">
      <div class="slide-header">
        <h2>${escapeHtml(slide.title)}</h2>
        ${slide.subtitle ? `<h3>${escapeHtml(slide.subtitle)}</h3>` : ""}
      </div>
      <div class="slide-body">
        ${slide.contents.map(c => renderContent(c)).join("\n")}
      </div>
      <div class="slide-footer">
        <span class="page-num">${idx + 1} / ${total}</span>
      </div>
    </div>`;
}

function renderContent(content: SlideContent): string {
  switch (content.type) {
    case "text":
      return `<${content.data.tag} class="text-block">${formatText(content.data.content)}</${content.data.tag}>`;

    case "list":
      return renderList(content.data);

    case "table":
      return renderTable(content.data);

    case "code":
      return renderCode(content.data);

    case "columns":
      return renderColumns(content.data);

    case "metrics":
      return renderMetrics(content.data);

    case "conclusion":
      return renderConclusion(content.data);

    case "timeline":
      return renderTimeline(content.data);

    case "quote":
      return `<blockquote class="quote-block">${formatText(content.data)}</blockquote>`;

    default:
      return "";
  }
}

function renderList(items: any[]): string {
  const listItems = items.map(item => {
    const levelClass = `level-${item.level || 0}`;
    return `<li class="${levelClass}">${formatText(item.text)}</li>`;
  }).join("\n");
  return `<ul class="content-list">${listItems}</ul>`;
}

function renderTable(data: { headers: string[]; rows: string[][] }): string {
  const headerCells = data.headers.map(h => `<th>${formatText(h)}</th>`).join("");
  const bodyRows = data.rows.map(row =>
    `<tr>${row.map(cell => `<td>${formatText(cell)}</td>`).join("")}</tr>`
  ).join("\n");

  return `
    <div class="table-container">
      <table class="data-table">
        <thead><tr>${headerCells}</tr></thead>
        <tbody>${bodyRows}</tbody>
      </table>
    </div>`;
}

function renderCode(data: { lang: string; content: string }): string {
  // 如果是 ASCII 图或架构图，使用特殊样式
  const isAsciiArt = data.lang === "ascii" || data.lang === "diagram" || data.lang === "architecture" ||
                    data.content.includes("┌") || data.content.includes("╔") || data.content.includes("+--");

  const className = isAsciiArt ? "ascii-diagram" : "code-block";
  return `<pre class="${className}"><code>${escapeHtml(data.content)}</code></pre>`;
}

function renderColumns(data: { left: string; right: string }): string {
  return `
    <div class="two-columns">
      <div class="column column-left">
        ${formatText(data.left).split("\n").map(p => `<p>${p}</p>`).join("")}
      </div>
      <div class="column column-right">
        ${formatText(data.right).split("\n").map(p => `<p>${p}</p>`).join("")}
      </div>
    </div>`;
}

function renderMetrics(data: { value: string; label: string; trend?: string }[]): string {
  const items = data.map(m => {
    const trendClass = m.trend === "up" ? "trend-up" : m.trend === "down" ? "trend-down" : "";
    const trendIcon = m.trend === "up" ? "↑" : m.trend === "down" ? "↓" : "";
    return `
      <div class="metric-item ${trendClass}">
        <div class="metric-value">${escapeHtml(m.value)}${trendIcon ? `<span class="trend-icon">${trendIcon}</span>` : ""}</div>
        <div class="metric-label">${escapeHtml(m.label)}</div>
      </div>`;
  }).join("\n");

  return `<div class="metrics-grid">${items}</div>`;
}

function renderConclusion(data: { type: string; content: string }): string {
  const icon = data.type === "suggestion" ? "💡" : "📌";
  const title = data.type === "suggestion" ? "建议" : "结论";
  return `
    <div class="conclusion-box ${data.type}">
      <div class="conclusion-header">${icon} ${title}</div>
      <div class="conclusion-content">${formatText(data.content)}</div>
    </div>`;
}

function renderTimeline(data: { year: string; title: string; desc?: string }[]): string {
  const items = data.map((item, idx) => `
    <div class="timeline-item">
      <div class="timeline-dot"></div>
      <div class="timeline-year">${escapeHtml(item.year)}</div>
      <div class="timeline-content">
        <div class="timeline-title">${escapeHtml(item.title)}</div>
        ${item.desc ? `<div class="timeline-desc">${escapeHtml(item.desc)}</div>` : ""}
      </div>
    </div>
  `).join("\n");

  return `<div class="timeline-container">${items}</div>`;
}

function formatText(text: string): string {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ==================== CSS 样式 ====================

function getStyles(): string {
  return `
    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
      background: #1a1a1a;
      color: #333;
      line-height: 1.6;
    }

    /* 基础 Slide */
    .slide {
      width: 100vw;
      height: 100vh;
      padding: 50px 70px;
      background: linear-gradient(180deg, #FFFFFF 0%, #FAFBFC 100%);
      display: none;
      flex-direction: column;
      position: relative;
      page-break-after: always;
    }
    .slide.active { display: flex; }

    /* 封面页 */
    .slide-title {
      background: linear-gradient(135deg, ${CONFIG.colors.huaweiRed} 0%, #E31937 100%);
      color: white;
      justify-content: center;
      align-items: center;
      text-align: center;
    }
    .slide-title h1 {
      font-size: 3.2rem;
      font-weight: 700;
      letter-spacing: 3px;
      margin-bottom: 30px;
      text-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .slide-title .author { font-size: 1.3rem; opacity: 0.95; margin: 8px 0; }
    .slide-title .date { font-size: 1.1rem; opacity: 0.8; }
    .slide-title .footer-logo {
      position: absolute;
      bottom: 30px;
      left: 70px;
      font-size: 0.9rem;
      font-weight: 600;
      letter-spacing: 2px;
      opacity: 0.7;
    }

    /* 章节页 */
    .slide-section {
      background: linear-gradient(135deg, ${CONFIG.colors.huaweiBlue} 0%, #0066FF 100%);
      color: white;
      justify-content: center;
      align-items: flex-start;
      padding-left: 120px;
    }
    .slide-section .section-number {
      font-size: 6rem;
      font-weight: 800;
      opacity: 0.15;
      position: absolute;
      right: 100px;
      top: 50%;
      transform: translateY(-50%);
    }
    .slide-section h2 {
      font-size: 2.8rem;
      font-weight: 600;
      letter-spacing: 2px;
    }

    /* 内容页 Header */
    .slide-header {
      margin-bottom: 30px;
      padding-bottom: 20px;
      border-bottom: 3px solid ${CONFIG.colors.huaweiRed};
    }
    .slide-header h2 {
      font-size: 1.9rem;
      font-weight: 600;
      color: ${CONFIG.colors.huaweiGray};
    }
    .slide-header h3 {
      font-size: 1.1rem;
      color: ${CONFIG.colors.huaweiLightGray};
      margin-top: 8px;
      font-weight: 400;
    }

    /* 内容区 */
    .slide-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 20px;
      overflow: hidden;
    }

    /* 列表 */
    .content-list {
      list-style: none;
      padding: 0;
    }
    .content-list li {
      font-size: 1.35rem;
      line-height: 1.7;
      margin: 14px 0;
      padding-left: 35px;
      position: relative;
      color: #444;
    }
    .content-list li::before {
      content: "";
      position: absolute;
      left: 0;
      top: 10px;
      width: 10px;
      height: 10px;
      background: ${CONFIG.colors.huaweiRed};
      border-radius: 2px;
    }
    .content-list li.level-1 {
      padding-left: 60px;
      font-size: 1.15rem;
      color: #666;
    }
    .content-list li.level-1::before {
      left: 35px;
      width: 6px;
      height: 6px;
      background: ${CONFIG.colors.huaweiBlue};
      border-radius: 50%;
    }
    .content-list li.level-2 {
      padding-left: 85px;
      font-size: 1rem;
      color: #888;
    }
    .content-list li.level-2::before {
      left: 65px;
      width: 4px;
      height: 4px;
      background: #999;
      border-radius: 50%;
    }

    /* 表格 */
    .table-container {
      overflow-x: auto;
      margin: 15px 0;
    }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 1.1rem;
    }
    .data-table th {
      background: ${CONFIG.colors.huaweiRed};
      color: white;
      padding: 14px 18px;
      text-align: left;
      font-weight: 600;
    }
    .data-table td {
      padding: 12px 18px;
      border-bottom: 1px solid #e0e0e0;
    }
    .data-table tr:nth-child(even) { background: #f8f9fa; }
    .data-table tr:hover { background: #f0f4f8; }

    /* 代码块/架构图 */
    .code-block, .ascii-diagram {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 20px 25px;
      border-radius: 8px;
      font-family: "SF Mono", "Fira Code", monospace;
      font-size: 0.95rem;
      overflow-x: auto;
      line-height: 1.5;
    }
    .ascii-diagram {
      background: #f5f7fa;
      color: #333;
      border: 1px solid #e0e0e0;
      font-size: 0.85rem;
      line-height: 1.3;
    }

    /* 两栏布局 */
    .two-columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 40px;
      flex: 1;
    }
    .column {
      display: flex;
      flex-direction: column;
      gap: 15px;
    }
    .column p { font-size: 1.2rem; color: #444; }

    /* 关键指标 */
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 30px;
      padding: 20px 0;
    }
    .metric-item {
      text-align: center;
      padding: 25px;
      background: linear-gradient(135deg, #f8f9fa 0%, #fff 100%);
      border-radius: 12px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    }
    .metric-value {
      font-size: 2.8rem;
      font-weight: 700;
      color: ${CONFIG.colors.huaweiRed};
    }
    .metric-label {
      font-size: 1rem;
      color: #666;
      margin-top: 8px;
    }
    .metric-item.trend-up .metric-value { color: #00a854; }
    .metric-item.trend-down .metric-value { color: ${CONFIG.colors.huaweiRed}; }
    .trend-icon { font-size: 1.5rem; margin-left: 5px; }

    /* 结论/建议框 */
    .conclusion-box {
      background: linear-gradient(135deg, #fff9e6 0%, #fff 100%);
      border-left: 5px solid ${CONFIG.colors.accentGold};
      padding: 20px 25px;
      border-radius: 0 8px 8px 0;
      margin: 15px 0;
    }
    .conclusion-box.suggestion {
      background: linear-gradient(135deg, #e6f7ff 0%, #fff 100%);
      border-left-color: ${CONFIG.colors.huaweiBlue};
    }
    .conclusion-header {
      font-size: 1.1rem;
      font-weight: 600;
      color: #333;
      margin-bottom: 10px;
    }
    .conclusion-content {
      font-size: 1.15rem;
      color: #555;
      line-height: 1.7;
    }

    /* 时间轴 */
    .timeline-container {
      display: flex;
      flex-direction: column;
      gap: 0;
      position: relative;
      padding-left: 30px;
    }
    .timeline-container::before {
      content: "";
      position: absolute;
      left: 8px;
      top: 5px;
      bottom: 5px;
      width: 3px;
      background: linear-gradient(180deg, ${CONFIG.colors.huaweiRed}, ${CONFIG.colors.huaweiBlue});
    }
    .timeline-item {
      display: flex;
      align-items: flex-start;
      gap: 20px;
      padding: 15px 0;
      position: relative;
    }
    .timeline-dot {
      position: absolute;
      left: -26px;
      top: 20px;
      width: 14px;
      height: 14px;
      background: ${CONFIG.colors.huaweiRed};
      border-radius: 50%;
      border: 3px solid white;
      box-shadow: 0 0 0 3px ${CONFIG.colors.huaweiRed}33;
    }
    .timeline-year {
      font-size: 1.1rem;
      font-weight: 700;
      color: ${CONFIG.colors.huaweiRed};
      min-width: 80px;
    }
    .timeline-title {
      font-size: 1.25rem;
      font-weight: 600;
      color: #333;
    }
    .timeline-desc {
      font-size: 1rem;
      color: #666;
      margin-top: 5px;
    }

    /* 引用块 */
    .quote-block {
      font-size: 1.3rem;
      font-style: italic;
      color: #555;
      padding: 20px 30px;
      border-left: 4px solid ${CONFIG.colors.huaweiBlue};
      background: #f8f9fa;
      margin: 15px 0;
    }

    /* 文本块 */
    .text-block {
      font-size: 1.2rem;
      color: #444;
      line-height: 1.8;
    }
    h4.text-block {
      font-size: 1.3rem;
      font-weight: 600;
      color: ${CONFIG.colors.huaweiGray};
      margin-top: 15px;
      padding-bottom: 8px;
      border-bottom: 2px solid #eee;
    }

    /* 页脚 */
    .slide-footer {
      position: absolute;
      bottom: 25px;
      right: 50px;
      left: 50px;
      display: flex;
      justify-content: flex-end;
      align-items: center;
      font-size: 0.9rem;
      color: #999;
    }
    .slide-title .slide-footer,
    .slide-section .slide-footer {
      color: rgba(255,255,255,0.6);
    }

    /* 进度条 */
    .progress-bar {
      position: fixed;
      top: 0;
      left: 0;
      height: 4px;
      background: ${CONFIG.colors.huaweiRed};
      transition: width 0.3s ease;
      z-index: 1000;
    }

    /* 帮助提示 */
    .help-tip {
      position: fixed;
      bottom: 20px;
      left: 20px;
      padding: 10px 20px;
      background: rgba(0,0,0,0.75);
      color: white;
      border-radius: 6px;
      font-size: 0.85rem;
      opacity: 0;
      transition: opacity 0.3s;
      z-index: 1000;
    }
    .help-tip.show { opacity: 1; }

    /* 打印样式 */
    @media print {
      .slide { display: flex !important; page-break-after: always; height: 100vh; }
      body { background: white; }
      .progress-bar, .help-tip { display: none; }
    }
  `;
}

// ==================== JavaScript ====================

function getScript(): string {
  return `
    (function() {
      const slides = document.querySelectorAll('.slide');
      const progress = document.getElementById('progress');
      const help = document.getElementById('help');
      let current = 0;

      function showSlide(n) {
        if (n < 0) n = 0;
        if (n >= slides.length) n = slides.length - 1;
        current = n;
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
            const page = prompt('跳转到页码 (1-' + slides.length + '):');
            if (page) showSlide(parseInt(page) - 1);
            break;
          case 'h': case 'H': case '?': help.classList.toggle('show'); break;
        }
      });

      document.addEventListener('click', (e) => {
        if (e.target.closest('a, button, input')) return;
        const x = e.clientX / window.innerWidth;
        if (x > 0.5) showSlide(current + 1);
        else showSlide(current - 1);
      });

      let touchStartX = 0;
      document.addEventListener('touchstart', (e) => { touchStartX = e.touches[0].clientX; });
      document.addEventListener('touchend', (e) => {
        const diff = touchStartX - e.changedTouches[0].clientX;
        if (Math.abs(diff) > 50) {
          if (diff > 0) showSlide(current + 1);
          else showSlide(current - 1);
        }
      });

      const hash = location.hash.match(/slide-(\\d+)/);
      showSlide(hash ? parseInt(hash[1]) - 1 : 0);

      setTimeout(() => {
        help.classList.add('show');
        setTimeout(() => help.classList.remove('show'), 3000);
      }, 500);
    })();
  `;
}

// ==================== 任务状态管理 ====================

function loadState(): TaskState | null {
  const statePath = path.join(process.cwd(), CONFIG.stateFile);
  if (!fs.existsSync(statePath)) return null;
  try { return JSON.parse(fs.readFileSync(statePath, "utf-8")); } catch { return null; }
}

function saveState(state: TaskState): void {
  const statePath = path.join(process.cwd(), CONFIG.stateFile);
  const dir = path.dirname(statePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  state.updatedAt = new Date().toISOString();
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
}

function clearState(): void {
  const statePath = path.join(process.cwd(), CONFIG.stateFile);
  if (fs.existsSync(statePath)) fs.unlinkSync(statePath);
}

// ==================== TVS 输出 ====================

function printSuccess(inputFile: string, outputFile: string, slideCount: number): void {
  console.log(`
┌─ ✅ PPT Generated (华为风格) ───────────────────┐
│                                                 │
│  Input    ${inputFile.slice(-40).padEnd(40)}│
│  Output   ${outputFile.slice(-40).padEnd(40)}│
│  Slides   ${String(slideCount).padEnd(40)}│
│                                                 │
│  Features:                                      │
│    • ← → 翻页 | F 全屏 | P 打印 | G 跳页       │
│    • 表格 / 架构图 / 时间轴 / 关键指标          │
│    • 结论框 / 建议框 / 多栏布局                 │
│                                                 │
└─────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: solar-dark
切换: /theme <style>
`);
}

function printError(error: string): void {
  console.error(`
┌─ ❌ Error ──────────────────────────────────────┐
│  ${error.slice(0, 47).padEnd(47)}│
└─────────────────────────────────────────────────┘
`);
}

// ==================== 主程序 ====================

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.includes("--help") || args.includes("-h") || args.length === 0) {
    console.log(`
PPT Skill v2 - Markdown to Huawei-style HTML Presentation

Usage:
  bun run ppt.ts <input.md> [output.html]

Markdown 语法:
  # 标题              → 封面页 (华为红)
  ## 章节             → 章节页 (科技蓝)
  ### 内容页标题      → 内容页
  - 要点              → 列表
    - 子要点          → 二级列表

  | 列1 | 列2 |       → 表格
  |-----|-----|
  | A   | B   |

  \`\`\`architecture    → 架构图
  ┌─────┐
  │ Box │
  └─────┘
  \`\`\`

  :::metrics          → 关键指标
  - 40%: 成本降低
  - 60%: 效率提升
  :::

  :::timeline         → 时间轴
  - 2024-Q1: 启动
  - 2024-Q2: 上线
  :::

  :::conclusion       → 结论框
  核心结论内容
  :::

  :::suggestion       → 建议框
  建议内容
  :::

  > 引用文字          → 引用块
  **40%** 降低成本    → 关键数字突出
`);
    return;
  }

  const inputFile = args[0];
  const outputFile = args[1] || inputFile.replace(/\.md$/, ".html");

  if (!fs.existsSync(inputFile)) {
    printError(`File not found: ${inputFile}`);
    return;
  }

  const state: TaskState = {
    inputFile, outputFile, totalSlides: 0, processedSlides: 0,
    status: "processing", startedAt: new Date().toISOString(), updatedAt: new Date().toISOString()
  };
  saveState(state);

  try {
    const content = fs.readFileSync(inputFile, "utf-8");
    const result = parseMarkdown(content);
    const html = generateHTML(result);
    fs.writeFileSync(outputFile, html);

    state.totalSlides = result.slides.length;
    state.processedSlides = result.slides.length;
    state.status = "completed";
    saveState(state);

    printSuccess(inputFile, outputFile, result.slides.length);
    clearState();

  } catch (error: any) {
    state.status = "error";
    state.error = error.message;
    saveState(state);
    printError(error.message);
  }
}

main();
