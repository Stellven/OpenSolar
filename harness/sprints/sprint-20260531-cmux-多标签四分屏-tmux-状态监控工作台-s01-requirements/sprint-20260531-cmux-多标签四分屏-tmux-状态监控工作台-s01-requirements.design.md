# Design: cmux 多标签四分屏 tmux 状态监控工作台 — Requirements (S01)

sprint_id: `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s01-requirements`

## 1. 系统定位

cmux = 本地多标签大屏工作台 + ssh 传输 + tmux capture/pipe 远端 pane 状态镜像。
不是交互式 remote pane attach 系统。不是重做 tmux/remote dispatch。

## 2. 架构拓扑

```
┌──────────────────────────────────────────────┐
│              cmux 本地工作台                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│  │ Tab A   │ │ Tab B   │ │ Tab C   │ ...    │
│  │ 4 panes │ │ 2 panes │ │ 4 panes │        │
│  └────┬────┘ └────┬────┘ └────┬────┘        │
│       │           │           │              │
│   ┌───┴───────────┴───────────┴────┐         │
│   │     tmux-pane-view / tail-F    │         │
│   └───┬───────────┬───────────┬────┘         │
│       │ local     │ ssh       │ ssh          │
│       ▼           ▼           ▼              │
│   local tmux   mini tmux    mini tmux        │
│   capture      capture      pipe+tail        │
└──────────────────────────────────────────────┘
```

## 3. 监控模式规格

| 模式 | 命令 | 适用场景 | 输出 |
|------|------|---------|------|
| capture | `tmux capture-pane -p -t <target> -S -<lines>` | 当前屏幕状态 | 最近 N 行 |
| tail | `tail -F <log_path>` (经 pipe-pane) | 持续日志流 | 追加日志 |

capture 模式要求：
- 轮询间隔可配 (默认 1s)
- 抓取行数可配 (默认 60)
- 输出顶部带时间戳/target/mode/host
- 失败时 fail-open 显示错误，不黑屏退出

tail 模式要求：
- 远端需先开启 `tmux pipe-pane -o -t <target> 'cat >> <log_path>'`
- 本地 `ssh <host> 'tail -F <log_path>'`

## 4. 布局规格

| Pane 数 | 布局 | 描述 |
|---------|------|------|
| 1 | 全屏 | single pane |
| 2 | `even-horizontal` | 左右平分 |
| 3 | 上 2 下 1 | `main-horizontal` 变体 |
| 4 | `tiled` (2×2) | **默认平均分屏** |

## 5. Config Schema

```yaml
workspace_name: solar-monitor
ssh_profiles:
  mini:
    host: mini
    user: lisihao
    control_master: auto
    control_path: ~/.ssh/cmux-%r@%h:%p
    control_persist: 10m

tabs:
  - name: project-a
    panes:
      - title: planner
        source: remote         # local | remote
        ssh_profile: mini
        tmux_target: solar:0.0
        mode: capture          # capture | tail
        lines: 60
        interval_sec: 1
      - title: builder
        source: remote
        ssh_profile: mini
        tmux_target: solar:0.1
        mode: capture
      - title: eval
        source: remote
        ssh_profile: mini
        tmux_target: solar:0.2
        mode: tail
        log_path: ~/.tmux-pane-logs/solar-0-2.log
      - title: local-monitor
        source: local
        tmux_target: local:0.0
        mode: capture
```

## 6. 脚本清单

| 脚本 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `cmux-monitor-up` | 按配置启动工作台 | workspace.yaml | tmux session |
| `cmux-monitor-down` | 停止工作台 | workspace name | 清理 session |
| `cmux-monitor-doctor` | 健康检查 | workspace.yaml | ssh/tmux/target 状态 |
| `tmux-pane-view` | 单 pane capture 视图 | target + mode | 屏幕输出 |
| `tmux-pane-log-follow` | 单 pane tail 视图 | log_path + ssh | 持续日志 |
| `render-cmux-workspace` | 从 yaml 生成 tmux 命令 | workspace.yaml | bash 脚本 |

## 7. SSH 复用规格

推荐 `~/.ssh/config` 段：
```
Host mini
  ControlMaster auto
  ControlPath ~/.ssh/cmux-%r@%h:%p
  ControlPersist 10m
```

doctor 检查项：
- SSH 连接可达
- ControlMaster socket 存在
- 远端 tmux server 运行
- 目标 pane 存在
- pipe-pane log 文件可读 (tail 模式)

## 8. 需求分组

| RG | 需求 | 验收 | 对应切片 |
|----|------|------|---------|
| RG1 | Config Schema 定义 | YAML schema + 样例 | S01→S02 |
| RG2 | capture 模式实现 | 本地+远程 capture 可工作 | S01→S03 |
| RG3 | tail 模式实现 | pipe-pane + tail-F 可工作 | S01→S03 |
| RG4 | 布局管理 | 1/2/3/4 pane 布局正确 | S01→S03 |
| RG5 | 启停脚本 | up/down 一键操作 | S01→S03 |
| RG6 | Doctor 健康检查 | ssh/tmux/target/log 可检查 | S01→S04 |
| RG7 | SSH 复用 | ControlMaster 验证 | S01→S03 |
| RG8 | 文档 | 设计决策 + 使用指南 | S01→S04 |

## 9. Epic→Sprint Traceability

| 切片 | 输入 | 产出 | 验收 | 依赖 |
|------|------|------|------|------|
| S01 requirements | epic.md, 用户需求 | config schema, 模式规格, 脚本清单 | D1-D6 | 无 |
| S02 architecture | S01 schema + 规格 | 脚本架构, tmux 命令序列 | 架构 review | S01 |
| S03 core-runtime | S02 架构 | 6 脚本实现 + 配置样例 | 脚本可运行 | S02 |
| S04 observability | S03 脚本 | doctor + 文档 | doctor 通过 | S03 |
| S05 verification | S03+S04 | E2E 验证 | 全部 AC 通过 | S03,S04 |

## 10. 非目标
- 不做远程 tmux pane 一等公民 attach
- 不追求 vim/top/htop 等复杂 TUI 完美渲染
- 不做可写交互控制面
- 不重做 remote dispatch / Mirage / operator runtime

## 11. 风险

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | capture-pane 对宽字符/ANSI 渲染不完美 | 显示异常 | 接受为 known limitation |
| R2 | SSH 连接中断后 pane 黑屏 | 监控中断 | fail-open + 自动重连 |
| R3 | pipe-pane 日志文件无限增长 | 磁盘 | logrotate 建议 |
