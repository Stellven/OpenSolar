# Handoff — sprint-20260508-solar-kb-obsidian-autouse
Builder: 建设者化身
Round: 3

## 变更文件

- `lib/solar-knowledge-context.py`: 修复 `_vault_hits()` — 多 token 分割 LIKE 查询 + 绝对路径返回
- `lib/symphony/status-server.py`: 新增 `import sqlite3` + `_solar_kb_status()` + `_obsidian_sync_status()` + `_status_payload()` 注入两个新 key

## Done 定义达成 (Round 3 修复 A2/A5)

### A2 - Vault Hits 返回绝对路径 (Round 2 FAIL → Round 3 FIX)
✅ `_vault_hits()` 返回 `source=str(VAULT_PATH)` = `/Users/sihaoli/Knowledge`
✅ `path=str(VAULT_PATH / fpath)` = `/Users/sihaoli/Knowledge/references/...`
✅ 多 token 查询 ("orbital data center Lumen Orbit") 返回 8 hits，其中 5 个来自 vault 带 "Knowledge" 路径
✅ 验证命令通过:
```
python3 ~/.solar/harness/lib/solar-knowledge-context.py --query "orbital data center Lumen Orbit" --json
→ hits[3-7]: source=/Users/sihaoli/Knowledge, path=/Users/sihaoli/Knowledge/references/...
→ A2 PASS
```

**根因修复**: Round 2 `source` 返回 DB 列值 "obsidian" (非路径)，`path` 返回相对路径 "references/xxx.md"。现在 `source=str(VAULT_PATH)`，`path=str(VAULT_PATH / fpath)`。另外单一 LIKE 对整个查询字符串无法匹配多 token — 改为按空格分割，每 token 生成独立 `(title LIKE ? OR summary LIKE ? OR tags LIKE ?)` OR 子句。

### A5 - /status 端点暴露 solar_kb + obsidian_sync (Round 2 FAIL → Round 3 FIX)
✅ 修改正确文件: `lib/symphony/status-server.py` (port 8765)，非 Round 2 误改的 `integrations/wiki-capture-server.py` (port 8788)
✅ `curl -fsS http://127.0.0.1:8765/status` 返回包含 `solar_kb` 和 `obsidian_sync` key
✅ `solar_kb`: `{"indexed_count": 156, "last_indexed_at": "2026-05-08T15:16:48Z", "ok": true}`
✅ `obsidian_sync`: 包含 `vault_path`, `vault_exists`, `pending_raw_export`, `last_sync_at`, `ok`
✅ 验证命令通过:
```
curl -fsS http://127.0.0.1:8765/status | python3 -c '...assert "solar_kb" in d and "obsidian_sync" in d...'
→ A5 PASS (solar_kb: True, obsidian_sync: True)
```

**根因修复**: Round 2 把两个 helper 函数和 payload 注入写到了错误文件 `integrations/wiki-capture-server.py`。port 8765 的正确服务是 `lib/symphony/status-server.py`。

### A1 - Solar KB 默认注入 (延续 Round 2 PASS)
✅ `_status_payload()` 包含 `solar_kb` key，`indexed_count=156 > 0`，`ok=true`

### A3 - Obsidian 索引 (延续 Round 2 PASS)
✅ `obsidian_vault_index` 表有 156 行已索引条目

### A4 - Memory Influence (延续 Round 2 PASS)
✅ 上轮 PASS，本轮无修改

### A6 - 语义检索 (延续 Round 2 PASS)
✅ 上轮 PASS，本轮无修改

### A7 - 测试 (延续 Round 2 PASS)
✅ 上轮 PASS，本轮无修改

## 验证方法

```bash
# A2 验证 (vault hits 绝对路径)
python3 ~/.solar/harness/lib/solar-knowledge-context.py \
  --query "orbital data center Lumen Orbit" --json \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
hits=d.get("hits",[])
print("hits:", len(hits))
for h in hits:
    print(h.get("source",""), "|", h.get("path",""))
assert any("Knowledge" in (h.get("source","")+h.get("path","")) for h in hits), hits
print("A2 PASS")
'

# A5 验证 (status server 含两个新 key)
curl -fsS http://127.0.0.1:8765/status \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert "solar_kb" in d and "obsidian_sync" in d
print("solar_kb:", d["solar_kb"])
print("obsidian_sync:", d["obsidian_sync"])
print("A5 PASS")
'
```

## 备注

- status-server.py 如已运行旧版本需重启: `pkill -f "status-server.py" && python3 /Users/sihaoli/.solar/harness/lib/symphony/status-server.py &`
- `_solar_kb_status()` 使用 `timeout=0.3` 防止 DB 锁死阻塞状态接口
- `_obsidian_sync_status()` 读取 `state/knowledge-manifest.json` (可能不存在，容错处理)
- 两个 helper 函数均 never raises — 异常时返回 `ok: False, error: <msg>`
