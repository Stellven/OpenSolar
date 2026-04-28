# GitHub 历史清理通知

## 发生了什么

在 **2026-04-28**，我们对 Solar 相关仓库的 git 历史执行了敏感信息清理操作。

## 清理内容

我们使用 `git filter-repo` 工具从 git 历史中删除了以下类型的敏感信息：

### 1. 删除的文件类型
- `.env` 文件及其所有变体（`.env.*`）
- OAuth 客户端密钥文件（`client_secret_*.json`）
- 凭证文件（`*credentials*.json`）
- 私有配置文件（`*-private.*`）

### 2. 替换的敏感内容
所有硬编码的 API 密钥已被替换为 `<REDACTED>` 占位符：
- **Anthropic API Keys**: `sk-ant-*` → `<REDACTED:ANTHROPIC_KEY>`
- **OpenAI API Keys**: `sk-or-*` → `<REDACTED:OPENAI_KEY>`
- **AWS Access Keys**: `AKIA*` → `<REDACTED:AWS_KEY>`
- **Zhipu AI Keys**: `ZHIPU_API_KEY` → `ZHIPU_API_KEY="<REDACTED>"`
- **DeepSeek Keys**: `DEEPSEEK_API_KEY` → `DEEPSEEK_API_KEY="<REDACTED>"`
- **Google API Keys**: `GOOGLE_API_KEY` → `GOOGLE_API_KEY="<REDACTED>"`
- **Email 地址**: `haogege1977@*` → `<REDACTED:EMAIL>`

## 影响范围

如果你 fork 了本仓库，你的 fork 会与上游 diverge（分叉）。

## 如何重新同步

如果你的本地 fork 或克隆受到影响，请按以下步骤重新同步：

1. **删除你的旧克隆**（或备份到其他位置）
2. **重新克隆本仓库**:
   ```bash
   git clone https://github.com/lisihao/Solar.git
   ```
3. **如果你有本地修改**，请先使用 `git fetch` + `git rebase` 而不是直接删除

## 历史时间线

- **2026-04-28 10:58 UTC**: 创建 mirror backup（`~/.solar/backups/*-pre-purge-*`）
- **2026-04-28 11:01 UTC**: 执行 `git filter-repo` 删除敏感文件
- **2026-04-28 11:02 UTC**: 执行 `git filter-repo --replace-text` 替换硬编码密钥
- **2026-04-28 11:05 UTC**: Force push 到 GitHub main 分支
- **2026-04-28 11:06 UTC**: 验证 GitHub 历史已清理

## 技术细节

使用的工具: `git filter-repo` v2.47.0

清理的仓库:
- `~/.claude` (https://github.com/lisihao/solar.git → 已迁移至 Solar.git)
- `~/Solar` (https://github.com/lisihao/Solar.git)
- `~/Solar-MAX` (https://github.com/lisihao/Solar.git)

## 验证

清理后，我们验证了以下内容：
- ✅ 本地工作树文件保持完整（`~/.zshrc`, `~/.solar/brain-router/.env` 等未删除）
- ✅ GitHub 历史中不再包含 `.env` 文件记录
- ✅ GitHub 历史中不再包含 `client_secret_*.json` 文件记录
- ✅ GitHub 历史中不再包含硬编码的 API 密钥

## 恢复

如有问题或需要恢复旧历史，请联系维护者。Mirror backup 保留在 `~/.solar/backups/`。

---

**通知日期**: 2026-04-28
**执行者**: Solar Harness (sprint-20260428-110149)
**文档版本**: 1.0
