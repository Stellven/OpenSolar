# /weather - 天气查询

查询指定城市的天气信息，支持 TVS 渲染展示。

## 使用方式

```bash
/weather                    # 查询默认城市 (北京)
/weather 上海               # 查询上海天气
/weather Beijing --en       # 英文输出
/weather --forecast         # 显示 5 天预报
```

## 功能

| 功能 | 说明 |
|------|------|
| 实时天气 | 温度、湿度、风速、天气状况 |
| 5天预报 | 未来5天天气趋势 |
| 多城市 | 支持中英文城市名 |
| TVS渲染 | 美观的终端卡片展示 |

## 数据源

优先级:
1. Apple WeatherKit (via Shortcut) - 无需 API Key
2. OpenWeatherMap API - 需要 API Key

## 输出示例

```
┌─────────────────────────────────────────────────────────────────┐
│                     🌤️ 北京天气                                  │
├─────────────────────────────────────────────────────────────────┤
│  温度      -2°C (体感 -6°C)                                     │
│  天气      晴转多云                                              │
│  湿度      35%                                                   │
│  风速      北风 3级                                              │
│  日出      07:12  日落 17:38                                    │
├─────────────────────────────────────────────────────────────────┤
│  未来 5 天:                                                      │
│  02/03 ☀️  -1°C ~ 8°C                                           │
│  02/04 ⛅  0°C ~ 7°C                                            │
│  02/05 🌧️  2°C ~ 5°C                                            │
│  02/06 ☀️  -2°C ~ 6°C                                           │
│  02/07 ☀️  -3°C ~ 5°C                                           │
└─────────────────────────────────────────────────────────────────┘
```

## 数据库 Schema (IaST)

```sql
CREATE TABLE sys_weather_cache (
  city TEXT PRIMARY KEY,
  data JSON,
  fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 缓存 30 分钟内有效
CREATE VIEW v_weather_valid AS
SELECT * FROM sys_weather_cache
WHERE fetched_at > datetime('now', '-30 minutes');
```

## 演进记录

- **触发**: 用户需求 "帮我查看今天北京的天气"
- **匹配**: NO_MATCH (无天气相关能力)
- **创建**: 2026-02-02 自动演进生成
- **类型**: Skill + Shortcut

## 相关

- `/shortcut` - Apple Shortcuts 执行
- `sys_weather_cache` - 天气缓存表
