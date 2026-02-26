# 小爱自检清单 (XiaoAi Self-Check Checklist)

> **用途**: 每次从 GitHub 拉取、同步到新机器、新安装后执行
> **目的**: 确保 AI 秘书小爱功能完整可用
> **更新**: 2026-02-18

---

## 一、OpenClaw 安装检查

### 1.1 核心安装

```bash
# 检查 OpenClaw 安装
check_openclaw() {
  echo "=== OpenClaw 安装检查 ==="

  # 检查 openclaw 命令
  if command -v openclaw &> /dev/null; then
    version=$(openclaw --version 2>/dev/null | head -1)
    echo "✓ OpenClaw: $version"
  else
    echo "✗ OpenClaw 未安装"
    echo "  安装命令: npm install -g @anthropic/openclaw"
    return 1
  fi

  # 检查配置目录
  if [ -d "$HOME/.openclaw" ]; then
    count=$(ls ~/.openclaw 2>/dev/null | wc -l | tr -d ' ')
    echo "✓ ~/.openclaw 存在 ($count 项)"
  else
    echo "✗ ~/.openclaw 不存在"
    echo "  初始化命令: openclaw setup"
  fi
}

check_openclaw
```

**验收标准**:
- [ ] openclaw 命令存在
- [ ] 版本 ≥ 2026.2
- [ ] ~/.openclaw 目录存在

### 1.2 配置文件

```bash
# 检查配置文件
check_config() {
  echo "=== 配置文件检查 ==="

  configs=(
    "$HOME/.openclaw/openclaw.json"
    "$HOME/.openclaw/agents"
    "$HOME/.openclaw/credentials"
  )

  for f in "${configs[@]}"; do
    if [ -e "$f" ]; then
      echo "✓ $f"
    else
      echo "✗ $f (缺失)"
    fi
  done

  # 检查 openclaw.json 关键配置
  if [ -f "$HOME/.openclaw/openclaw.json" ]; then
    echo ""
    echo "=== 关键配置检查 ==="

    # 检查模型配置
    if grep -q "glm-4.7\|glm-5" ~/.openclaw/openclaw.json 2>/dev/null; then
      echo "✓ GLM 模型已配置"
    else
      echo "⚠ GLM 模型未配置"
    fi

    # 检查 Gateway
    if grep -q '"mode".*"local"' ~/.openclaw/openclaw.json 2>/dev/null; then
      echo "✓ Gateway 模式: local"
    else
      echo "⚠ Gateway 模式未设置"
    fi
  fi
}

check_config
```

**验收标准**:
- [ ] openclaw.json 存在
- [ ] agents 目录存在
- [ ] GLM 模型已配置

---

## 二、模型配置检查

### 2.1 GLM API 密钥

```bash
# 检查 GLM API 密钥
check_glm_key() {
  echo "=== GLM API 密钥检查 ==="

  # 检查环境变量
  if [ -n "$ZHIPU_API_KEY" ]; then
    key="$ZHIPU_API_KEY"
    len=${#key}
    prefix=$(echo "$key" | cut -c1-8)
    suffix=$(echo "$key" | tail -c 5)
    echo "✓ ZHIPU_API_KEY (${prefix}...${suffix}, ${len} chars)"
  else
    echo "✗ ZHIPU_API_KEY 未设置"
    echo "  获取地址: https://open.bigmodel.cn/"
    return 1
  fi

  # 测试 API 连通性
  echo ""
  echo "=== API 连通性测试 ==="
  # 简单测试 - 调用小爱
  result=$(openclaw agent --local --agent main --message "回复OK" 2>/dev/null | head -3)
  if echo "$result" | grep -q "OK\|ok"; then
    echo "✓ GLM API 连通正常"
  else
    echo "✗ GLM API 连通失败"
    echo "  返回: $result"
  fi
}

check_glm_key
```

**验收标准**:
- [ ] ZHIPU_API_KEY 已设置
- [ ] API 连通测试通过

### 2.2 模型配置

```bash
# 检查模型配置
check_model_config() {
  echo "=== 模型配置检查 ==="

  if [ -f "$HOME/.openclaw/openclaw.json" ]; then
    # 提取主模型
    primary=$(cat ~/.openclaw/openclaw.json | grep -o '"primary"[^,}]*' | head -1)
    echo "主模型: $primary"

    # 提取所有模型
    echo ""
    echo "已配置模型:"
    cat ~/.openclaw/openclaw.json | grep -oE '"zai/[a-z0-9.-]+"' | sort -u
  else
    echo "✗ openclaw.json 不存在"
  fi
}

check_model_config
```

**验收标准**:
- [ ] 主模型已设置 (推荐: glm-4.7 或 glm-5)
- [ ] 至少 1 个模型已配置

---

## 三、邮件服务 (Himalaya)

### 3.1 Himalaya 安装

