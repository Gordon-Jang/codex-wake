# Checkpoint-first quota watcher — v0.4

## Goal

Continue a long Codex task across included-usage windows without reopening the entire
old conversation and without competing with Codex Desktop for the same thread writer.

The durable object is a **WAKE job**, not a Codex thread.

## Persistent layout

```text
~/.codex/wake/
├─ watcher.pid
├─ watcher.log
└─ jobs/
   └─ <job-id>/
      ├─ state.json
      ├─ checkpoint.md
      └─ runs/
         └─ run-0001-<timestamp>.jsonl
```

The Skill install lives separately under `~/.codex/skills/wake`. Reinstalling the Skill
therefore does not erase job/checkpoint history.

## Initial registration

`$wake` runs inside the source Codex conversation and requires `CODEX_THREAD_ID`.
The thread id is recorded only as provenance. It is never used for automatic resume.

The current model writes a compact checkpoint and then arms the job.

```text
draft
  |
  | checkpoint filled + job-arm
  v
monitoring
```

A draft job is never launched.

## Quota authority

WAKE reads `account/rateLimits/read` from one hidden persistent local
`codex app-server`.

- `ordinaryUsageAllowed == false` means wait.
- `ordinaryUsageAllowed == true` permits a checkpoint handoff.
- null/unknown means do not infer recovery.
- `resetsAt` is only a scheduling hint.

Multiple windows can exist. WAKE always re-reads the authoritative boolean before launch.

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

`waiting_user`, `needs_attention`, `stopped`, `draft`, and `completed` are not auto-launched.

## Handoff contract

Recovery uses a fresh:

```text
codex exec --json -C <workspace> --add-dir <job-dir> ...
```

It does **not** use `codex exec resume`.

The continuation prompt requires the new thread to:

1. read `checkpoint.md` first;
2. normally inspect only `git status --short` and `git diff --stat`;
3. continue from `Next actions`;
4. skip work already listed under `Completed` or `Do not repeat`;
5. update the checkpoint after meaningful milestones;
6. call `job-pause` when user input is required;
7. call `job-complete` after the Goal is fully verified.

## Why not resume the old Desktop thread?

In testing, detached `codex exec resume <thread-id>` failed with:

```text
thread-store conflict: thread ... already has an active writer
```

Codex Desktop already owned that thread. v0.4 avoids that control-plane conflict entirely
by making a new thread for each quota handoff.

## Desktop wake acceptance criteria

The current watcher path is `cli_continuation_only`: it can prove that a new CLI continuation thread read the checkpoint and continued the task, but it does not directly wake the interrupted Desktop-owned thread or Goal.

Treat Desktop wake as a separate capability. It is successful only when a supported Desktop thread/Goal bridge is available and WAKE verifies the returned thread/Goal status on the Desktop-owned runtime. Until that bridge exists and is tested, CLI continuation results must not be presented as Desktop wake results.

## Failure handling

WAKE distinguishes transient failures from terminal ones:

- selected-model capacity and common temporary network/HTTP 502/503/504 failures enter `retry_waiting`;
- retry delay grows exponentially from 60 seconds, is capped at 15 minutes, and stops after 8 retries;
- if a continuation process exits while quota is available for a non-retryable reason, WAKE sets `needs_attention`;
- if it exits while quota is unavailable, WAKE returns to `quota_waiting`;
- missing workspace paths or launch errors also become `needs_attention`.

## Context-efficiency rule

The checkpoint should stay small and operational. Record conclusions, file paths, short
verification results, and next actions. Do not paste old chat history, full logs, or large
diffs. Old chats remain available as archives if a human later needs them.
