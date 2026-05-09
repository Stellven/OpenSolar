# Handoff — sprint-20260507-symphony2
Builder: 建設者化身
Round: 2

## 變更文件

- `~/.solar/harness/lib/symphony/hooks.sh` (修改): 修復兩個安全缺陷
  - `perl alarm kill -$$` → `kill q(TERM), -getpgrp()` (正確發信號給進程組)
  - `env_allow` 空值不再注入 (只注入非空 host var)
- `~/.solar/harness/lib/symphony/workspace-manager.sh` (修改): 消除 do_create TOCTOU 競態
  - 移除先檢查後寫的雙步操作
  - 改用 `set -o noclobber` + O_EXCL 原子聲明 `.solar-sprint-id`

## Round 2 Fix 說明

### Fix 1: perl alarm kill -$$ → -getpgrp()

原代碼 `kill SIGTERM, -$$` 中 `$$` 是 perl 自身 PID，`-$$` 表示 "發送信號給 PID 為 $$ 的進程組"。
問題：perl 進程自己可能不是其子 bash 進程的進程組 leader，信號無法觸達。
修復：`-getpgrp()` 取得當前進程組 ID，確保 SIGTERM 送達整個 bash 子進程樹。

### Fix 2: do_create 原子聲明

原代碼：
```bash
if [[ -f "${ws_dir}/.solar-sprint-id" ]]; then return 0; fi
# ... (race window here) ...
echo "$sprint_id" > "${ws_dir}/.solar-sprint-id"
```
兩個並發 create 都可能通過第一個 if，然後都寫入同一個文件。

修復：
```bash
if ! ( set -o noclobber && echo "$sprint_id" > "$claim_file" ) 2>/dev/null; then
  echo "$ws_dir"; return 0  # already claimed
fi
```
bash noclobber 模式使用 O_EXCL 系統調用，由 OS 保證原子性。第二個並發 create 的 noclobber 寫入必定失敗，走冪等返回路徑。

### Fix 3 (MEDIUM): env_allow 空值過濾

原代碼對 env_allow 變量無條件注入 `VAR=`，可能讓 hook 以為 VAR 已設置。
修復：`[[ -n "$val" ]] &&` 過濾，只注入有值的變量。

## Done 定義達成

1. **D1** workflow-loader.py 解析 hooks: 段 ✅
2. **D2** workspace-manager.sh create 調用 pre_claim / post_claim ✅
3. **D3** workspace-manager.sh clean 調用 pre_release / post_release ✅
4. **D4** hooks.sh run_hook 強隔離 ✅
5. **D5** env_allow 白名單擴展 ✅
6. **D6** CLAUDECODE guard 修復 ✅
7. **D7** Sprint 1 14/14 無回歸 ✅
8. **D8** 文檔 + ADR ✅

## 验证方法

```bash
# D1
python3 ~/.solar/harness/lib/symphony/workflow-loader.py --validate ~/.solar/harness/templates/WORKFLOW.solar.md

# D2-D5 hook tests (8/8 PASS)
bash ~/.solar/harness/test-symphony-hooks.sh

# D6 guard tests (2/2 PASS)
bash ~/.solar/harness/test-symphony-d6-guard.sh

# D7 Sprint 1 regression (all PASS)
bash -c 'cd ~/.solar/harness && for t in test-symphony-issue-adapter.sh test-symphony-scheduler-dry-run.sh test-symphony-workspace.sh test-symphony-no-live-pane-mutation.sh; do bash $t; done'

# D8 ADR word count (≥200)
awk '/Hook Lifecycle Design/,/^## /{print}' ~/.solar/harness/docs/symphony-integration-adr.md | wc -w
```

## Round 2 修復的安全缺陷

| 缺陷 | 嚴重性 | 狀態 |
|------|--------|------|
| do_create TOCTOU 競態 | HIGH | ✅ 已修復 (O_EXCL atomic write) |
| perl alarm kill -$$ 進程組錯誤 | HIGH | ✅ 已修復 (getpgrp()) |
| env_allow 空值注入 | MEDIUM | ✅ 已修復 (non-empty guard) |

## 備注

- `set -o noclobber` 在 bash subshell 中使用，不影響 workspace-manager.sh 主 shell 的設置
- `getpgrp()` 在 macOS perl 5.x 可用，無需額外模塊
- perl fallback 仍無 5s SIGKILL grace period（gtimeout 有），生產環境建議 `brew install coreutils`