```bash
# 检查 Himalaya
check_himalaya() {
  echo "=== Himalaya 邮件服务 ==="

  # 检查安装
  if command -v himalaya &> /dev/null; then
    version=$(himalaya --version 2>/dev/null | head -1)
    echo "✓ Himalaya: $version"
  else
    echo "✗ Himalaya 未安装"
    echo "  安装命令: brew install himalaya"
    return 1
  fi

  # 检查配置
  if [ -f "$HOME/.config/himalaya/config.toml" ]; then
    echo "✓ 配置文件存在"
    # 检查账户数
    accounts=$(grep -c "\[accounts\." ~/.config/himalaya/config.toml 2>/dev/null || echo 0)
    echo "  已配置账户: $accounts 个"
  else
    echo "✗ 配置文件不存在"
    echo "  配置路径: ~/.config/himalaya/config.toml"
  fi

  # 测试连接
  echo ""
  echo "=== 邮件连接测试 ==="
  if himalaya list -s 1 2>/dev/null | head -3 | grep -q "@"; then
    echo "✓ 邮件读取正常"
  else
    echo "⚠ 邮件读取失败或无邮件"
  fi
}

check_himalaya
```

**验收标准**:
- [ ] Himalaya 已安装
- [ ] config.toml 存在
- [ ] 至少 1 个邮箱已配置
- [ ] 邮件读取测试通过

---

## 四、提醒服务 (Apple Reminders)

### 4.1 Remindctl 安装

```bash
# 检查 Remindctl
check_remindctl() {
  echo "=== Apple Reminders 服务 ==="

  # 检查安装
  if command -v remindctl &> /dev/null; then
    echo "✓ remindctl 已安装"
  else
    echo "✗ remindctl 未安装"
    echo "  安装命令: brew tap himalaya-dev/tap && brew install remindctl"
    return 1
  fi

  # 测试访问
  echo ""
  echo "=== 提醒列表测试 ==="
  if remindctl list lists 2>/dev/null | head -5; then
    echo "✓ 提醒访问正常"
  else
    echo "⚠ 提醒访问可能需要授权"
    echo "  请在 系统设置 > 隐私与安全 > 提醒事项 中授权"
  fi
}

check_remindctl
```

**验收标准**:
- [ ] remindctl 已安装
- [ ] 提醒列表可读取

---

## 五、任务管理 (Things 3)

### 5.1 Things CLI 安装

```bash
# 检查 Things CLI
check_things() {
  echo "=== Things 3 任务管理 ==="

  # 检查安装
  if command -v things &> /dev/null; then
    echo "✓ things CLI 已安装"
  else
    echo "✗ things CLI 未安装"
    echo "  安装命令: brew install things-cli"
    return 1
  fi

  # 检查 Things 应用
  if [ -d "/Applications/Things3.app" ]; then
    echo "✓ Things 3 应用已安装"
  else
    echo "⚠ Things 3 应用未找到"
  fi

  # 测试连接
  echo ""
  echo "=== Things 连接测试 ==="
  today=$(things today 2>/dev/null | head -5)
  if [ -n "$today" ]; then
    echo "✓ Things 连接正常"
    echo "$today"
  else
    echo "⚠ Things 连接失败或无今日任务"
  fi
}

check_things
```

**验收标准**:
- [ ] things CLI 已安装
- [ ] Things 3 应用已安装
- [ ] Things 连接测试通过

---

## 六、Apple Shortcuts

### 6.1 Shortcuts 可用性

```bash
# 检查 Shortcuts
check_shortcuts() {
  echo "=== Apple Shortcuts ==="

  # 检查命令
  if command -v shortcuts &> /dev/null; then
    echo "✓ shortcuts 命令可用"
  else
    echo "✗ shortcuts 命令不可用"
    return 1
  fi

  # 统计快捷指令
  count=$(shortcuts list 2>/dev/null | wc -l | tr -d ' ')
  echo "  已创建快捷指令: $count 个"

  # 检查 Solar 相关快捷指令
  echo ""
  echo "=== Solar 相关快捷指令检查 ==="

  solar_shortcuts=(
    "solar_set_reminder"
    "solar_get_weather"
    "solar_send_message"
    "solar_calendar_event"
    "solar_create_note"
  )

  existing=$(shortcuts list 2>/dev/null)
  for s in "${solar_shortcuts[@]}"; do
    if echo "$existing" | grep -qi "$s"; then
      echo "✓ $s"
    else
      echo "✗ $s (未创建)"
    fi
  done
}

check_shortcuts
```

**验收标准**:
- [ ] shortcuts 命令可用
- [ ] 快捷指令数 ≥ 50
- [ ] Solar 相关快捷指令存在 (可选)

---

## 七、小爱功能测试

### 7.1 基础功能测试

