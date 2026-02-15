# /http - API 快速测试

## 触发
- `/http GET <url>` - GET 请求
- `/http POST <url> <body>` - POST 请求
- `/http <url>` - 智能检测方法
- `/http test <url>` - 测试 API 健康
- `/http bench <url>` - 简单压测

## 执行

### 基础请求

```bash
# GET 请求
curl -s "$URL" | jq .

# POST JSON
curl -s -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d "$BODY" | jq .

# 带认证
curl -s -H "Authorization: Bearer $TOKEN" "$URL" | jq .

# 显示响应头
curl -sI "$URL"

# 显示完整信息 (响应码+时间)
curl -s -o /dev/null -w "Status: %{http_code}\nTime: %{time_total}s\n" "$URL"
```

### 带重试

```bash
# 重试 3 次，间隔 2 秒
for i in 1 2 3; do
  RESPONSE=$(curl -s -w "\n%{http_code}" "$URL")
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | sed '$d')

  if [ "$HTTP_CODE" -eq 200 ]; then
    echo "$BODY" | jq .
    break
  fi

  echo "Attempt $i failed ($HTTP_CODE), retrying..."
  sleep 2
done
```

### 断言检查

```bash
# 检查状态码
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
if [ "$STATUS" -eq 200 ]; then
  echo "✓ API 正常"
else
  echo "✗ API 异常: $STATUS"
fi

# 检查响应包含特定字段
RESPONSE=$(curl -s "$URL")
if echo "$RESPONSE" | jq -e '.data' > /dev/null 2>&1; then
  echo "✓ 包含 data 字段"
else
  echo "✗ 缺少 data 字段"
fi
```

### 简单压测

```bash
# 使用 ab (Apache Bench)
ab -n 100 -c 10 "$URL"

# 使用 hey (推荐)
brew install hey
hey -n 100 -c 10 "$URL"

# 简单循环测试
echo "发送 10 个请求..."
for i in $(seq 1 10); do
  TIME=$(curl -s -o /dev/null -w "%{time_total}" "$URL")
  echo "Request $i: ${TIME}s"
done
```

### HTTPie (更友好的 curl)

```bash
# 安装
brew install httpie

# GET
http GET "$URL"

# POST JSON
http POST "$URL" name=value

# 带认证
http "$URL" Authorization:"Bearer $TOKEN"
```

## 常用模板

| 场景 | 命令 |
|------|------|
| 快速 GET | `curl -s URL \| jq .` |
| POST JSON | `curl -sX POST URL -H "Content-Type: application/json" -d '{}'` |
| 检查状态 | `curl -sI URL \| head -1` |
| 下载文件 | `curl -O URL` |
| 带 Cookie | `curl -b "session=xxx" URL` |

## 输出格式

```
┌─ 🌐 HTTP Request ───────────────────────────────────────────────┐
│                                                                  │
│  Method: GET                                                     │
│  URL: https://api.example.com/users                              │
│                                                                  │
├─ Response ───────────────────────────────────────────────────────┤
│  Status: 200 OK                                                  │
│  Time: 0.234s                                                    │
│  Size: 1.2 KB                                                    │
│                                                                  │
│  Body:                                                           │
│  {                                                               │
│    "users": [                                                    │
│      {"id": 1, "name": "Alice"},                                 │
│      {"id": 2, "name": "Bob"}                                    │
│    ]                                                             │
│  }                                                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 环境变量

```bash
# 在 ~/.zshrc 或 ~/.solar/env 中设置
export API_BASE="https://api.example.com"
export API_TOKEN="your-token"

# 使用
curl -s -H "Authorization: Bearer $API_TOKEN" "$API_BASE/users"
```
