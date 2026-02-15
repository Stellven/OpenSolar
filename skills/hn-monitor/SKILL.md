# /hn-monitor - Hacker News 监控

监控 Hacker News 热门话题，支持定时更新和历史趋势查看。

## 使用方式

```bash
/hn-monitor                # 查看当前 Top 30
/hn-monitor --save         # 抓取并保存到数据库
/hn-monitor --history      # 查看 24 小时历史趋势
/hn-monitor --stop         # 停止定时监控
```

## 功能

| 功能 | 说明 |
|------|------|
| 实时抓取 | 从 HN Firebase API 获取 Top 30 |
| 数据存储 | 保存到 ~/.solar/solar.db (hn_topics 表) |
| 历史趋势 | 查看 24 小时内的热门变化 |
| 定时执行 | LaunchAgent 每小时自动更新 |

## 数据流

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  HN API      │ →  │  fetch.ts    │ →  │  SQLite      │
│  (Firebase)  │    │  (Bun)       │    │  (hn_topics) │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │  Dashboard   │
                                        │  (Solar Web) │
                                        └──────────────┘
```

## 输出示例

```
┌─────────────────────────────────────────────────────────────────┐
│                     📡 HACKER NEWS TOP 30                        │
├─────────────────────────────────────────────────────────────────┤
│  更新时间: 2026/1/31 14:00:00                                   │
├─────────────────────────────────────────────────────────────────┤
│   1. [ 948 pts] Antirender: remove glossy shine on renders      │
│   2. [ 856 pts] Show HN: I built a new programming language     │
│   3. [ 742 pts] The future of AI inference                      │
│   ...                                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 数据库 Schema

```sql
CREATE TABLE hn_topics (
  id INTEGER,
  title TEXT,
  url TEXT,
  score INTEGER,
  author TEXT,
  comments INTEGER,
  fetched_at DATETIME,
  PRIMARY KEY (id, fetched_at)
);
```

## 定时任务

安装位置: `~/Library/LaunchAgents/com.solar.hn-monitor.plist`

- 每小时执行一次
- 自动保存到数据库
- 日志: `~/.solar/logs/hn-monitor.log`

### 管理定时任务

```bash
# 查看状态
launchctl list | grep hn-monitor

# 手动触发
launchctl start com.solar.hn-monitor

# 停止
launchctl unload ~/Library/LaunchAgents/com.solar.hn-monitor.plist

# 重新启动
launchctl load ~/Library/LaunchAgents/com.solar.hn-monitor.plist
```

## 依赖

- Bun runtime
- ~/.solar/solar.db (Solar 数据库)

## 相关

- `/solar-web` - Solar Web Dashboard (显示 HN 数据)
- `sys_skills` - 技能注册表