```bash
# 功能测试
test_xiaoai() {
  echo "=== 小爱功能测试 ==="

  # 1. 基础响应测试
  echo "1. 基础响应测试..."
  result=$(openclaw agent --local --agent main --message "回复OK确认你工作正常" 2>/dev/null)
  if echo "$result" | grep -q "OK\|ok"; then
    echo "   ✓ 基础响应正常"
  else
    echo "   ✗ 基础响应异常"
    echo "   返回: $result"
  fi

  # 2. 邮件功能测试 (仅检查 himalaya)
  echo "2. 邮件功能检查..."
  if command -v himalaya &> /dev/null; then
    echo "   ✓ 邮件工具可用"
  else
    echo "   ✗ 邮件工具不可用"
  fi

  # 3. 提醒功能测试
  echo "3. 提醒功能检查..."
  if command -v remindctl &> /dev/null; then
    echo "   ✓ 提醒工具可用"
  else
    echo "   ✗ 提醒工具不可用"
  fi

  # 4. 任务功能测试
  echo "4. 任务功能检查..."
  if command -v things &> /dev/null; then
    echo "   ✓ 任务工具可用"
  else
    echo "   ✗ 任务工具不可用"
  fi

  # 5. 快捷指令测试
  echo "5. 快捷指令检查..."
  if command -v shortcuts &> /dev/null; then
    echo "   ✓ 快捷指令可用"
  else
    echo "   ✗ 快捷指令不可用"
  fi
}

test_xiaoai
```

**验收标准**:
- [ ] 基础响应正常
- [ ] 邮件工具可用
- [ ] 提醒工具可用
- [ ] 任务工具可用
- [ ] 快捷指令可用

---

## 八、一键自检脚本

### 8.1 完整自检

```bash
#!/bin/bash
# xiaoai-self-check.sh - 小爱一键自检

echo "╭─────────────────────────────────────────────────────────────────╮"
echo "│                    💝 小爱 (XiaoAi) 系统自检                    │"
echo "│                    $(date '+%Y-%m-%d %H:%M:%S')                            │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo ""

echo "━━━━ 一、OpenClaw 安装 ━━━━"
check_openclaw
echo ""

echo "━━━━ 二、模型配置 ━━━━"
check_glm_key
echo ""

echo "━━━━ 三、邮件服务 ━━━━"
check_himalaya
echo ""

echo "━━━━ 四、提醒服务 ━━━━"
check_remindctl
echo ""

echo "━━━━ 五、任务管理 ━━━━"
check_things
echo ""

echo "━━━━ 六、快捷指令 ━━━━"
check_shortcuts
echo ""

echo "━━━━ 七、功能测试 ━━━━"
test_xiaoai
echo ""

echo "├─────────────────────────────────────────────────────────────────┤"
echo "│  自检完成！请检查上方 ✗ 项并修复                                │"
echo "╰─────────────────────────────────────────────────────────────────╯"
```

---

## 九、常见问题修复

### 9.1 问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| openclaw 未安装 | 未安装 CLI | `npm install -g @anthropic/openclaw` |
| GLM API 失败 | 密钥未设置 | 设置 `ZHIPU_API_KEY` 环境变量 |
| 邮件读取失败 | himalaya 未配置 | 编辑 `~/.config/himalaya/config.toml` |
| 提醒访问失败 | 权限未授权 | 系统设置 > 隐私 > 提醒事项 |
| Things 连接失败 | CLI 未安装 | `brew install things-cli` |
| 快捷指令失败 | 权限问题 | 系统设置 > 隐私 > 自动化 |

### 9.2 修复命令速查

```bash
# 安装 OpenClaw
npm install -g @anthropic/openclaw

# 初始化配置
openclaw setup

# 配置向导
openclaw configure

# 安装 Himalaya
brew install himalaya

# 安装 Remindctl
brew tap himalaya-dev/tap
brew install remindctl

# 安装 Things CLI
brew install things-cli

# 测试小爱
openclaw agent --local --agent main --message "测试"
```

---

## 附录：标准配置参考

### A. 小爱依赖清单

| 组件 | 用途 | 安装方式 |
|------|------|----------|
| OpenClaw | AI 秘书核心 | npm |
| GLM API | 模型服务 | bigmodel.cn |
| Himalaya | 邮件服务 | brew |
| Remindctl | 提醒服务 | brew |
| Things CLI | 任务管理 | brew |
| Shortcuts | 快捷指令 | 系统内置 |

### B. 环境变量清单

| 变量名 | 用途 | 获取地址 |
|--------|------|----------|
| ZHIPU_API_KEY | GLM API 密钥 | open.bigmodel.cn |

### C. 配置文件位置

| 文件 | 路径 |
|------|------|
| OpenClaw 主配置 | ~/.openclaw/openclaw.json |
| Himalaya 配置 | ~/.config/himalaya/config.toml |
| Agent 配置 | ~/.openclaw/agents/main/ |

### D. 小爱调用方式

```bash
# 基础调用
openclaw agent --local --agent main --message "任务"

# 后台运行
openclaw agent --local --agent main --message "任务" &

# 在 Claude 中调用
# Solar 会自动调用: /xiaoai 或说"小爱"/"呼叫小爱"
```

---

*XiaoAi Self-Check Checklist v1.0*
*创建于: 2026-02-18*
*维护者: Solar*
