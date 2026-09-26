---
name: wake
description: >
  Memory-capsule-first continuation for long Codex work across quota windows. Persist
  the current task as a durable WAKE job, keep a compact cross-model memory capsule,
  and continue in a new lightweight Codex exec thread after included usage recovers.
  Explicit commands: $wake, $wake start, $wake stop, $wake status.
---

# WAKE v0.5.0

WAKE persists the TASK, not the chat thread.

## Desktop / CLI handoff boundary

The watcher currently has a CLI continuation adapter only: after quota recovery it
starts a new `codex exec` thread from the memory capsule/checkpoint. This is not the
same as waking the interrupted Desktop thread. A Desktop wake is accepted only when a
supported Desktop thread/goal bridge is present and its returned thread/goal status is
verified; otherwise report `cli_continuation_only` explicitly and do not claim that the
Desktop conversation was resumed.

## Memory Capsule

Every WAKE job owns two different state layers:

- `memory-capsule.md`: first-priority, cross-model task memory; maximum 8 KiB.
- `checkpoint.md`: the more detailed structured execution record.

The capsule is **not** a rewritten conversation and is **not** a chat summary. It is a
deterministic projection of task state:

- objective;
- current position;
- verified facts;
- decisions and things not to repeat;
- constraints;
- active files;
- next actions;
- blockers;
- resume policy.

The watcher refreshes the capsule locally from `checkpoint.md`; this consumes no model
turn. The job metadata declares:

- `memoryFormat = wake-memory-v1`
- `contextPolicy = capsule_first`
- `historyPolicy = do_not_replay`

A new AI/Codex continuation must read `state.json` and `memory-capsule.md` first.
Read `checkpoint.md` only when the capsule is insufficient or conflicts with live state.
Do not reconstruct or replay the old conversation.

## Core rule

Never use `codex exec resume`, `--last`, recency, title, or another heuristic to
reopen the old conversation. The old conversation is an archive. The durable object is
the WAKE job plus its memory capsule/checkpoint.

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

4. Fill `checkpoint.md` with concise authoritative state:

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

5. Arm the job:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-arm --job-id <job-id>`

Arming automatically creates/refreshes `memory-capsule.md` and refuses to arm if the
checkpoint still contains placeholders.

6. Continue the task normally.

## Memory discipline while working

While a WAKE job is active:

- update `checkpoint.md` after every meaningful milestone;
- update it before long-running, risky, quota-heavy, or subagent operations;
- then run `memory-refresh` for immediate capsule synchronization;
- preserve verified work and explicit user constraints;
- record abandoned approaches under Decisions / Do not repeat;
- do not paste full logs, diffs, or chat transcripts.

Command:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-refresh --job-id <job-id>`

The watcher also detects a newer checkpoint and refreshes the capsule automatically on
its next local poll.

## Pre-quota sealing

The watcher records the highest returned usage percentage across primary/secondary
windows and marks memory pressure as:

- below 80%: `normal`
- 80-89%: `prepare`
- 90-94%: `high`
- 95%+: `final`

At 90% or above the watcher seals the latest checkpoint projection into the capsule.
If the checkpoint changes later, the next poll creates a new seal. This is local file
work only; WAKE does not spend another model turn merely to create the capsule.

This cannot preserve thoughts that were never written to `checkpoint.md`, so checkpoint
discipline remains the source of truth.

## Quota behavior

The watcher keeps one hidden persistent local `codex app-server` only for
`account/rateLimits/read`.

- `ordinaryUsageAllowed == false`: active jobs become `quota_waiting`.
- `resetsAt` is only a check-time hint.
- only `ordinaryUsageAllowed == true` permits a handoff.
- recovery starts a NEW `codex exec` thread.
- transient capacity/network failures use bounded exponential backoff
  (`retry_waiting`) instead of immediately giving up or spinning.

WAKE does not bypass, evade, or increase platform quota.

## New-thread recovery order

The continuation thread must:

1. read `state.json`;
2. read `memory-capsule.md` as primary task memory;
3. probe Git first with `git rev-parse --is-inside-work-tree`; only if that succeeds,
   inspect `git status --short` and `git diff --stat`. Never run `git diff` outside a
   worktree;
4. do not reread `SKILL.md` just to recover the job; this handoff already contains the
   recovery protocol;
5. read `checkpoint.md` only when more detail is actually required;
6. continue from Next actions;
7. update checkpoint + refresh memory after meaningful milestones;
8. mark WAITING_USER or DONE with the helper commands below.

It must not reconstruct, resume, reread, or summarize the old chat.

## WAITING_USER

If progress requires an answer, approval, credential, restart, or manual action:

1. update `checkpoint.md`;
2. refresh memory;
3. run:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-pause --job-id <job-id> --reason "<short reason>"`

The pause command also refreshes the capsule before changing state.

After the user resolves the blocker:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-rearm --job-id <job-id>`

## DONE

After the original Goal is fully verified:

1. update `checkpoint.md`;
2. refresh memory;
3. run:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-complete --job-id <job-id>`

The complete command refreshes the capsule one final time. Completed jobs remain as
local history and are ignored by the watcher.

## $wake status

Report watcher status and the current thread's active WAKE job without changing state:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status`

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-current`

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-status-current`

## $wake stop

Stop automatic continuation for the current task without deleting its memory:

`python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-stop-current`

A `stopped` job is retained locally and is never auto-launched.

## Diagnostics

- `python ...\wake_watcher.py doctor`
- `python ...\wake_watcher.py status`
- `python ...\wake_watcher.py quota`
- `python ...\wake_watcher.py job-list`
- `python ...\wake_watcher.py job-status --job-id <id>`
- `python ...\wake_watcher.py memory-status --job-id <id>`
- `python ...\wake_watcher.py memory-refresh --job-id <id>`

## Safety

- Never resume the original thread automatically.
- Never launch a job without a ready capsule/checkpoint.
- Never auto-launch `waiting_user`, `needs_attention`, `stopped`, `completed`, or
  `draft`; only `quota_waiting` and due `retry_waiting` may launch a handoff.
- Never infer quota recovery from time alone.
- Never delete user work to recover a job.
- Never treat a CLI continuation as proof that a Desktop thread/Goal woke successfully.
