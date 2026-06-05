# Solar

> **Autonomous Software Organization Runtime**  
> 让用户当老板，让 AI 组织自己完成软件工程。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Solar Core](https://img.shields.io/badge/Solar-Core-38bdf8.svg)](CLAUDE.md)
[![Solar Harness](https://img.shields.io/badge/Solar-Harness-8b5cf6.svg)](harness/)
[![AI Native](https://img.shields.io/badge/AI--Native-Execution%20Fabric-14b8a6.svg)](#solar-是什么)

Solar is an AI-native operating system prototype for long-running, evidence-driven software work. It is not a chatbot, not a prompt collection, and not a simple multi-agent demo. Solar treats natural language as the control surface, requirements as compilable artifacts, AI products as schedulable physical operators, and software delivery as evidence-gated DAG execution.

中文一句话：**Solar 把老板的一句话编译成一支 AI 组织的自主行动。**

---

## Solar 是什么

Solar 当前由三层组成：

| Layer | Directory | Role |
|---|---|---|
| **Solar Core** | `CLAUDE.md`, `agents/`, `skills/`, `rules/`, `hooks/`, `core/` | Claude/Codex-native workflow kernel: agents, skills, rules, hooks, persistent operating context. |
| **Solar Harness** | `harness/` | Requirement compiler, sprint control plane, DAG scheduler, worker lease, model fleet dispatch, evaluator, benchmark, and experience memory. |
| **Solar Knowledge** | `docs/`, `scripts/`, knowledge adapters, runtime-generated indices | Unified knowledge surface for docs, accepted artifacts, research evidence, and context maps. |

Solar 的核心价值观：

- **Human as Boss, not Runtime Glue** — 用户只表达目标、边界、预算和偏好。
- **AI manages AI** — Solar 负责需求澄清、任务分解、调度、打回、验收和汇报。
- **AI develops AI** — Solar 可以构建 skills、capsules、MCP、evaluators、reports 和代码产物。
- **AI optimizes AI** — Solar 通过 evidence、side-info、benchmarks、scorecards 和 Meta Harness 优化自己的策略。
- **Evidence defines completion** — 没有 handoff、eval、test、artifact 或 deterministic gate，就不能宣称完成。

---

## System Architecture

![Solar system architecture](docs/assets/solar-system-architecture.svg)

Solar does not treat a model as the unit of execution. It treats an **AI-capable execution surface** as the unit of execution.

That surface may be a Claude Code pane, a Codex instance, DeepSeek Reasonix, a browser session, Gemini/GPT Web, an API model, a local model, an MCP server, or a remote worker. Solar Harness wraps these surfaces as physical operators and schedules them through a single control plane.

---

## Solar Harness: the Control Plane

Solar Harness turns a user goal into a controlled software delivery flow:

```text
Boss Intent
  -> Executive Intent Contract
  -> Sprint Contract / PRD
  -> Plan + TaskGraph IR
  -> Capability Annotation
  -> Logical Operator DAG
  -> Physical Operator Binding
  -> Queue / Lease / Dispatch
  -> Handoff / Eval / Node Verdict
  -> Parent Gate
  -> Accepted Artifact / Experience Memory
```

Key primitives:

| Primitive | Meaning |
|---|---|
| **Sprint Contract** | A file-backed engineering contract: objective, scope, constraints, acceptance, owner intent. |
| **TaskGraph IR** | Machine-readable DAG with `depends_on`, `read_scope`, `write_scope`, `required_capabilities`, `gate`, and `acceptance`. |
| **Physical Operator** | A concrete execution surface: tmux pane, Claude Code, Codex, browser profile, API worker, remote shell, local process. |
| **Logical Operator** | Stable semantic work: compile requirement, build graph, implement code, run browser research, evaluate evidence, optimize artifact. |
| **Pane / Actor Lease** | Runtime ownership protocol to prevent multiple tasks from fighting over the same worker. |
| **Evidence ABI** | Handoff, eval, session log, deterministic gate, and accepted artifact schema. |
| **Meta Harness** | Self-optimization layer for prompts, policies, capsules, evaluators, and routing rules. |

---

## Logical Operators → Physical Operators

![Solar operator DAG runtime](docs/assets/solar-operator-dag.svg)

Solar separates **what to do** from **who executes it**.

Examples of logical operators:

- `CompileRequirement`
- `GeneratePRD`
- `BuildTaskGraph`
- `ImplementCode`
- `RunBrowserResearch`
- `EvaluateEvidence`
- `UpdateContextMap`
- `OptimizeArtifact`

Examples of physical operators:

- Claude Code interactive pane
- Codex instance
- DeepSeek Reasonix reasoning surface
- GPT / Gemini / DeepSeek browser session
- GLM / DeepSeek / Claude subscription worker
- API model worker
- local model process
- remote Mac mini / devbox worker
- deterministic Python verifier

Why this matters:

1. **Subscription-era AI has different economics** — Web/TUI products and monthly plans can be far more cost-efficient for long-running engineering work than pure API calls.
2. **Web AI surfaces often expose stronger product capabilities** — file handling, browser tools, multimodal UI, long context, workspace memory, and built-in agentic behavior may arrive before equivalent APIs.
3. **Code agents are already internal runtimes** — Claude Code and Codex are not simple LLM endpoints; each instance has its own planning, tool use, file editing, and execution loop.
4. **Scheduling should be about execution surfaces, not model names** — the planner should ask which surface is best for this logical operator under this cost, risk, context, and evidence requirement.

---

## Autonomous Software Organization Loop

![Solar autonomous loop](docs/assets/solar-autonomous-loop.svg)

Solar's long-term direction is an autonomous software organization runtime:

```text
Boss
  -> Boss Command Layer
  -> Requirement Compiler
  -> AI Organization Runtime
  -> Evidence Court
  -> Context + Experience Memory
  -> Meta Harness
  -> Better Solar
```

This is the operating model:

| Role | Responsibility |
|---|---|
| **Boss / Operator** | Sets goal, boundary, budget, risk tolerance, and final approval policy. |
| **PM** | Turns intent into requirements, acceptance, and non-goals. |
| **Planner** | Produces plan, architecture, TaskGraph IR, and capability plan. |
| **Scheduler** | Chooses ready nodes, batches safe parallel work, binds physical operators. |
| **Builder Fleet** | Implements, researches, tests, drafts, and produces artifacts. |
| **Evaluator** | Reads evidence, checks scope, verifies acceptance, and returns verdict + side-info. |
| **Autopilot** | Detects stuck work, stale leases, missing handoff, failed review, and safe repair actions. |
| **Meta Harness** | Optimizes templates, policies, capsules, evaluators, and routing based on replayable evidence. |

---

## What Solar can do today

| Capability | Status | Notes |
|---|---|---|
| Solar Core install | Available | Installs Claude/Codex-facing agents, rules, skills, hooks, and core files. |
| Solar Harness local runtime | Available | File-backed sprint contracts, coordinator, queues, leases, builder/evaluator flow. |
| TaskGraph DAG scheduling | Available | Dependency gating, write-scope batching, capability matching, parent-gate checks. |
| Multi-pane / TUI execution | Available | Product delivery panes plus builder lab style execution. |
| Model / operator registry | Available | Model aliases, physical operators, actors, hosts, capability/risk/cost profiles. |
| Evidence-native evaluation | Available | Handoff, eval, node verdict, session logs, deterministic research gates. |
| Remote worker path | Available / evolving | Remote sync, dispatch, monitor, and verification scripts are present. |
| Plugin framework | Available / evolving | Harness can load and validate `harness/plugins/<id>/manifest.yaml` when plugin manifests are present. The public repo does not need to ship enabled third-party plugins by default. |
| Solar-bundled skills | Available | Repository skills are copied into `~/.claude/skills/` by `install.sh`. Counts may change with the repo. |
| Third-party skills | Optional | Installed separately through `SKILLS-INSTALL.md`; they are an enhancement, not required for the base install. |
| Deep Research OS | Evolving | Evidence extraction, citation checking, research evaluation, and report gates. |
| Context Map / PEEK-style layer | Planned / integrating | Orientation cache for repos, topics, vaults, and long-running projects. |
| Meta Harness self-optimization | Planned / integrating | Optimizes text artifacts using evaluator score, side-info, replay, and promotion gates. |
| Hard sandbox / write enforcement | Planned | Current design uses scope, lease, evaluator, and guards; stronger filesystem enforcement is a priority. |

---

## Quick Start

### Human install

```bash
git clone https://github.com/lisihao/Solar.git ~/Solar
cd ~/Solar
./install.sh
```

What install does:

- copies Solar Core assets into `~/.claude/`;
- creates `~/.solar/`;
- syncs the published `harness/` source into `~/.solar/harness/` when present;
- copies optional packaged runtime components such as `mempalace/` and `codex-bridge/` when present;
- creates `~/.solar/bin/solar-harness`;
- runs L1 + L2 install verification.

### Agent install / deploy / self-check path

If you want Claude, Codex, Cursor, Copilot, or another code agent to install Solar for you, give it this exact instruction:

```text
Install Solar from https://github.com/lisihao/Solar using INSTALL-AGENT.md.
Follow the steps exactly. Before each command, report: purpose, command, and expected output.
Do not use sudo/root. Stop immediately on any failure and show the exact output.
After installation, run the L1 + L2 self-check:

cd ~/Solar && ./install.sh
~/.solar/bin/solar-harness help
cd ~/Solar && ./scripts/sync-harness-runtime.sh
~/.solar/bin/solar-harness help

If optional third-party skills are requested, use SKILLS-INSTALL.md, but do not install optional third-party skills without asking first.
```

Dedicated documents:

| Document | Purpose |
|---|---|
| [`INSTALL-AGENT.md`](INSTALL-AGENT.md) | Step-by-step install/deploy/self-check protocol for AI agents. |
| [`SKILLS-INSTALL.md`](SKILLS-INSTALL.md) | Optional skill expansion protocol for AI agents. |
| [`scripts/sync-harness-runtime.sh`](scripts/sync-harness-runtime.sh) | Syncs repository `harness/` into the local runtime `~/.solar/harness/`. |

### Harness runtime

```bash
cd ~/Solar
./scripts/sync-harness-runtime.sh
~/.solar/bin/solar-harness help
~/.solar/bin/solar-harness start
```

Runtime boundary:

- repository source: `~/Solar/harness/`
- local runtime: `~/.solar/harness/`
- generated runtime state: `run/`, `state/`, `logs/`, `cache/`, `vendor/`, `venvs/`

Runtime logs, databases, private trajectories, local model caches, credentials, and machine-local state should not be committed as source.

### Optional skills and plugins

Base install is intentionally conservative:

- Solar-bundled skills are copied from `skills/` into `~/.claude/skills/`.
- Third-party skill packs are optional; use [`SKILLS-INSTALL.md`](SKILLS-INSTALL.md) and ask the user before installing optional repositories.
- Harness plugin support is installed as framework code. Plugins must provide `harness/plugins/<id>/manifest.yaml` and pass plugin validation before they should be treated as usable.
- API keys are optional for install. If you need API-backed features, copy `.env.template` to `.env` and fill values locally. Do not commit `.env`.

---

## Design Principles

1. **Natural language is the control surface**  
   Users give goals; Solar compiles goals into contracts, graphs, and execution plans.

2. **Requirements are compilable artifacts**  
   Prompt is temporary. Contract, PRD, traceability, TaskGraph, and evidence are durable.

3. **Models are not the execution unit**  
   AI-capable environments are execution units: TUI panes, code agents, browser profiles, APIs, local processes, and remote workers.

4. **Parallelism requires boundaries**  
   Safe throughput requires dependency gates, write scopes, leases, worker health, and evaluator verdicts.

5. **Capabilities are schedulable assets**  
   Skills, MCPs, web product features, model strengths, code-agent behaviors, and deterministic tools should be modeled, injected, evaluated, and optimized.

6. **Evidence defines completion**  
   A task is not complete because a model says it is complete. It is complete when evidence passes review.

7. **Self-optimization must be controlled**  
   Solar can optimize prompts, policies, capsules, and routing, but protected core changes require replay, canary, rollback, and human approval.

---

## Roadmap

| Phase | Theme | Work |
|---|---|---|
| 1 | **Public homepage + docs cleanup** | Keep README, install docs, and user guide aligned with the current architecture. |
| 2 | **Privacy and release hardening** | Template local host configs, remove machine fingerprints, add privacy scan and release gates. |
| 3 | **Operator runtime** | Formalize logical/physical operator schemas, leases, health, scorecards, and fallback ladders. |
| 4 | **Model fleet manager** | Subscription-aware routing, cost/quality/latency scoring, browser-native operators. |
| 5 | **Hard execution boundaries** | Write-scope enforcement, per-node worktrees, patch gates, permission policy, sandbox adapters. |
| 6 | **Context Map plane** | PEEK-style repo/topic/project maps with provenance, staleness, role-aware rendering. |
| 7 | **Deep Research OS** | Source discovery, evidence ledger, claim ledger, citation gate, report compiler, research evaluator. |
| 8 | **Meta Harness** | Artifact registry, evaluator registry, replay set, side-info schema, Pareto frontier, promotion/rollback. |
| 9 | **Boss dashboard** | Autonomous progress, active DAGs, worker fleet, evidence status, cost/throughput, approvals needed. |

---

## Current Boundary

Solar is a serious prototype, not a finished commercial operating system. The core abstractions are already visible: requirement compilation, TaskGraph IR, physical operator scheduling, evidence ABI, model fleet control, and self-optimization hooks.

The next engineering priority is to make these abstractions clean, safe, observable, and easy to install:

- remove machine-local details from public-facing config and docs;
- replace Mermaid diagrams with maintained SVG architecture assets;
- stabilize the public documentation around Core / Harness / Knowledge;
- strengthen privacy, release, and sandbox gates;
- expose the Harness runtime through cleaner APIs and dashboards.

---

## Closing

Solar is not built around a single model, a single UI, or a single agent loop.

It treats natural language as the control surface, requirements as compilable artifacts, AI products as physical operators, capabilities as schedulable capsules, and engineering work as evidence-gated DAG execution.

**Solar makes AI work run like system software: compiled, scheduled, bounded, evidenced, and optimized.**
