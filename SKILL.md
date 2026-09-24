---
name: wake
description: >
  Manage state-aware continuation for the current Codex conversation. Prefer the
  local quota watcher when installed: register the exact current Codex thread via
  CODEX_THREAD_ID, monitor account quota locally, and wake the thread when ordinary
  usage becomes available again. Fall back to synchronized Scheduled Tasks when
  exact-thread registration or the watcher is unavailable. Explicitly invoke with
  $wake, $wake start, $wake stop, or $wake status. Re-arm implicitly only when the
  user resolves a blocker in a conversation already using WAKE.
---

# WAKE

WAKE keeps long Codex work moving without blindly retrying quota every 15 minutes.

## Backends

### Local quota watcher

Preferred for quota exhaustion:

- register the exact current thread from `CODEX_THREAD_ID`
- read limits locally through `codex app-server`
- use `ordinaryUsageAllowed` as the recovery authority
- use `resetsAt` only as a hint for when to check again
- resume only exact registered threads that observed quota blocking
- never use `--last` and never guess a thread id

### Scheduled Task fallback

Use the synchronized quarter-hour grid only when the watcher cannot safely handle
the thread, or for non-quota transient failures:

`RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0`

## Commands

- `$wake` — same as `$wake start`
- `$wake start` — enable or re-arm WAKE
- `$wake stop` — unregister/stop WAKE for this conversation
- `$wake status` — report backend and state without modifying it

## START

When `$wake` or `$wake start` is invoked:

1. Operate on the CURRENT conversation only.
2. Do not create or infer another thread.
3. Start the local watcher if installed and not already running.
4. From a shell/tool execution inside THIS conversation, register the exact current thread.

Windows:

`"$HOME\.codex\skills\wake\scripts\register-current.cmd"`

macOS/Linux:

`"$HOME/.codex/skills/wake/scripts/register-current.sh"`

The helper must obtain the id from `CODEX_THREAD_ID`. Never substitute recency,
title, project path, ordering, or `--last`.

5. If exact registration succeeds, prefer the watcher for quota recovery.
6. Use at most one synchronized Scheduled Task as fallback when useful.

## STATE MACHINE

### ACTIVE

Work is already progressing.

- Do not duplicate work.
- Do not restart running commands, tests, builds, agents, or processes.
- Leave watcher registration in `monitoring`.

### WAITING_USER

Progress requires the user to answer, approve, provide information/credentials,
restart something, perform a manual step, or confirm an external action.

Before ending the turn, pause the exact registration:

Windows:

`"$HOME\.codex\skills\wake\scripts\pause-current.cmd" --reason "<short reason>"`

macOS/Linux:

`"$HOME/.codex/skills/wake/scripts/pause-current.sh" --reason "<short reason>"`

Then:

- pause/disable fallback Scheduled Task when possible
- do not create retry tasks
- do not send periodic waiting messages
- preserve all existing work
- emit at most one concise message explaining what is awaited

A `waiting_user` entry must never be woken by quota recovery.

### QUOTA_BLOCKED

The local watcher handles quota without needing a model turn at the moment of exhaustion.

1. A thread registered by `$wake` starts in `monitoring`.
2. The watcher independently reads `account/rateLimits/read`.
3. When `ordinaryUsageAllowed == false`, `monitoring` becomes `quota_waiting`.
4. `resetsAt` may schedule the next check, but is never proof of recovery.
5. Only `ordinaryUsageAllowed == true` permits resume.
6. Resume only exact `quota_waiting` thread ids.
7. After a launch, return the registration to `monitoring`.
8. The resumed turn must classify state again before doing work.

If the watcher or exact registration is unavailable, use conservative Scheduled
Task fallback on the quarter-hour grid.

WAKE must never bypass or evade platform limits.

### RETRYABLE_BLOCKED

For transient non-quota network/service/model failures:

- preserve valid work
- use synchronized Scheduled Task fallback
- do not create extra retry schedules

### RUNNABLE

If unfinished work can continue without user input:

- inspect current conversation, files, worktree, runtime state, and tests
- preserve completed work
- continue only unfinished work
- do not restart from scratch
- do not create duplicate schedules or registrations

### DONE

After verifying the original request is complete:

- report the result
- stop/remove fallback Scheduled Task
- unregister the exact thread

Windows:

`"$HOME\.codex\skills\wake\scripts\unregister-current.cmd"`

macOS/Linux:

`"$HOME/.codex/skills/wake/scripts/unregister-current.sh"`

### UNKNOWN

If user dependency is unclear:

- ask one concise question
- treat as WAITING_USER
- pause watcher registration and fallback task

## RE-ARM AFTER USER INPUT

If the user resolves a previous WAITING_USER blocker, re-enable exact monitoring:

Windows:

`"$HOME\.codex\skills\wake\scripts\resume-current.cmd"`

macOS/Linux:

`"$HOME/.codex/skills/wake/scripts/resume-current.sh"`

If implicit invocation does not happen, `$wake` is the manual re-arm.

## WATCHER COMMANDS

Installed watcher:

`~/.codex/skills/wake/watcher/wake_watcher.py`

Useful commands:

- `doctor` — verify Codex CLI/App Server quota integration
- `quota` — read quota once
- `status` — watcher process and registration counts
- `list` — list exact-thread registrations
- `register-current` — register current `CODEX_THREAD_ID`
- `pause-current` — mark current thread WAITING_USER
- `resume-current` — return current thread to monitoring
- `unregister-current` — remove current registration

The watcher never stores OpenAI credentials, never redeems credits, never infers
recovery from `resetsAt` alone, never uses `--last`, and never wakes
`waiting_user` entries.

Watcher-driven resume currently uses exact detached `codex exec resume <thread-id>`.
Codex Desktop UI synchronization may vary by version, so Scheduled Task fallback
remains available.
