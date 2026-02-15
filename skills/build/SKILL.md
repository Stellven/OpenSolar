---
name: build
description: 构建项目
user-invocable: true
context: fork
agent: ops
---

# 项目构建

使用 Ops Agent 构建项目。

## 自动检测构建系统

- CMake: `cmake --build build --config Release`
- Make: `make -j$(nproc)`
- npm: `npm run build`
- Cargo: `cargo build --release`
- Go: `go build ./...`

## 步骤

1. 检测构建系统
2. 创建构建目录 (如需要)
3. 运行构建命令
4. 验证构建产物
5. 报告结果

## 输出格式

```
构建结果: [成功/失败]
├── 构建系统: CMake
├── 构建类型: Release
├── 耗时: X.XX 秒
└── 产物: build/libxxx.a
```
