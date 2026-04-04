<!--
  ┌─────────────────────────────────────────────────────────────────┐
  │  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY                     │
  │                                                                 │
  │  This file is assembled from:                                   │
  │    1. TIM standards (tim/CLAUDE.md)                             │
  │    2. Project-specific content (CLAUDE-PROJECT.md)              │
  │                                                                 │
  │  To update:                                                     │
  │    - TIM standards: edit tim/CLAUDE.md, then run sync           │
  │    - Project content: edit CLAUDE-PROJECT.md, then run sync     │
  │                                                                 │
  │  Sync command: tim/bin/sync-claude-md                           │
  └─────────────────────────────────────────────────────────────────┘
-->

# CLAUDE.md

## How to Work

- Best technical solution, not easiest. Quality and correctness over speed. Don't offer easy vs best — just do best.
- Follow requests exactly. If uncertain, ASK.
- Investigate root causes. No workarounds that mask issues.
- Complete features fully. No TODOs, placeholders, or partial implementations.
- If you touched a file with violations, fix them.

## AI Behavioral Gates

- File >500 lines → BLOCKED. Function >50 lines → BLOCKED.
- No bypass flags. Human approval is the only escape hatch.

## AI Behavioral Rules

- When investigating a problem or diagnosing an issue: investigate the root cause, report findings, present options. Do not take action until the human explicitly approves. This applies to code edits, API calls, config changes, data modifications, and deployments. The only exception is read-only investigation (reading files, checking logs, querying for info). This does NOT apply when executing an approved plan — during implementation, act on the plan's instructions.
- Never speculate about causes. Investigate first — read logs, check state, verify facts — then state what you found. If you can't determine the cause, say "I don't know, here's what I checked." Never say "it might be X."
- No silent fallbacks. No `|| true`. No `|| return 0`. No `2>/dev/null` on things that matter. No `x or default` with fabricated defaults. No silent catches. If an operation fails, the caller must know immediately. If you're tempted to add a fallback, you don't understand the failure mode — figure it out instead.
- When a file operation fails with "Operation not permitted" (macOS immutable flags, locked enforcement files), stop immediately and ask the human to unlock. Do not attempt workarounds (cp, xattr, write tool). The human can unlock in seconds. Also: unstaged changes in locked files block ALL commits via pre-commit stash failure — if this happens, ask the human to unlock before committing.
- When a pre-commit hook auto-fixes files (prettier, ruff-format, eslint --fix) and then reports failure, the files are already correctly formatted. Just re-stage (`git add`) and re-commit. Do not try to run the formatter directly, read its config, or manually fix formatting.
- Never SSH into a running machine to edit project files. Clone the repo locally, make changes on a branch, push, and let the build system deploy. The running environment stays untouched until verified.

## Tests

**AI must not write tests unless explicitly asked.** AI-generated tests optimize for metrics, not for finding bugs. They create false confidence. Tests are human territory — humans write them when they choose to.

If a human asks you to write tests, write tests that would catch real bugs. Do not write tests to hit coverage numbers.

## Code Quality

- `mypy --strict` (Python) / `tsc strict` (Node). Zero warnings.
- Secrets never committed. All input validated (Pydantic/Zod).
- Migrations only — no sync(), create_all(), manual DDL.
- No TODO/FIXME/XXX, no print debugging, no bare except.
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

## Deployment

Deployments use `ops.sh ship` — the standard single-command deploy pipeline. `ship` validates the current branch matches the target env, commits and pushes code changes, builds all services via BuildKit, deploys (migrations + manifests + rollout), runs health checks, then commits and pushes the overlay update. `build` and `deploy` are available as individual commands but `ship` is preferred.

## ops.sh (MANDATORY)

ops.sh is the **only** way to interact with the k3s cluster. All cluster operations go through ops.sh — run `<alias> --env <env> --help` for available commands. Never bypass it with direct SSH, kubectl, or raw SQL.

ops.sh lives in the infra repo, not in projects. Projects have only `ops-config.yaml`. Each project has a shell alias that wraps ops.sh — the alias name is the `project.name` field from that project's `ops-config.yaml`. To find the alias for the current project, read `ops-config.yaml` and use the `project.name` value. Example: if `project.name: "myapp"`, then `myapp --env dev ship`.

**Available commands:**

- `status` — pods, services, deployments
- `health` — health check all services
- `logs <svc|job>` — view logs for a service (deployment) or a job (e.g., migration jobs)
- `describe <svc|job|pod>` — describe a service, job, or pod with events (use this to diagnose failures like ImagePullBackOff, CrashLoopBackOff, etc.)
- `restart <svc|all>` / `stop` / `start` — manage services
- `shell <svc>` — interactive shell in a pod
- `exec <svc> <cmd...>` — run a command in a pod
- `build <svc|all>` — build images via kaniko
- `deploy` — run migrations + apply manifests
- `ship` — full pipeline: commit, push, build, deploy, health check, commit overlay
- `fetch <svc> <path>` — copy file from pod (allowed paths only)
- `db backup|restore|migrate|shell|query|status` — database operations
- `vault get|put|del|ls|status|unseal|secrets|keys` — Vault secret operations
- `delete <type> <name>` — delete a resource (job, pod, scaledobject, triggerauthentication)
- `cleanup [logs]` — remove completed/failed pods and jobs, or truncate node logs
- `disk` — PVC and volume usage

