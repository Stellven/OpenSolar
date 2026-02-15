---
name: theme
description: TVS 风格切换
command: theme
user_invocable: true
category: workflow
---

# /theme - TVS 风格切换

## 用法

```bash
/theme                    # 显示当前风格 + 风格列表
/theme list               # 列出所有可用风格
/theme <name>             # 切换到指定风格
/theme preview <name>     # 预览风格效果
```

## 内置风格

| 快捷键 | ID | 名称 | 特点 |
|--------|-----|------|------|
| `1` | `solar-dark` | Solar Dark | **默认** 专业深色 |
| `2` | `solar-light` | Solar Light | 清新浅色 |
| `3` | `minimal` | Minimal | 极简无边框 |
| `4` | `neon` | Neon | 赛博朋克 |
| `5` | `ascii` | ASCII | 纯 ASCII 兼容 |
| `6` | `rounded` | Rounded | 柔和圆角 |

## 执行流程

### 1. 无参数 `/theme`

显示当前状态和风格选择器：

```
╭─────────────────────────────────────────────────────────────╮
│                    TVS THEME SELECTOR                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Current: solar-dark ✓                                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [1] Solar Dark   ████ ✓ Active                      │   │
│  │ [2] Solar Light  ████                               │   │
│  │ [3] Minimal      ░░░░                               │   │
│  │ [4] Neon         ▓▓▓▓                               │   │
│  │ [5] ASCII        +--+                               │   │
│  │ [6] Rounded      ╭──╮                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Usage: /theme <name> or /theme <number>                   │
│                                                             │
╰─────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─╯
```

### 2. `/theme list`

详细风格列表：

```
╭─────────────────────────────────────────────────────────────╮
│                    TVS THEME LIST                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ID            Name          Border    Scheme   Status      │
│  ─────────────────────────────────────────────────────────  │
│  solar-dark    Solar Dark    single    dark     ✓ Active   │
│  solar-light   Solar Light   single    light               │
│  minimal       Minimal       none      dark                │
│  neon          Neon          double    dark                │
│  ascii         ASCII         ascii     dark                │
│  rounded       Rounded       rounded   dark                │
│                                                             │
╰─────────────────────────── [solar-dark] Powered by TVS v0.3.0 ─╯
```

### 3. `/theme <name>`

切换风格并确认：

```
╭─────────────────────────────────────────────────────────────╮
│                    THEME SWITCHED                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  From:  solar-dark                                          │
│  To:    neon ✓                                              │
│                                                             │
│  All agents and workflows will use this theme.              │
│                                                             │
╰─────────────────────────────── [neon] Powered by TVS v0.3.0 ─╯
```

### 4. `/theme preview <name>`

预览风格效果（不切换）：

```
╔═════════════════════════════════════════════════════════════╗
║                    THEME PREVIEW: neon                       ║
╠═════════════════════════════════════════════════════════════╣
║                                                             ║
║  ╔═══════════════════╗  ╔═══════════════════╗              ║
║  ║   SAMPLE CARD     ║  ║   SAMPLE TABLE    ║              ║
║  ╠═══════════════════╣  ╠═══════════════════╣              ║
║  ║ Key     Value     ║  ║ A    B    C       ║              ║
║  ║ Status  Active    ║  ║ 1    2    3       ║              ║
║  ║ Progress ▓▓▓▓░░░  ║  ╚═══════════════════╝              ║
║  ╚═══════════════════╝                                      ║
║                                                             ║
║  Use `/theme neon` to apply.                                ║
║                                                             ║
╚═════════════════════════════════════ [PREVIEW] TVS v0.3.0 ══╝
```

## 风格效果对比

### Solar Dark (默认)
```
┌─────────────────────────────┐
│        SOLAR DARK           │
├─────────────────────────────┤
│ Status    Active            │
│ Progress  ████████░░ 80%    │
└─────────────────────────────┘
```

### Neon
```
╔═════════════════════════════╗
║          NEON               ║
╠═════════════════════════════╣
║ Status    Active            ║
║ Progress  ▓▓▓▓▓▓▓▓░░ 80%    ║
╚═════════════════════════════╝
```

### Rounded
```
╭─────────────────────────────╮
│        ROUNDED              │
├─────────────────────────────┤
│ Status    Active            │
│ Progress  ●●●●●●●●○○ 80%    │
╰─────────────────────────────╯
```

### ASCII
```
+-----------------------------+
|          ASCII              |
+-----------------------------+
| Status    Active            |
| Progress  ########.. 80%    |
+-----------------------------+
```

### Minimal
```
MINIMAL

Status    Active
Progress  ████████░░ 80%
```

## 全局生效

风格切换后，以下组件自动应用新风格：

- 所有 Agent 输出
- 所有 Skill 输出
- 任务状态显示
- 错误信息
- 进度报告
- 仪表盘

## 存储

风格设置存储在 `~/.solar/solar.db`:

```sql
-- 查看当前风格
SELECT * FROM v_tvs_active_theme;

-- 查看切换历史
SELECT * FROM tvs_theme_history ORDER BY switched_at DESC LIMIT 10;
```
