#!/usr/bin/env bun
/**
 * Code Indexer - 扫描项目代码建立索引
 *
 * 功能：
 * 1. 扫描 ~/ 下所有项目的代码
 * 2. 提取函数、类、常量、接口定义
 * 3. 存入 Cortex FTS 表
 * 4. 支持快速搜索
 */

import { readdirSync, readFileSync, statSync, writeFileSync, existsSync } from 'fs';
import { join, extname, relative } from 'path';
import { Database } from 'bun:sqlite';

// ============ 配置 ============

const HOME = process.env.HOME || '/Users/sihaoli';
const DB_PATH = `${HOME}/.solar/solar.db`;

// 要扫描的目录 - 扫描整个 ~ 目录
const SCAN_DIRS = [HOME];

// 要索引的文件类型
const EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.py', '.go', '.rs', '.java', '.swift', '.kt', '.scala', '.c', '.cpp', '.h'];

// 跳过的目录（只跳过缓存和构建目录）
const SKIP_DIRS = [
  'node_modules', '.git', 'dist', 'build', '__pycache__', '.venv', 'vendor',
  '.npm', '.cache', '.rustup', '.cargo', '.bun', '.Trash',
  'Applications', 'Movies', 'Music', 'Pictures', 'Downloads',
];

// 最大文件大小 (100KB)
const MAX_FILE_SIZE = 100 * 1024;

// ... (其余代码保持不变，使用之前实现的完整版本)
