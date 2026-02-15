---
name: himalaya
description: "CLI email client (IMAP/SMTP)"
homepage: https://github.com/pimalaya/himalaya
metadata: {"moltbot":{"emoji":"📧","requires":{"bins":["himalaya"]}}}
---

# Himalaya Email CLI

## Quick Reference

| 操作 | 命令 |
|------|------|
| 列出文件夹 | `himalaya folder list` |
| 列出邮件 | `himalaya envelope list` |
| 指定文件夹 | `--folder "Sent"` |
| 搜索 | `envelope list from X subject Y` |
| 读取邮件 | `himalaya message read <ID>` |
| 回复 | `himalaya message reply <ID>` |
| 全部回复 | `himalaya message reply <ID> --all` |
| 转发 | `himalaya message forward <ID>` |
| 写邮件 | `himalaya message write` |
| 移动 | `himalaya message move <ID> "Archive"` |
| 删除 | `himalaya message delete <ID>` |
| 附件 | `himalaya attachment download <ID>` |
| JSON输出 | `--output json` |

## 配置

```toml
# ~/.config/himalaya/config.toml
[accounts.personal]
email = "you@example.com"
default = true

backend.type = "imap"
backend.host = "imap.example.com"
backend.port = 993
backend.auth.cmd = "pass show email/imap"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.example.com"
message.send.backend.port = 587
```

## 发送邮件

```bash
cat << 'EOF' | himalaya template send
From: you@example.com
To: recipient@example.com
Subject: Test

Hello!
EOF
```

## 多账户

```bash
himalaya --account work envelope list
```

详细文档: `himalaya --help`
