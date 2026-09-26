# Memory-capsule quota watcher — v0.5

## Goal

Continue a long Codex task across included-usage windows without replaying the old
conversation and without competing with Codex Desktop for the same thread writer.

The durable object is a **WAKE job**, not a Codex thread.

## Persistent layout

```text
~/.codex/wake/
├─ watcher.pid
├─ watcher.log
└─ jobs/
   └─ <job-id>/
      ├─ state.json
      ├─ memory-capsule.md
      ├─ checkpoint.md
      └─ runs/
         └─ run-0001-<timestamp>.jsonl
```

The Skill install lives separately under `~/.codex/skills/wake`.

## Two state layers

`checkpoint.md` is the detailed, structured execution state written by the active agent.

`memory-capsule.md` is a deterministic compact projection of the checkpoint. It is
limited to 8 KiB and follows `WAKE_MEMORY_CAPSULE_V1`.

The capsule contains:

- Objective
- Current position
- Verified facts
- Decisions / do not repeat
- Constraints
- Active files
- Next actions
- Blocker
- Resume policy

It intentionally does **not** contain chat chronology or a rewritten transcript.

The related `state.json` metadata includes:

```json
{
  "memoryFormat": "wake-memory-v1",
  "contextPolicy": "capsule_first",
  "historyPolicy": "do_not_replay"
}
```

## Initial registration

`$wake` runs inside the source Codex conversation and requires `CODEX_THREAD_ID`.
The source thread id is provenance only.

The current agent fills `checkpoint.md`; `job-arm` then generates the first capsule.

```text
draft
  |
  | checkpoint filled
  | memory capsule generated
  | job-arm
  v
monitoring
```

A draft job is never launched.

## Local memory refresh

`memory-refresh` reads `checkpoint.md`, selects the task-state sections, applies
per-section limits, and writes `memory-capsule.md`. It does not call a model.

The watcher also compares checkpoint mtime with `memoryCheckpointMtimeNs`. If the
checkpoint is newer, the next local poll refreshes the capsule automatically.

This makes capsule generation independent from quota availability. Even if the model can
no longer run, a checkpoint that was already written can still be projected into the
short recovery memory locally.

## Pre-quota sealing

The watcher reads `account/rateLimits/read` and derives memory pressure from the highest
returned primary/secondary `usedPercent`:

```text
<80%   normal
80-89  prepare
90-94  high
95+    final
```

At 90% or above, WAKE ensures the latest checkpoint projection is present and records:

- `memorySealedAt`
- `memorySealedCheckpointMtimeNs`

If checkpoint mtime changes after a seal, the next poll creates a new seal.

No model turn is started merely to seal memory.

## Quota authority

- `ordinaryUsageAllowed == false` means wait.
- `ordinaryUsageAllowed == true` permits a handoff.
- null/unknown never implies recovery.
- `resetsAt` is only a scheduling hint.

## State machine

```text
monitoring
   |
   | ordinaryUsageAllowed == false
   v
quota_waiting
   |
   | ordinaryUsageAllowed == true
   v
running  -- starts NEW codex exec thread
   |
   +--> completed
   |
   +--> waiting_user
   |
   +--> quota_waiting      (run ended while quota blocked)
   |
   +--> retry_waiting      (temporary capacity/network failure)
   |       |
   |       +--> running    (bounded exponential backoff)
   |
   +--> needs_attention    (non-retryable failure / retry limit exceeded)
```

`waiting_user`, `needs_attention`, `stopped`, `draft`, and `completed` are not
auto-launched.

## Handoff contract

Recovery uses a fresh:

```text
codex exec --json -C <workspace> --add-dir <job-dir> ...
```

It does **not** use `codex exec resume`.

The new thread reads in this order:

1. `state.json`
2. `memory-capsule.md`
3. minimal live workspace state; probe Git with `git rev-parse --is-inside-work-tree`
   before any `git status` / `git diff` commands
4. `checkpoint.md` only if more detail is actually required

The prompt explicitly forbids reconstructing, rereading, or summarizing the previous
conversation.

After a meaningful milestone, the continuation updates checkpoint and runs
`memory-refresh`. Pause and complete commands also refresh the capsule before changing
state.

## Desktop wake acceptance criteria

The current watcher path is still `cli_continuation_only`. It proves that a new CLI
continuation thread consumed the persisted task state; it does not directly wake the
interrupted Desktop-owned thread or Goal.

Desktop wake is successful only when a supported Desktop thread/Goal bridge exists and
WAKE verifies the returned state on the Desktop-owned runtime.

## Failure handling

- model capacity and temporary network/HTTP 502/503/504 errors enter `retry_waiting`;
- retry delay grows exponentially from 60 seconds, capped at 15 minutes;
- retry stops after 8 transient failures;
- if a run ends while quota is blocked, return to `quota_waiting`;
- non-retryable failures become `needs_attention`.

## Context-efficiency rule

The capsule is task-state serialization, not a compressed transcript. The active agent
must still write important state into checkpoint before it is lost. Old chats remain
archives and are not the default recovery source.
