# Solar Skills Install Protocol

> For AI agents installing optional third-party skills after the base Solar install.

Solar does not require third-party skills to complete the base install. `./install.sh` copies repository-bundled skills from `skills/` into `~/.claude/skills/`. This document is only for optional skill expansion.

---

## Rules for the installing agent

1. Do not install optional third-party repositories without asking the user first.
2. Do not delete or overwrite the user's existing skills.
3. Do not claim success without checking the installed paths.
4. Do not use `sudo` or root.
5. If a git clone fails, report the error and ask whether to retry with a proxy/mirror.
6. Keep all installations under `~/.claude/skills/` unless the user explicitly asks otherwise.

---

## Preflight

```bash
# Solar base install should already be present
test -f ~/.claude/CLAUDE.md && echo "Solar core present" || echo "Run: cd ~/Solar && ./install.sh"

test -d ~/.claude/skills && echo "Skills directory present" || mkdir -p ~/.claude/skills

which git && git --version | head -1
```

Stop if `git` is missing.

---

## What is already installed by Solar

Base install copies the repository's bundled skills:

```bash
cd ~/Solar
find skills -maxdepth 2 -type f | head
ls ~/.claude/skills | head
```

The exact number of bundled skills can change with the repository. Do not hard-code a count in user reports.

---

## Optional Pack A — Karpathy-style programming skills

Ask first:

```text
Do you want to install the optional Karpathy-style programming skill pack into ~/.claude/skills/?
```

Install only after approval:

```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
if [ -d .karpathy-tmp ]; then
  rm -rf .karpathy-tmp
fi
git clone --depth=1 https://github.com/forrestchang/andrej-karpathy-skills.git .karpathy-tmp
if [ -d .karpathy-tmp/skills ]; then
  cp -Rn .karpathy-tmp/skills/* ~/.claude/skills/
else
  cp -Rn .karpathy-tmp/* ~/.claude/skills/
fi
rm -rf .karpathy-tmp
```

Check:

```bash
ls ~/.claude/skills | grep -E "python|review|debug|test" | head || true
```

---

## Optional Pack B — Claude Code built-in skills

Claude Code may already ship its own skills. Link/copy only after user approval.

```bash
for path in \
  /Applications/Claude.app/Contents/Resources/skills \
  "$HOME/Library/Application Support/Claude/skills" \
  "$HOME/.config/claude/skills"; do
  if [ -d "$path" ]; then
    echo "Found Claude skills: $path"
  fi
done
```

If the user wants them installed:

```bash
mkdir -p ~/.claude/skills
for path in \
  /Applications/Claude.app/Contents/Resources/skills \
  "$HOME/Library/Application Support/Claude/skills" \
  "$HOME/.config/claude/skills"; do
  if [ -d "$path" ]; then
    cp -Rn "$path"/* ~/.claude/skills/ 2>/dev/null || true
  fi
done
```

---

## Optional Pack C — gstack setup

If `~/.claude/skills/gstack/setup` exists, it can be initialized after user approval:

```bash
if [ -f ~/.claude/skills/gstack/setup ]; then
  cd ~/.claude/skills/gstack
  ./setup
  echo "gstack setup complete"
else
  echo "gstack setup script not found; skip"
fi
```

Check:

```bash
find ~/.claude/skills/gstack -maxdepth 3 -type f | head 2>/dev/null || true
```

---

## Optional Pack D — Skill retriever MCP

This is optional and depends on the user's Claude Code MCP setup.

```bash
SKILL_MCP=$(find ~/.claude/core ~/.claude/mcp-servers -name "*skill-retriever*" -type d 2>/dev/null | head -1)
if [ -n "$SKILL_MCP" ]; then
  echo "Found skill retriever candidate: $SKILL_MCP"
else
  echo "No skill retriever MCP found; skip"
fi
```

If the user approves registration and `claude` CLI is available:

```bash
if [ -n "$SKILL_MCP" ] && command -v claude >/dev/null 2>&1; then
  cd "$SKILL_MCP"
  [ -f package.json ] && npm install --silent
  if [ -f main.js ]; then
    claude mcp add skill-retriever -- node "$SKILL_MCP/main.js"
  elif [ -f main.ts ]; then
    echo "main.ts found; compile/register manually according to this MCP package"
  fi
fi
```

---

## Optional third-party repositories

These should be installed only when the user explicitly asks for that domain:

| Domain | Example source | When to install |
|---|---|---|
| Claude API examples | `anthropics/claude-cookbooks` | User is developing Claude API apps. |
| Agent orchestration | LangGraph-related skills if available | User is building LangGraph/agent workflow demos. |
| ML experiments | MLflow-related materials if available | User is doing ML experiment tracking. |

Do not promise a fixed repository is maintained unless you have verified it at install time.

---

## Verification

```bash
echo "=== Solar Skills Summary ==="
test -d ~/.claude/skills && echo "skills_dir=ok" || echo "skills_dir=missing"
TOTAL=$(find ~/.claude/skills -maxdepth 1 -mindepth 1 2>/dev/null | wc -l | tr -d ' ')
echo "skill_entries=$TOTAL"

for s in gstack python-pro code-reviewer brainstorming writing-plans systematic-debugging; do
  [ -e ~/.claude/skills/$s ] && echo "present: $s" || true
done
```

A small number of skills is not a Solar install failure. Third-party skills are optional enhancements.

---

## Final report format

```text
Skills install report
- Base Solar skills: present/missing
- Optional Karpathy pack: installed/skipped/failed
- Optional Claude built-ins: installed/skipped/failed
- Optional gstack setup: done/skipped/failed
- Optional MCP registration: done/skipped/failed
- Total skill entries: N
- Failures: none / exact command + output
```

---

## Bottom line

Solar's base system should install and run without third-party skill packs. Use this protocol only to expand the available skill surface after the user approves the extra repositories or MCP registrations.
