# /sandbox - 沙箱安全执行

## 触发
- `/sandbox <命令>` - 在 Docker 沙箱中执行命令
- `/sandbox build` - 构建沙箱镜像
- `/sandbox check` - 检查沙箱状态
- `/sandbox history` - 执行历史

## 执行

### 在沙箱中运行

```bash
bun ~/.claude/core/sandbox/executor.ts run "$COMMAND"
```

### 构建沙箱镜像

```bash
bun ~/.claude/core/sandbox/executor.ts build
```

### 检查状态

```bash
bun ~/.claude/core/sandbox/executor.ts check
```

## 沙箱特性

### 安全限制

| 限制 | 默认值 | 说明 |
|------|--------|------|
| 内存 | 512MB | 防止内存耗尽 |
| CPU | 1 核 | 限制计算资源 |
| 进程数 | 100 | 防止 fork 炸弹 |
| 超时 | 60s | 防止无限循环 |
| 网络 | 禁用 | 防止数据泄露 |
| 文件系统 | 只读 | 防止系统破坏 |

### 自动触发

以下命令会自动在沙箱中执行:

- `rm -rf` 相关命令
- `curl | bash` / `wget | sh`
- `sudo` 命令
- `eval` / `exec`
- 涉及 `/dev/` 的操作

### 手动沙箱

对于不确定的命令，建议使用:

```bash
/sandbox <命令>
```

## 输出格式

```
┌─ 🔒 Sandbox Execution ──────────────────────────────────────────┐
│                                                                  │
│  Command: ls -la /tmp                                            │
│  Sandboxed: ✓                                                    │
│  Exit Code: 0                                                    │
│  Duration: 234ms                                                 │
│                                                                  │
├─ Output ─────────────────────────────────────────────────────────┤
│                                                                  │
│  total 0                                                         │
│  drwxrwxrwt 2 root root 40 Jan 15 10:30 .                        │
│  drwxr-xr-x 1 root root 40 Jan 15 10:30 ..                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 执行历史

```sql
SELECT command, exit_code, duration_ms, sandboxed, created_at
FROM sandbox_executions
ORDER BY created_at DESC
LIMIT 20;
```

## Docker 镜像

沙箱基于 Ubuntu 22.04，包含:
- bash, curl, wget, git, jq
- python3, pip
- nodejs, npm
- bun
- sqlite3

## 注意事项

1. **首次使用**需要构建镜像 (`/sandbox build`)
2. **无网络**访问，需要网络请在本地执行
3. **输出限制** 50KB，超出会截断
4. **工作目录**挂载到 `~/.solar/sandbox-workspace`

## 何时使用沙箱

| 场景 | 建议 |
|------|------|
| 运行用户提供的代码 | ✓ 强烈建议 |
| 执行不熟悉的脚本 | ✓ 建议 |
| 常规 git/npm 操作 | ✗ 不需要 |
| 读取文件 | ✗ 不需要 |
| 系统管理命令 | ✓ 建议 |
