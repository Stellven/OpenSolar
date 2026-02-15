#!/usr/bin/env bun
/**
 * HN Monitor - Hacker News 热门话题监控
 *
 * 功能:
 * - 抓取 HN Top Stories
 * - 存储到 SQLite
 * - 支持历史查询
 *
 * 使用:
 *   bun run fetch.ts              # 抓取并显示
 *   bun run fetch.ts --save       # 抓取并保存到数据库
 *   bun run fetch.ts --history    # 查看历史趋势
 */

import { Database } from "bun:sqlite";
import { homedir } from "os";
import { existsSync } from "fs";

const HN_API = "https://hacker-news.firebaseio.com/v0";
const DB_PATH = `${homedir()}/.solar/solar.db`;
const TOP_N = 30;

interface HNStory {
  id: number;
  title: string;
  url?: string;
  score: number;
  by: string;
  time: number;
  descendants?: number;
}

interface StoredTopic {
  id: number;
  title: string;
  url: string;
  score: number;
  author: string;
  comments: number;
  fetched_at: string;
}

async function fetchTopStories(): Promise<number[]> {
  const res = await fetch(`${HN_API}/topstories.json`);
  const ids = await res.json() as number[];
  return ids.slice(0, TOP_N);
}

async function fetchStory(id: number): Promise<HNStory | null> {
  try {
    const res = await fetch(`${HN_API}/item/${id}.json`);
    return await res.json() as HNStory;
  } catch {
    return null;
  }
}

async function fetchAllStories(): Promise<HNStory[]> {
  const ids = await fetchTopStories();
  const stories = await Promise.all(ids.map(fetchStory));
  return stories.filter((s): s is HNStory => s !== null && s.type === "story" || s?.title !== undefined);
}

function initDB(db: Database) {
  db.run(`
    CREATE TABLE IF NOT EXISTS hn_topics (
      id INTEGER,
      title TEXT,
      url TEXT,
      score INTEGER,
      author TEXT,
      comments INTEGER,
      fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (id, fetched_at)
    )
  `);

  db.run(`
    CREATE INDEX IF NOT EXISTS idx_hn_topics_fetched
    ON hn_topics(fetched_at DESC)
  `);
}

function saveStories(db: Database, stories: HNStory[]) {
  const stmt = db.prepare(`
    INSERT OR REPLACE INTO hn_topics (id, title, url, score, author, comments, fetched_at)
    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
  `);

  for (const s of stories) {
    stmt.run(s.id, s.title, s.url || "", s.score, s.by, s.descendants || 0);
  }
}

function getHistory(db: Database, hours: number = 24): StoredTopic[] {
  return db.query(`
    SELECT * FROM hn_topics
    WHERE fetched_at > datetime('now', '-${hours} hours')
    ORDER BY fetched_at DESC, score DESC
  `).all() as StoredTopic[];
}

function formatStory(s: HNStory, rank: number): string {
  const points = `${s.score}`.padStart(4);
  const comments = `${s.descendants || 0}`.padStart(3);
  return `  ${rank.toString().padStart(2)}. [${points} pts] ${s.title.slice(0, 60)}${s.title.length > 60 ? "..." : ""} (${comments} comments)`;
}

function printTVS(stories: HNStory[]) {
  const now = new Date().toLocaleString("zh-CN");

  console.log(`
┌─────────────────────────────────────────────────────────────────┐
│                     📡 HACKER NEWS TOP ${TOP_N}                       │
├─────────────────────────────────────────────────────────────────┤
│  更新时间: ${now.padEnd(47)}│
├─────────────────────────────────────────────────────────────────┤`);

  stories.slice(0, 15).forEach((s, i) => {
    const line = formatStory(s, i + 1);
    console.log(`│${line.padEnd(65)}│`);
  });

  console.log(`├─────────────────────────────────────────────────────────────────┤
│  使用: /hn-monitor --history 查看趋势                            │
└─────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list`);
}

function printHistory(topics: StoredTopic[]) {
  // Group by hour
  const byHour = new Map<string, StoredTopic[]>();
  for (const t of topics) {
    const hour = t.fetched_at.slice(0, 13);
    if (!byHour.has(hour)) byHour.set(hour, []);
    byHour.get(hour)!.push(t);
  }

  console.log(`
┌─────────────────────────────────────────────────────────────────┐
│                     📈 HN HISTORY (24h)                          │
├─────────────────────────────────────────────────────────────────┤`);

  for (const [hour, items] of Array.from(byHour.entries()).slice(0, 5)) {
    const top = items.sort((a, b) => b.score - a.score)[0];
    console.log(`│  ${hour} - Top: ${top.title.slice(0, 45)}...│`);
  }

  console.log(`└─────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list`);
}

async function main() {
  const args = process.argv.slice(2);
  const shouldSave = args.includes("--save");
  const showHistory = args.includes("--history");

  // Ensure DB exists
  if (!existsSync(DB_PATH)) {
    console.error(`Database not found: ${DB_PATH}`);
    process.exit(1);
  }

  const db = new Database(DB_PATH);
  initDB(db);

  if (showHistory) {
    const history = getHistory(db);
    printHistory(history);
    return;
  }

  console.log("Fetching HN top stories...");
  const stories = await fetchAllStories();

  if (shouldSave) {
    saveStories(db, stories);
    console.log(`Saved ${stories.length} stories to database.`);
  }

  printTVS(stories);
}

main().catch(console.error);
