---
name: changelog
description: 自动生成 CHANGELOG - 基于 Git 提交历史
user-invocable: true
argument-hint: "[version] [--since=tag|date]"
---

# Changelog 自动生成

基于 Git 提交历史自动生成符合 [Keep a Changelog](https://keepachangelog.com/) 规范的变更日志。

## 使用方式

```bash
/changelog              # 生成自上次 tag 以来的变更
/changelog v1.2.0       # 生成指定版本的 changelog
/changelog --since=v1.0 # 从指定 tag 开始
```

## 执行步骤

### 1. 收集提交信息

```bash
# 获取自上次 tag 以来的所有提交
git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~50")..HEAD --pretty=format:'%H|%s|%b---END---'

# 获取当前版本信息
git describe --tags --abbrev=0 2>/dev/null || echo "unreleased"
```

### 2. 分类提交

根据 Conventional Commits 规范分类：

| 前缀 | 分类 | 说明 |
|------|------|------|
| `feat:` | Added | 新功能 |
| `fix:` | Fixed | Bug 修复 |
| `perf:` | Changed | 性能优化 |
| `refactor:` | Changed | 重构 |
| `docs:` | Documentation | 文档更新 |
| `test:` | - | 测试 (不记录) |
| `chore:` | - | 杂项 (不记录) |
| `BREAKING CHANGE` | Breaking Changes | 破坏性变更 |

### 3. 生成 Changelog

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- 新功能描述 (#PR号)

### Changed
- 变更描述

### Fixed
- 修复描述

### Breaking Changes
- 破坏性变更描述

## [1.0.0] - 2026-01-30

### Added
- 初始版本功能

[Unreleased]: https://github.com/user/repo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/user/repo/releases/tag/v1.0.0
```

## 输出选项

- **append**: 追加到现有 CHANGELOG.md
- **replace**: 替换 [Unreleased] 部分
- **stdout**: 输出到终端
- **file**: 写入指定文件

## 智能功能

1. **自动检测版本号**: 从 package.json / Cargo.toml / CMakeLists.txt 读取
2. **关联 Issue/PR**: 自动从提交信息提取 #123 格式的引用
3. **作者归属**: 可选包含贡献者列表
4. **Breaking Change 检测**: 自动识别 BREAKING CHANGE 标记

## 示例输出

```markdown
## [1.2.0] - 2026-01-30

### Added
- 用户行为分析模块 - 自适应推荐系统 (#45)
- Apple Shortcuts 集成 - 支持 macOS 快捷指令 (#46)

### Changed
- 优化 Token 消耗 - 懒加载模式配置 (#44)
- 更新架构图 - 新增两层设计 (#47)

### Fixed
- 修复 Git log 格式解析问题 (#43)

### Contributors
- @sihaoli
```

## 配置

在 `.solar/changelog.json` 中配置：

```json
{
  "types": {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Performance"
  },
  "exclude": ["chore", "test", "ci"],
  "groupByScope": true,
  "includeContributors": true
}
```
