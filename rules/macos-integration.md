# Solar 铁律: macOS 系统集成

> **来源: 2026-02-04 Mail Agent 开发的血泪教训**
> **问题: "简单"功能反复出错，暴露系统集成盲区**

## 铁律 1: osascript 必须双重重定向

```bash
# ❌ 错误: 只重定向 stderr
osascript -e "..." 2>/dev/null

# ✓ 正确: stdout 和 stderr 都重定向
osascript -e "..." >/dev/null 2>&1
```

**原因:** osascript 成功时返回 "true" 到 stdout

## 铁律 2: Bash while+pipe 必须用进程替换

```bash
# ❌ 错误: pipe 创建子进程，变量丢失
echo "$data" | while read line; do
    RESULT="$line"  # 子进程中修改，父进程看不到
done

# ✓ 正确: 进程替换，不创建子进程
while read line; do
    RESULT="$line"  # 当前进程中修改，全局可见
done < <(echo "$data")
```

## 铁律 3: AppleScript 字符串必须转义

```bash
# ❌ 错误: 直接拼接
osascript -e "tell app \"Mail\" to ... \"$content\" ..."

# ✓ 正确: 先转义
safe_content=$(echo "$content" | sed 's/\\/\\\\/g; s/"/\\"/g')
osascript -e "tell app \"Mail\" to ... \"$safe_content\" ..."
```

## 铁律 4: 可选参数必须有默认值

```bash
# ❌ 错误: 直接使用 $3
local attachment="$3"  # 如果没传，报 unbound variable

# ✓ 正确: 使用默认值
local attachment="${3:-}"
```

## 铁律 5: 系统集成必须分步验证

```
开发流程:
1. 单独测试每个函数 (send_imessage, send_email, etc.)
2. 验证返回值和副作用
3. 再进行端到端集成
4. 不要"写完直接跑"
```

## 常见 macOS 系统工具

| 工具 | 用途 | 注意事项 |
|------|------|----------|
| osascript | AppleScript 执行 | stdout 会输出返回值 |
| imagesnap | 摄像头拍照 | 需要 -w 延迟 |
| shortcuts | 快捷指令 | JSON 参数需转义 |
| himalaya | 邮件 CLI | 用 -o json 输出 |
| remindctl | 提醒事项 | 需要日期格式 |

## 反思总结

```
为什么 ThunderDuck 能一次搞通，Mail Agent 反复出错？

ThunderDuck:
  ✓ 深厚知识积累
  ✓ 明确技术边界
  ✓ 测试驱动闭环
  ✓ 确定性反馈

Mail Agent:
  ✗ 陌生领域盲区
  ✗ 系统集成复杂
  ✗ 补丁式开发
  ✗ 过度自信

教训:
  - 看起来简单 ≠ 实际简单
  - 系统集成的复杂度在"胶水代码"
  - 陌生领域要更谨慎，不能草率
  - 每次出错都要问"为什么"，不只是"怎么改"
```

---

*macOS Integration Rules v1.0*
*从 2026-02-04 Mail Agent 开发中学到*
*君子日省三次，才能进步*
