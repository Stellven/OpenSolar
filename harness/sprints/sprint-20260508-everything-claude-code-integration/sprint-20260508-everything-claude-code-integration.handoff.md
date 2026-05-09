# Handoff — sprint-20260508-everything-claude-code-integration
Builder: 建设者化身
Round: 1

## 变更文件

- `lib/everything_claude_code_adapter.py`: 新增 S1 env overrides (ECC_HOME_OVERRIDE/ECC_STAGING/ECC_RUN_DIR), S2 sync-allowlisted 命令, S3 rollback 命令; 保留原有 doctor/inventory/install-dry-run/report 命令完整
- `solar-harness.sh`: everything-claude-code case 新增 sync 和 rollback 子命令 (line ~1845)
- `tests/test-everything-claude-code-integration.sh`: 新建，22 个测试覆盖 A1-A7

## Done 定义达成

### A1 - Source Is Vendored But Not Activated
✅ `test -d vendor/everything-claude-code/.git` passes  
✅ `git -C vendor/everything-claude-code rev-parse HEAD` = `841beea45cb25ba51f29fa45b7e272938d19b80a`  
✅ 零 live config 变更 (所有操作只写 staging/run dirs)

### A2 - Inventory Covers Every Upstream Surface
✅ `solar-harness everything-claude-code inventory --json` 包含 agents/commands/skills/hooks/rules/mcp_configs/scripts/tests 全部 8 个 surface key  
✅ 计数与 status.json 中 evidence 一致: agents=80 commands=117 skills=61 hooks=72 rules=130 mcp_configs=2 scripts=157 tests=117

### A3 - Collision Analysis Is Mandatory
✅ `install-dry-run --json` 包含 `collisions` 列表、`gstack` 和 `superpowers` compatibility key  
✅ 碰撞数 = 41 (status.json evidence 一致)

### A4 - No Global Hook Activation Without Review
✅ `install-dry-run --json` 的 `live_hook_changes == 0`  
✅ sync-allowlisted 只写 ECC_STAGING (默认 vendor/everything-claude-code-staging), 不接触 ~/.claude  
✅ blocked_by_default 列表阻止 hooks/mcp_configs 被 sync

### A5 - Allowlisted Sync Is Idempotent And Reversible
✅ `bash tests/test-everything-claude-code-integration.sh --case sync-rollback` PASS=22 FAIL=0  
✅ 第一次 sync 复制 1 个 skill 到 staging  
✅ 第二次 sync 跳过 (identical hash), copied=0  
✅ rollback 删除新增文件, manifest 归档为 sync-rolled-back-*.json  
✅ 幂等性: 微秒精度时间戳防止 manifest 覆盖

### A6 - Status Server Shows Candidate State
✅ `solar-harness integrations status --json` 包含 `affaan-m/everything-claude-code`  
✅ status = `"warn"` (installed=true, configured=true, running=false, used_by_default=false)  
✅ external-integrations-health.py 已预先实现此条目

### A7 - Tests Are Local And Safe
✅ 全部 22 个测试通过 PASS=22 FAIL=0  
✅ 测试使用 mktemp 临时目录 + ECC_STAGING/ECC_RUN_DIR/ECC_HOME_OVERRIDE 隔离  
✅ 不需要真实 Claude plugin install 或外部 credentials  
✅ trap 'rm -rf "$TMP"' EXIT 确保清理

## 验证方法

```bash
# 完整测试套件 (A1-A7)
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh

# A5 单独跑
bash /Users/sihaoli/.solar/harness/tests/test-everything-claude-code-integration.sh --case sync-rollback

# A2 验证
solar-harness everything-claude-code inventory --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert all(k in d["counts"] for k in ["agents","commands","skills","hooks","rules","mcp_configs","scripts","tests"]); print("ok")'

# A3/A4 验证
solar-harness everything-claude-code install --dry-run --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); assert "collisions" in d and "gstack" in d["compatibility"] and d["live_hook_changes"]==0; print("ok")'

# A6 验证
solar-harness integrations status --json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); item=[x for x in d["integrations"] if "everything-claude-code" in x["name"]][0]; assert item["status"] in ("warn","missing"); print(item["status"])'

# sync CLI (手动测试)
solar-harness everything-claude-code sync \
  --allowlist /Users/sihaoli/.solar/harness/config/everything-claude-code.allowlist.json \
  --dry-run --json

# rollback CLI (手动测试)
solar-harness everything-claude-code rollback --json
```

## 备注

- `everything-claude-code.allowlist.json` 保持保守默认 (allowed 全空), 不实际 sync 任何文件到 staging — 需要人工审核后加入具体 key 才会 sync
- `ECC_HOME_OVERRIDE` 仅影响 COLLISION_TARGETS 的 HOME 路径,不影响 HARNESS/VENDOR 路径 (防止测试时误改 VENDOR 指向)
- now_compact() 使用微秒精度 (%f) 防止同一秒内多次 sync 覆盖 manifest
- solar-harness.sh 的 sync 子命令解析 `--allowlist` 标志后传给 adapter; rollback 直接透传所有参数
