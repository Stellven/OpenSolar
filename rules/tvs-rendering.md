# Solar 铁律: TVS 渲染

> **TVS 是 Solar 字符界面的唯一渲染器**

## 核心原则

**所有 Solar 终端输出必须通过 TVS 渲染。LLM 不渲染像素，只生成意图和结构。**

```
┌─────────────────────────────────────────────────────────────┐
│                    TVS = Solar 渲染核心                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Solar Output                                              │
│       │                                                     │
│       ▼                                                     │
│   ┌───────────────────────────────────────────────────┐    │
│   │                    TVS                             │    │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────────────┐   │    │
│   │  │   VDL   │→ │  TCSS   │→ │ Compiler+Render │   │    │
│   │  │ (意图)  │  │ (布局)  │  │   (确定性)      │   │    │
│   │  └─────────┘  └─────────┘  └─────────────────┘   │    │
│   └───────────────────────────────────────────────────┘    │
│       │                                                     │
│       ▼                                                     │
│   Terminal / Web / SSH                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────┐
│                    TVS 渲染管线                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   LLM 生成 (意图层)                                         │
│   ┌──────────────────────────────────────────────────────┐ │
│   │  VDL (Visual Description Language)                   │ │
│   │  • card("标题", [...sections])                       │ │
│   │  • kv([{key, value}])                                │ │
│   │  • table(headers, rows)                              │ │
│   │  • sparkline(data, label)                            │ │
│   │  • progress(value, max)                              │ │
│   └──────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│   编译器 (确定性)                                           │
│   ┌──────────────────────────────────────────────────────┐ │
│   │  TCSS → Grid IR → ASCII/Braille                      │ │
│   └──────────────────────────────────────────────────────┘ │
│                          ↓                                  │
│   终端输出                                                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 适用范围

**所有 Solar 终端输出**，包括但不限于：

| 场景 | TVS 组件 |
|------|---------|
| 状态报告 | `card()` + `kv()` |
| 数据表格 | `table()` |
| 进度展示 | `progress()` + `sparkline()` |
| 架构图 | `section("ascii", ...)` |
| 仪表盘 | 完整 `dashboard` |
| 错误信息 | `card()` + `section("error")` |
| 任务列表 | `table()` / `kv()` |

## 显式触发词 (高优先级渲染)

当用户说以下词时，输出完整 VDL 仪表盘：
- "我要看..."
- "我想看..."
- "给我看..."
- "展示..."
- "显示..."
- "呈现..."

## VDL 快速参考

### 基础组件

```typescript
// 卡片
card("TITLE", [
  kv([{ key: "Status", value: "Active" }]),
  sparkline([1,2,3,4,5], "trend"),
  progress(75, 100)
])

// 键值对
kv([
  { key: "Name", value: "Solar" },
  { key: "Version", value: "2.0" }
])

// 表格
table(
  ["Column 1", "Column 2", "Column 3"],
  [
    ["A", "B", "C"],
    ["D", "E", "F"]
  ]
)

// Sparkline (Braille 精度)
sparkline([10, 20, 30, 25, 35, 40], "Latency")
// Output: ▁▂▄▃▅▆

// 进度条
progress(75, 100)
// Output: ███████░░░ 75%
```

### 布局 (TCSS)

```css
/* 3列网格 */
.root {
  columns: 3;
  gap: 1;
}

/* 响应式 */
@media (max-width: 80) {
  .root { columns: 1; }
}

