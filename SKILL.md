---
name: wake
description: >
  Checkpoint-first continuation for long Codex work across quota windows. Persist the
  current task as a durable WAKE job with a compact checkpoint. When ordinary included
  usage returns, continue the job in a new lightweight Codex exec thread instead of
  resuming the old chat. Explicit commands: $wake, $wake start, $wake stop, $wake status.
---

# WAKE v0.4.0

WAKE persists the TASK, not the chat thread.

## Core rule

Never use `codex exec resume`, `--last`, recency, title, or another heuristic to
reopen the old conversation. The old conversation is an archive. The durable object is
the WAKE job and its checkpoint.

## $wake / $wake start

For the CURRENT Codex conversation only:

1. Start the local watcher if it is not running.

Windows:
`"$HOME\.codex\skills\wake\scripts\start-watcher.cmd"`

macOS/Linux:
`"$HOME/.codex/skills/wake/scripts/start-watcher.sh"`

2. Define one concise task Goal from the user's actual request.
3. From a shell/tool inside THIS conversation, create the job:

Windows example:
`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-create-current --cwd "<workspace>" --goal "<goal>"`

The helper MUST obtain the source thread from `CODEX_THREAD_ID`; never guess it.
If the thread already has a non-completed WAKE job, the helper returns that existing job
with `alreadyExists: true` instead of creating a duplicate.
4. Read the returned `checkpointPath` and refresh it into a compact,
authoritative checkpoint containing:

- Goal
- Constraints
- Completed
- Decisions
- Files changed
- Verification
- Current state
- Next actions
- Do not repeat
- Blockers
- Handoff

Keep it concise. Prefer a few KB; do not dump chat history.
5. Arm the job only after Goal and Next actions are real:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-arm --job-id <job-id>`

6. Continue the task normally.

## Checkpoint discipline

While a WAKE job is active:

- update the checkpoint after every meaningful milestone;
- update it before long-running, risky, or quota-heavy operations;
- preserve verified work and explicit user constraints;
- record abandoned approaches under Decisions / Do not repeat;
- do not copy large logs, diffs, or chat transcripts into the checkpoint;
- use paths, short results, commit ids, and test summaries instead.

The checkpoint is the recovery authority after a quota handoff.

## Quota behavior

The watcher keeps one hidden persistent local `codex app-server` only for
`account/rateLimits/read`.

- `ordinaryUsageAllowed == false`: active jobs become `quota_waiting`.
- `resetsAt` is only a check-time hint.
- only `ordinaryUsageAllowed == true` permits a handoff.
- recovery starts a NEW `codex exec` thread with the checkpoint path.
- transient capacity/network failures use bounded exponential backoff (`retry_waiting`) instead of immediately giving up or spinning.
- the recovery prompt explicitly forbids reconstructing or resuming the old chat.

This avoids Desktop active-writer conflicts and reduces repeated context processing.

## New-thread handoff

The continuation thread must:

1. read the checkpoint first;
2. inspect only minimal live workspace state, normally `git status --short` and
   `git diff --stat`;
3. continue from Next actions;
4. not redo items listed under Completed or Do not repeat unless stale;
5. keep updating the checkpoint;
6. mark WAITING_USER or DONE with the helper commands below.

WAKE does not bypass, evade, or increase platform quota.

## WAITING_USER

If progress requires an answer, approval, credential, restart, or manual action:

1. update the checkpoint with the exact blocker;
2. run:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-pause --job-id <job-id> --reason "<short reason>"`

A `waiting_user` job is never auto-launched.

After the user resolves the blocker:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-rearm --job-id <job-id>`

## DONE

After the original Goal is fully verified:

1. update the checkpoint with final verification;
2. run:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-complete --job-id <job-id>`

Completed jobs remain as local history and are ignored by the watcher.

## $wake status

Report both watcher status and the current thread's active WAKE job without changing state:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status`

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-current`

If no active job is associated with the current thread, say so plainly.

## $wake stop

Stop automatic continuation for the current task without deleting its checkpoint:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-stop-current`

A `stopped` job is retained locally and is never auto-launched. A later `$wake start`
may refresh its checkpoint and arm/rearm it again.

## Diagnostics

- `python ...\wake_watcher.py doctor`
- `python ...\wake_watcher.py status`
- `python ...\wake_watcher.py quota`
- `python ...\wake_watcher.py job-list`
- `python ...\wake_watcher.py job-status --job-id <id>`

## Safety

- Never resume the original thread automatically.
- Never launch a job without a completed checkpoint.
- Never auto-launch `waiting_user`, `needs_attention`, `stopped`, `completed`, or `draft`; only `quota_waiting` and due `retry_waiting` may launch a handoff.
- Never infer quota recovery from time alone.
- Never delete user work to recover a job.
- If a continuation process exits while quota is available without marking DONE or
  WAITING_USER, set `needs_attention` instead of looping.
