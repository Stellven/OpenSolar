# PRD: 核心实现与数据模型

epic_id: `epic-20260531-cmux-多标签四分屏-tmux-状态监控工作台`
sprint_id: `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

# 请为 solar-harness 开一个新的 P0 功能单：cmux 多标签四分屏 tmux 状态监控工作台

请为 solar-harness 开一个新的 P0 功能单，主题是：
在我的电脑（笔记本或 mac mini）上配置一个 `cmux` 监控工作台，支持多个 tab 页面；每个 tab 最多 4 个 pane，平均分配屏幕空间；每个 pane 用来显示一个本地或远程 mac mini 上运行的 tmux pane 的状态。

这张单的目标不是做一个通用终端复用器，也不是重做 tmux/remote dispatch，而是做一个实用、稳定、可重复启动的 `cmux + ssh + tmux` 监控工作台。

一、先写死核心实现判断

不要按“每个 cmux pane 直接 attach 一个远程 tmux pane”来设计。

原因：
1. tmux 原生 attach 的核心单位是 session/window/client，不是把单个 pane 当独立 attach endpoint 暴露。
2. 我这次的需求重点是“显示运行状态”，不是在 cmux 里远程交互编辑。
3. 因此第一阶段最稳的设计应该是：
   - `capture-pane` 屏幕镜像
   - 或 `pipe-pane + tail -F` 日志流
   - 再由 cmux 负责本地 tab + 4-pane layout

一句话：
**cmux 做本地大屏工作台，ssh 做传输，tmux capture/pipe 做远端 pane 状态镜像。**

二、功能目标

### Goal A：cmux 多标签页工作台
1. 支持多个 tab 页面。
2. 每个 tab 最多 4 个 pane。
3. 默认 4-pane 等分屏幕空间。
4. tab 对应一个逻辑工作区，例如：
   - `project-a`
   - `project-b`
   - `mini-runtime`
   - `local-runtime`

### Goal B：每个 pane 绑定一个 tmux pane 来源
每个 cmux pane 可以显示以下来源之一：
1. 本机 tmux pane
2. 远程 mac mini tmux pane（经 ssh）

最少支持 target 形式：
- `solar:0.0`
- `solar:0.1`
- `solar:1.0`
- `build:2.3`

### Goal C：只读状态监控优先
第一阶段监控模式优先级：
1. `capture-pane` 轮询镜像
2. `pipe-pane + tail -F` 持续日志流

要求：
- 默认模式优先 `capture-pane`，因为更接近“当前屏幕状态”
- 日志型 pane 可切 `tail` 模式
- 不要求第一阶段支持真正交互式 attach 单 pane
- 不要求第一阶段把 curses/vim/top/htop 等复杂 TUI 完美渲染

### Goal D：一键启动 / 配置驱动
必须支持通过配置文件生成/启动整个 cmux 工作台，而不是靠手工逐 pane 输入命令。

至少要支持：
- `workspace.yaml` / `monitor.yaml` 一类配置
- 定义 tabs
- 定义每个 tab 的 1~4 个 pane
- 定义 pane 来源：local / remote
- 定义 target pane id
- 定义 mode：capture / tail
- 定义刷新间隔、抓取行数、标题

三、实现方向（要求 requirements/architecture 写死）

### 1. 推荐监控模式 A：capture-pane mirror
示例命令：

```bash
ssh mini 'while true; do clear; tmux capture-pane -p -t solar:0.0 -S -60; sleep 1; done'
```

要求：
- 支持本地 target 与远程 target
- 支持可配置 lines / interval
- 输出顶部要带时间戳、target、mode、host
- 失败时 fail-open 显示错误信息，而不是黑屏退出

### 2. 推荐监控模式 B：pipe-pane + tail -F
远程端可选开启：

```bash
tmux pipe-pane -o -t solar:0.0 'cat >> ~/.tmux-pane-logs/solar-0-0.log'
```

本地监控：

```bash
ssh mini 'tail -F ~/.tmux-pane-logs/solar-0-0.log'
```

要求：
- 作为日志流模式
- 适合 builder/evaluator/build logs/agent 输出
- 要明确定义与 capture mode 的差异和适用场景

### 3. cmux 布局要求
必须支持：
- 一个 tab 内最多 4 pane
- 1 pane：全屏
- 2 pane：左右平分
- 3 pane：上 2 下 1 或等价清晰布局
- 4 pane：2x2 平均分

重点：
**默认 4 pane 时必须平均分屏幕空间。**

### 4. SSH 复用
要求默认推荐并支持 OpenSSH ControlMaster 复用：
- `ControlMaster auto`
- `ControlPath ~/.ssh/cmux-%r@%h:%p`
- `ControlPersist 10m`

目的：
- 避免同一个 tab 内 4 个 pane 各自重复认证
- 提高远程刷新流畅度

四、建议新增的产物

请按实现最小化原则，优先考虑这些产物：

1. `scripts/cmux/` 或等价目录
   - `cmux-monitor-up`
   - `cmux-monitor-down`
   - `cmux-monitor-doctor`
   - `tmux-pane-view`
   - `tmux-pane-log-follow`
   - `render-cmux-workspace`

2. 配置样例
   - `config/cmux-monitor.example.yaml`

3. 文档
   - `docs/cmux-monitor-workspace.md`

五、建议的数据模型

配置至少要表达：

```yaml
workspace_name: solar-monitor
ssh_profiles:
  mini:
    host: mini
    user: your-user