/* Focus 样式 */
:focus {
  border-color: cyan;
}
```

## 输出格式

展示内容时，输出完整的 VDL 结构:

```typescript
// agent-memory-architecture.vdl
export const dashboard = {
  layout: `
    .root { columns: 2; gap: 1; }
    #overview { column: 1; row: 1; }
    #papers { column: 2; row: 1; }
    #design { column: 1 / span 2; row: 2; }
  `,
  widgets: [
    card("OVERVIEW", [
      kv([
        { key: "Papers", value: "3" },
        { key: "Status", value: "Analyzed" }
      ])
    ]),
    card("PAPERS", [
      table(
        ["#", "Name", "Core"],
        [
          ["1", "A-MEM", "Zettelkasten"],
          ["2", "Survey", "3D Framework"],
          ["3", "Mem0", "Production"]
        ]
      )
    ]),
    card("ARCHITECTURE", [
      // ASCII diagram here
    ])
  ]
};
```

## 示例: 之前的架构设计

如果用 TVS 渲染 Agent Memory 架构:

```typescript
// 论文分析仪表盘
const paperDashboard = {
  layout: `
    .root { columns: 3; gap: 1; }
    @media (max-width: 100) { .root { columns: 1; } }
  `,
  widgets: [
    card("A-MEM", [
      kv([
        { key: "Conference", value: "NeurIPS 2025" },
        { key: "Innovation", value: "Memory Evolution" }
      ]),
      sparkline([1,2,3,4,5,6,7,8], "citations")
    ]),
    card("MEMORY SURVEY", [
      kv([
        { key: "Framework", value: "3D Taxonomy" },
        { key: "Dimensions", value: "Form×Function×Dynamics" }
      ])
    ]),
    card("MEM0", [
      kv([
        { key: "Type", value: "Production" },
        { key: "Latency", value: "-91%" },
        { key: "Cost", value: "-90%" }
      ]),
      progress(91, 100)
    ])
  ]
};
```

渲染输出:

```
┌─────────────────┬─────────────────┬─────────────────┐
│     A-MEM       │  MEMORY SURVEY  │      MEM0       │
├─────────────────┼─────────────────┼─────────────────┤
│ Conference      │ Framework       │ Type Production │
│   NeurIPS 2025  │   3D Taxonomy   │ Latency   -91%  │
│ Innovation      │ Dimensions      │ Cost      -90%  │
│   Memory Evol.  │   Form×Func×Dyn │ █████████░ 91%  │
│                 │                 │                 │
│ ▁▂▃▄▅▆▇█        │                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
```

## 风格系统

**TVS 支持多风格切换，所有 Agent 和流程共享同一风格设置。**

### 内置风格

| ID | 名称 | 边框 | 配色 | 特点 |
|----|------|------|------|------|
| `solar-dark` | Solar Dark | ┌─┐ | cyan | **默认** 专业现代 |
| `solar-light` | Solar Light | ┌─┐ | blue | 清新明亮 |
| `minimal` | Minimal | 无 | white | 极简纯文本 |
| `neon` | Neon | ╔═╗ | magenta | 赛博朋克 |
| `ascii` | ASCII | +-+ | white | 最大兼容 |
| `rounded` | Rounded | ╭─╮ | cyan | 柔和圆角 |

### 切换方式

```bash
/theme                    # 显示当前风格
/theme list               # 列出所有风格
/theme <name>             # 切换到指定风格
/theme solar-dark         # 切换到 Solar Dark
```

### 风格优先级

```
Session 指定 > Agent 偏好 > Phase 偏好 > Global 默认
```

### 风格存储 (IaST)

```sql
tvs_themes              -- 风格定义表
tvs_theme_preferences   -- 偏好设置表
tvs_theme_history       -- 切换历史表
v_tvs_active_theme      -- 当前激活风格视图
v_tvs_theme_list        -- 风格列表视图
```

## TVS Footer (铁律 - 必须)

**每次 TVS 渲染输出必须包含完整的 Footer (三行)：**

```
────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list
```

### Footer 内容要求

| 行 | 内容 | 说明 |
|----|------|------|
| 第1行 | 分隔线 | 全宽度横线 |
| 第2行 | `Powered by TVS v{版本} · Style: {当前风格}` | 主标识 |
| 第3行 | `可选风格: {3-6个其他风格} ...` | 提示可切换 |
| 第4行 | `切换风格: /theme <style>` | 切换命令 |

### 示例

```
┌─ 💻 Coder ──────────────────────────────────────────────────────┐
│ Task: 优化 Hash Join 性能                                        │
│ Plan:                                                           │
│   1. 分析当前瓶颈                                                │
│   2. 实现 SIMD 加速                                              │
│   3. 验证性能提升                                                │
├─────────────────────────────────────────────────────────────────┤
│ Progress   ████████░░░░ 67%                                     │
└─────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────
Powered by TVS v0.4.0 · Style: zenwhite.terminal
可选风格: monolith | aurora | cyberpunk | liquid.dark | swiss ...
切换风格: /theme <style> | 查看所有: /theme list
```

### 简洁版 Footer (空间受限时可用)

```
Powered by TVS v0.4.0 · zenwhite.terminal · /theme to switch
```

## 铁律总结

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🎨 TVS 渲染铁律                                           │
│                                                             │
│   1. LLM 生成 VDL，不生成 ASCII                             │
│   2. 布局用 TCSS，不用硬编码                                │
│   3. 组件用 DSL (card/kv/table/sparkline)                  │
│   4. 确定性渲染，可复现                                     │
│   5. 必须包含完整 Footer:                                   │
│      ─────────────────────────────────────────────────      │
│      Powered by TVS v0.4.0 · Style: {当前风格}              │
│      可选风格: monolith | aurora | cyberpunk ...            │
│      切换风格: /theme <style>                               │
│                                                             │
│   意图 → 编译 → 渲染 (三层分离)                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```
