---
name: solar-obsidian-wiki-integration
description: Integrate Ar9av/obsidian-wiki as Solar Harness durable knowledge memory
triggers: [solar-harness wiki, obsidian, llm-wiki, vault, knowledge-base]
---

# Sprint Contract — sprint-20260507-obsidian-wiki

Created: 2026-05-07T20:31:16Z
Status: drafting
Phase: spec
Priority: P1
Lane: delivery
Source Repo: https://github.com/Ar9av/obsidian-wiki

## Goal

Add a Solar Harness integration for `Ar9av/obsidian-wiki` so Solar can configure an Obsidian LLM Wiki vault, export sprint artifacts into `_raw/`, and expose wiki install/status/update/query workflows without disrupting existing sprint automation.

## Source Facts

The upstream repo is a skill-based Obsidian knowledge framework. Its setup flow writes `~/.obsidian-wiki/config`, symlinks `.skills/*` into agent skill directories, and expects a vault containing `index.md`, `log.md`, `hot.md`, `.manifest.json`, `_raw/`, `projects/`, `concepts/`, `entities/`, `skills/`, `references/`, `synthesis/`, and `journal/`.

## Requirements

1. Add `solar-harness wiki` subcommands:
   - `install --vault <path> [--repo <path>] [--refresh]`
   - `status [--json]`
   - `export-sprint <sid> [--redact|--full]`
   - `update [--project <path>] [--mode append|full]`
   - `query "<question>" [--quick]`
2. Implement a non-interactive installer. Do not run upstream `setup.sh` in a way that prompts.
3. Store upstream repo under `~/.solar/harness/vendor/obsidian-wiki` by default, unless `--repo` is provided.
4. Write `~/.obsidian-wiki/config` with `OBSIDIAN_VAULT_PATH` and `OBSIDIAN_WIKI_REPO`.
5. Create/repair a minimal vault structure and files compatible with upstream `wiki-setup`.
6. Install safe symlinks for at least `~/.codex/skills`, `~/.claude/skills`, and `~/.agents/skills`. Never overwrite real directories.
7. Export Solar sprint artifacts to `$OBSIDIAN_VAULT_PATH/_raw/solar-harness/<sid>.md`.
8. Default export mode must redact likely secrets and avoid full raw terminal transcript dumps.
9. Add wiki readiness to the HTTP status server if present; integration absence must be `warn`, not fatal.
10. Include tests using a temp repo copy and temp vault; no real user vault mutation during tests.
11. Include operator docs with five usage examples.

## Definition of Done

- [ ] D1: `bash -n ~/.solar/harness/integrations/obsidian-wiki.sh ~/.solar/harness/solar-harness.sh` passes.
  <!-- verify: cmd="bash -n ~/.solar/harness/integrations/obsidian-wiki.sh ~/.solar/harness/solar-harness.sh" expected_exit=0 -->
- [ ] D2: `solar-harness wiki install --vault <temp>` creates config, vault skeleton, and safe skill symlinks.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh install" expected_exit=0 -->
- [ ] D3: `solar-harness wiki status --json` emits valid JSON with repo/config/vault/skills fields.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status" expected_exit=0 -->
- [ ] D4: `solar-harness wiki export-sprint sprint-20260507-symphony3` creates `_raw/solar-harness/<sid>.md` with frontmatter, source list, and redaction.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh export" expected_exit=0 -->
- [ ] D5: `wiki update/query` bridge produces agent-readable instruction files and refuses empty query strings.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh bridge" expected_exit=0 -->
- [ ] D6: status server response includes `obsidian_wiki` readiness when status server module is available.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh status_server" expected_exit=0 -->
- [ ] D7: Real-path safety: tests prove no real directories in skill destinations are overwritten.
  <!-- verify: cmd="HARNESS_TEST=1 bash ~/.solar/harness/test-obsidian-wiki-integration.sh safety" expected_exit=0 -->
- [ ] D8: Docs exist at `docs/obsidian-wiki-integration.md` with at least five examples.
  <!-- verify: cmd="test -f ~/.solar/harness/docs/obsidian-wiki-integration.md && grep -c '^### Example' ~/.solar/harness/docs/obsidian-wiki-integration.md | awk '$1>=5'" expected_exit=0 -->

## In Scope

- Thin Solar integration layer.
- Safe installer and status checks.
- Sprint artifact export into Obsidian raw staging.
- Docs/tests/status server visibility.
- Optional use of local upstream clone for tests.

## Out of Scope

- Rewriting upstream skills.
- Requiring QMD semantic search.
- Automating the Obsidian desktop app.
- Bulk ingesting all private histories by default.
- Changing current Solar sprint lifecycle semantics.

## Stop Rules

- If installer can overwrite a real directory, stop and redesign symlink logic.
- If tests need a real user vault, stop and add temp-vault mode.
- If implementation exceeds 900 lines total, split and simplify.
- If status server integration makes `solar-harness status-server` fail when wiki is absent, stop and fix degradation.

## Planner Instructions

Read the product brief and design first:

- `/Users/lisihao/.solar/harness/sprints/sprint-20260507-obsidian-wiki.product-brief.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260507-obsidian-wiki.design.md`

Then produce:

1. A build plan with file ownership by slice.
2. A safe test strategy using temp vaults.
3. A builder dispatch plan that does not interrupt an active reviewing sprint.

## Builder Instructions

Implement exactly against the DoD. Prefer shell + Python stdlib only. Use upstream repo as reference, not as code to paste wholesale. Keep commands idempotent and safe.

## Evaluation Dimensions

1. Functional completeness against D1-D8.
2. Safety of config, symlink, and vault writes.
3. Non-interference with Solar sprint automation.
4. Docs clarity and operator usability.