tabs:
  - name: project-a
    panes:
      - title: planner
        source: remote
        ssh_profile: mini
        tmux_target: solar:0.0
        mode: capture
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

六、必须复用的现有资产

当前 Solar/harness 已有可复用能力：
- remote dispatch doctor / ssh / tmux / remote pane health 资产
- 大量 `tmux capture-pane` 使用与验证逻辑
- monitor 相关入口
- 远程 mac mini 相关 dispatch/doctor 文档与脚本

因此要求：
1. 优先复用现有 tmux/ssh/doctor 资产
2. 不要重复再做一套独立 remote health checker
3. 不要把这张单做成“重写 remote dispatch”

七、验收标准

AC1. 能通过一个配置文件定义多个 tabs，每个 tab 最多 4 pane。
AC2. 4-pane 布局默认平均分屏幕空间。
AC3. 每个 pane 能显示本地或远程 tmux pane 的运行状态。
AC4. 远程模式优先通过 `capture-pane` 镜像，日志模式支持 `pipe-pane + tail -F`。
AC5. 支持 SSH 复用，避免 4 pane 重复完整认证。
AC6. 有 doctor/health 检查，能提示：ssh/tmux/target pane/log path 是否可用。
AC7. 启停脚本和样例配置完整，用户不需要手工拼 4 条命令。
AC8. 文档明确说明：
- 为什么不直接 attach 单个 remote tmux pane
- capture 模式 vs tail 模式的适用场景
- 第一阶段 non-goals

八、非目标

1. 第一阶段不追求 cmux 原生远程 tmux pane 一等公民 attach。
2. 第一阶段不追求复杂 TUI（vim/top/htop）完美渲染。
3. 第一阶段不做可写交互控制面，只做状态显示优先。
4. 第一阶段不重做 remote dispatch、Mirage、operator runtime。

九、交付要求

请输出：
1. requirements
2. architecture
3. config schema / sample config
4. launch scripts design
5. doctor / health design
6. rollout / risks / non-goals
7. builder checklist

一句话定性：
这是一个 `cmux + ssh + tmux capture/pipe` 的多标签四分屏状态监控工作台，不是交互式 remote pane attach 系统。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260531-cmux-多标签四分屏-tmux-状态监控工作台.epic.md`、`epic-20260531-cmux-多标签四分屏-tmux-状态监控工作台.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.design.md`
- `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.plan.md`
- `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.task_graph.json`
- `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.handoff.md`
- `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.eval.md` 或 `sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime.eval.json`