**If ops.sh doesn't support what you need, STOP and ask the human.** Do not work around it with direct kubectl, SSH, or any other cluster access. The human will add the capability to ops.sh.

## Shared Libraries (REQUIRED)

Every project uses `tim-lib` (Python) or `@tim/lib` (Node) for: settings, logging, auth, errors, exception handlers, database pooling.

## Pattern Registry

Every project has `.tim-patterns.yaml`. Unregistered patterns block deployment. Custom patterns require human approval.

## Context Efficiency

### Subagent Discipline

- Prefer inline work for tasks under ~5 tool calls. Don't delegate trivially.
- Cap subagent output: "Final response MUST be under 2000 characters. List files modified and test results. No code snippets or stack traces."
- One TaskOutput call per subagent. If it times out, increase the timeout — don't re-read.
- Don't paste file contents into subagent prompts. Give file paths, let them read.
- Put quality rules in subagent prompts, not just the orchestrator. Let them enforce quality in their own context.

### File Reading

- Read files with purpose. Know what you're looking for before reading.
- Grep to locate relevant sections before reading large files.
- Never re-read a file already read this session.
- Files over 500 lines: use offset/limit for the relevant section only.

### Responses

- Don't echo back file contents you just read.
- Don't narrate tool calls. Just do it.
- Keep explanations proportional to complexity.

## Comms

Every project has a `comms/` folder (gitignored) with two files:

- **`inter-team.md`** — Cross-project messages between infra and this project. Infra writes directly into the project's file. **Always read this file when starting a session** — it may contain corrections or updates from infra.
- **`intra-team.md`** — Session-to-session notes within this project.

### Message ordering

**New messages go at the top** (prepend, not append). Sessions read top-down — the first entry must be the latest. When a message supersedes or corrects an older one, mark the old entry as stale:

```markdown
### ~~[old heading]~~ — STALE (corrected above on [date])
```

### Staleness

Messages accumulate across sessions. When reading comms, trust the topmost entry on a topic. If two entries contradict each other, the higher one wins. When writing a correction, always prepend — do not edit old entries in place (the history is useful context for why something changed).

Comms files are ephemeral working files, not project artifacts. They are scaffolded by `tim-sync` and gitignored. Do not commit them.

## Plans

Plans use `plans/` folder: `drafts/` → `active/` → `completed/` or `abandoned/`. Everything in a plan is required — no optional work.

Plan filenames: `YYYY-MM-DD-<slug>.md` (e.g., `2026-03-23-smtp-setup.md`). Plan title (H1) must match the slug (e.g., `# SMTP Setup`).

Plans always start in `plans/drafts/`. AI must never move plans between folders — promotion to `active/`, completion, and abandonment are human decisions. Plans require human review before promotion to `active/`.

---

<!-- ═══════════════════════════════════════════════════════════════════
     PROJECT-SPECIFIC CONTENT BELOW
     Edit CLAUDE-PROJECT.md to modify this section
     ═══════════════════════════════════════════════════════════════════ -->

# LED Flight

## Overview
LED flight tracker with dual runtime: CircuitPython (Adafruit MatrixPortal S3) + standard Python (Linux host).

## File Categories
- **CircuitPython** (`code.py`, `plane_icon.py`): Runs on microcontroller. No mypy, no type annotations, use `print()` for output. Linted by pylint with `.pylintrc-circuitpython`.
- **Standard Python** (all other `.py` files): Runs on Linux. Full TIM enforcement: mypy --strict, ruff, bandit, logging (not print).
- **`lib/`**: Precompiled `.mpy` CircuitPython libraries — binary, never modify, never lint.

## What This Project Does NOT Have
- No k8s, no ops.sh, no database, no deploy pipeline, no Dockerfile
- No web framework, no API served, no auth
- No tim-lib (standalone hardware project)

## Deployment
Manual: copy CircuitPython files to device via USB, run standard Python on Linux host via `run_ledflight.sh`.

## External Dependencies
- Flightradar24 API (read-only flight data)
- TimezoneDB API (timezone lookups)
- sunrise-sunset.org API (daylight times)

## TIM Exceptions
The following TIM requirements do not apply to this project:
- **No tim-lib**: Standalone hardware project, no web framework
- **No Dockerfile**: Not containerized
- **No ops-config.yaml**: Not deployed to k8s
- **No Gate 3**: No deploy pipeline
- **mypy exemption for CircuitPython files**: No type stubs for hardware modules (`board`, `digitalio`, `neopixel`, etc.)

## Security Considerations
- `code.py` downloads Python source from a GitHub raw URL and writes to disk (CircuitPython OTA update pattern) — known supply chain risk if the GitHub account is compromised
- MQTT connection in `code.py` uses `is_ssl=False` — data transmitted unencrypted
- `private.json` contains credentials — gitignored via `*private*` glob
- API responses from Flightradar24/TimezoneDB are deserialized without schema validation
