# Design: S03 Core-Runtime (cmux 监控工作台)

## 1. 目标

把 S02 的架构约束落成最小可用 runtime：

1. 配置驱动 workspace/tabs/panes
2. 本地 1/2/3/4 pane 布局规则
3. `capture-pane` 默认镜像模式
4. `pipe-pane + tail -F` 日志模式
5. `doctor` 检查 ssh/tmux/target pane/log path

## 2. 核心脚本

1. `render-cmux-workspace`
   - 读 yaml
   - 生成 tab / pane launch commands
2. `cmux-monitor-up`
   - 启动 workspace
3. `cmux-monitor-down`
   - 停止 workspace
4. `cmux-monitor-doctor`
   - 输出 machine-verifiable health report
5. `tmux-pane-view`
   - capture 模式
6. `tmux-pane-log-follow`
   - tail 模式

## 3. 模式边界

### capture
- 优先用于“当前屏幕状态”
- 支持 local/remote
- fail-open 输出错误信息，不黑屏退出

### tail
- 优先用于构建日志、agent 输出、pytest/build logs
- 支持 log path 校验
- 不承诺完整屏幕快照

## 4. 布局规则

1. 1 pane: full screen
2. 2 panes: 1x2
3. 3 panes: top-two / bottom-one
4. 4 panes: default 2x2 equal split

## 5. SSH 复用

默认推荐：
- `ControlMaster auto`
- `ControlPath ~/.ssh/cmux-%r@%h:%p`
- `ControlPersist 10m`

## 6. DoD

1. 配置样例可渲染
2. quad 默认 2x2 等分
3. local/remote capture 可表达
4. tail 模式与 doctor 可表达

