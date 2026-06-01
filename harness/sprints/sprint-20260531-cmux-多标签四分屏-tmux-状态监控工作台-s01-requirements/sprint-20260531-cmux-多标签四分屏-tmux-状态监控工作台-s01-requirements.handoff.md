# Handoff

## 结论

S01 requirements 已完成：cmux 监控工作台的核心形态、模式边界、配置 contract、doctor 目标和 P0 non-goals 已冻结，可进入 `S02_architecture`。

## 本切片锁定的设计前提

1. `cmux` 负责本地多 tab 和 4-pane 平均分屏工作台。
2. `ssh` 负责本地到远程 mac mini 传输。
3. `tmux capture-pane` 是默认状态镜像模式。
4. `tmux pipe-pane + tail -F` 是日志流模式。
5. 第一阶段不追求“每个 cmux pane 直接 attach 一个 remote tmux pane”。

## 进入 S02 必做项

1. 定义 `workspace/monitor yaml` schema
2. 定义 tab / pane / source / mode / ssh_profile / refresh 配置语义
3. 设计 1/2/3/4 pane 布局算法，尤其 4 pane 2x2 平均分屏
4. 设计 capture mode 和 tail mode 的脚本接口
5. 设计 doctor/health 和 SSH ControlMaster 默认建议

## 未闭环项

1. 还没有 `cmux-monitor-up/down/doctor` 脚本
2. 还没有 `tmux-pane-view` / `tmux-pane-log-follow` 入口
3. 还没有 config sample 与 docs
