# /watch - 文件/目录监控

## 触发
- `/watch <路径>` - 监控文件或目录变化
- `/watch <路径> --run <命令>` - 变化时执行命令
- `/watch stop` - 停止所有监控
- `/watch list` - 列出当前监控

## 执行

### 使用 fswatch (推荐)

```bash
# 安装 (如果没有)
brew install fswatch

# 监控目录，变化时执行命令
fswatch -o $PATH | xargs -n1 -I{} $COMMAND

# 监控 src 目录，变化时运行 build
fswatch -o ./src | xargs -n1 -I{} npm run build

# 监控特定文件类型
fswatch -e ".*" -i "\\.ts$" ./src | xargs -n1 -I{} echo "TS file changed"
```

### 使用 entr (轻量级)

```bash
# 安装
brew install entr

# 监控文件列表，变化时执行
find . -name "*.ts" | entr -r npm run dev

# 监控并重启服务
ls *.go | entr -r go run main.go
```

### 使用 nodemon (Node.js 项目)

```bash
# 安装
npm install -g nodemon

# 监控并重启
nodemon --watch src --ext ts,js --exec "npm run dev"
```

### 后台运行

```bash
# 后台启动监控
nohup fswatch -o ./src | xargs -n1 -I{} npm run build > ~/.solar/logs/watch.log 2>&1 &
echo $! > ~/.solar/watch.pid

# 停止
kill $(cat ~/.solar/watch.pid)
```

## 常用场景

| 场景 | 命令 |
|------|------|
| 前端热重载 | `fswatch -o ./src \| xargs -n1 npm run build` |
| Go 开发 | `ls *.go \| entr -r go run .` |
| 测试自动运行 | `fswatch -o ./test \| xargs -n1 npm test` |
| 文档生成 | `fswatch -o ./docs \| xargs -n1 npm run docs` |
| 日志监控 | `tail -f ~/.solar/logs/*.log` |

## 输出格式

```
┌─ 👁️ Watch ──────────────────────────────────────────────────────┐
│                                                                  │
│  监控路径: ./src                                                 │
│  触发命令: npm run build                                         │
│  状态: 运行中 (PID: 12345)                                       │
│                                                                  │
│  最近事件:                                                       │
│  10:23:15  src/index.ts 变更 → build 成功                        │
│  10:25:32  src/utils.ts 变更 → build 成功                        │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 注意事项

- macOS 推荐 fswatch (原生 FSEvents)
- 大目录用 `--exclude` 排除 node_modules
- 后台运行记得保存 PID
