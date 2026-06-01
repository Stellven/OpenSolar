# Handoff — sprint-20260531-cmux-多标签四分屏-tmux-状态监控工作台-s03-core-runtime

Builder: 建设者化身 (claude-sonnet)
Round: 1

## 变更文件

| 文件 | 描述 |
| --- | --- |
| `scripts/cmux/render-cmux-workspace` | workspace yaml loader + 布局渲染器，输出命令计划（JSON/human-readable） |
| `scripts/cmux/tmux-pane-view` | capture-pane 轮询脚本，fail-open，带时间戳/host/target |
| `scripts/cmux/tmux-pane-log-follow` | tail -F 模式统一入口，支持 local/remote，可校验 tmux target |
| `scripts/cmux/cmux-monitor-up` | 调用 render → 构建 cmux JSON layout → 启动工作台 |
| `scripts/cmux/cmux-monitor-down` | 安全关闭工作台（list-workspaces 确认后关闭） |
| `scripts/cmux/cmux-monitor-doctor` | machine-verifiable JSON health check |
| `config/cmux-workspace-sample.yaml` | 样例配置：local quad + tail + remote 注释模板 |
| `docs/cmux-monitoring-workspace.md` | 用户文档 |
| `harness/tests/cmux/test_render_workspace.py` | 12 项单测 |
| `harness/tests/cmux/__init__.py` | 测试包 init |

## Done 定义达成

### R1_workspace_renderer (G1)

1. **tabs/panes schema 可解析** ✅
   - `render-cmux-workspace config/cmux-workspace-sample.yaml` → 2 tabs，6 panes，JSON 输出正确
   - 测试：`test_single_pane_single_layout`, `test_quad_layout_2x2_output` 通过

2. **每 tab 最多 4 panes** ✅
   - 超出 4 panes 时 exit 1 + 错误信息含 "max"/"4"
   - 测试：`test_quad_requires_at_most_4_panes` 通过

3. **quad 默认 2x2 等分** ✅
   - layout=quad → 4 panes，cmux-monitor-up 生成嵌套 horizontal/vertical split 各 0.5
   - 测试：`test_quad_layout_2x2_output` 通过

### R2_capture_tail_scripts (G2)

4. **tmux-pane-view 可表达 capture mode** ✅
   - 命令：`tmux-pane-view solar-harness:0.0 60 2`
   - fail-open：capture-pane 失败时打印 WARN + 继续轮询
   - 测试：`test_capture_command_local`, `test_capture_command_remote` 通过

5. **tmux-pane-log-follow 可表达 tail mode** ✅
   - 本地：`tail -F ~/.solar/harness/.chain-watcher.log`
   - 远程：`ssh lisihao@mini 'tail -F /path/to.log'`
   - 测试：`test_tail_command_local` 通过

6. **失败时有可读错误输出** ✅
   - 缺少 ssh_profile / log_path 时 exit 1 + 明确错误信息
   - 测试：`test_remote_pane_requires_ssh_profile`, `test_tail_mode_requires_log_path` 通过

### R3_doctor_lifecycle (G3)

7. **doctor 覆盖 ssh/tmux/target pane/log path** ✅
   ```
   python3 scripts/cmux/cmux-monitor-doctor config/cmux-workspace-sample.yaml
   → {"ok": true, "workspace": "solar-runtime", "checks": [... 10 checks all ok]}
   ```

8. **ssh reuse 建议与检查存在** ✅
   - doctor 对 `control_master: true` 的 profile 检查 ControlMaster socket 是否存在
   - SSH reuse 配置示例在 docs/ 中

9. **up/down 生命周期可回放** ✅
   ```
   python3 scripts/cmux/cmux-monitor-up config/cmux-workspace-sample.yaml --dry-run
   → DRY-RUN: would launch workspace 'solar-runtime' with 2 tab(s)

   python3 scripts/cmux/cmux-monitor-down --dry-run --name solar-runtime
   → DRY-RUN: would close workspace 'solar-runtime'
   ```

### R4_handoff_eval (G4)

10. **handoff 写明 sample config / launch / doctor / risks** ✅ (本文档)

11. **eval 需要真实命令或 smoke 证据** ✅ (见"验证方法"部分)

12. **non-goals 再确认** ✅ (见 docs/ + 合约)

## 样例配置路径

`config/cmux-workspace-sample.yaml` — 包含：
- local quad 2x2（4个 capture panes 监控 solar-harness:0.{0,1,2,3}）
- local tail split（2个 tail panes 监控 .chain-watcher.log + session-state.jsonl）
- remote 模板（注释掉，按需启用）

## 验证命令

```bash
cd /Users/lisihao/.solar/harness

# 运行所有单测
/Users/lisihao/Library/Python/3.9/bin/pytest harness/tests/cmux/ -v
# 期望: 12 passed

# 渲染验证
python3 scripts/cmux/render-cmux-workspace config/cmux-workspace-sample.yaml
python3 scripts/cmux/render-cmux-workspace config/cmux-workspace-sample.yaml --validate-only
# 期望: "OK: 2 tabs validated"

# Doctor 健康检查
python3 scripts/cmux/cmux-monitor-doctor config/cmux-workspace-sample.yaml; echo "exit=$?"
# 期望: {"ok": true, ...} exit=0

# Up/Down dry-run
python3 scripts/cmux/cmux-monitor-up config/cmux-workspace-sample.yaml --dry-run
python3 scripts/cmux/cmux-monitor-down --dry-run --name solar-runtime
```

## 已知残余风险

1. `cmux-monitor-up/down` 真实启动需要 cmux 支持 `list-workspaces --json` API（已做 fallback）
2. Doctor remote SSH check 会真实发起连接，适合手动或 CI 环境
3. Python 3.9 不支持 `str | None`，已改为无类型注解
4. `capture-pane` 对复杂 curses TUI 显示不完美（架构级已知限制）

## Non-Goals 再确认

- ❌ 复杂 TUI 完美渲染
- ❌ 可写交互控制面
- ❌ 重做 remote dispatch
- ❌ remote tmux pane attach 协议层
