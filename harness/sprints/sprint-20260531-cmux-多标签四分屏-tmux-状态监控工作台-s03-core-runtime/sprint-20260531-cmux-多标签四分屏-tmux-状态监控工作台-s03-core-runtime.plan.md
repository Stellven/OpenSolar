# Plan: S03 Core-Runtime (cmux 监控工作台)

## Wave 1: 配置与渲染

1. 定义 workspace schema loader
2. 实现 tabs/panes 渲染器
3. 校验每 tab 最多 4 panes

## Wave 2: 监控模式

1. 实现 `tmux-pane-view`
2. 实现 `tmux-pane-log-follow`
3. local/remote source 分流

## Wave 3: 生命周期脚本

1. `cmux-monitor-up`
2. `cmux-monitor-down`
3. `cmux-monitor-doctor`

## Wave 4: 验证

1. sample config smoke
2. quad layout snapshot
3. ssh reuse / tmux target / tail path doctor

## 停止规则

1. 第一阶段不做交互式 remote pane attach。
2. 不重做 remote dispatch。
3. 不承诺复杂 TUI 完美渲染。

