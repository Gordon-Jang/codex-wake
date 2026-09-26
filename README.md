# wake

**wake** is a Codex Skill for long-running tasks that may span multiple quota windows.

## v0.5.0: memory capsule first

WAKE no longer treats the old conversation as the durable unit. It persists a **job** and
keeps two task-state layers under:

`~/.codex/wake/jobs/<job-id>/`

```text
state.json
memory-capsule.md
checkpoint.md
runs/
```

`memory-capsule.md` is the first-priority recovery memory. It is capped at 8 KiB and is
explicitly **not** a rewritten chat transcript. It contains only task state:

- objective;
- current position;
- verified facts;
- decisions / do-not-repeat items;
- constraints;
- active files;
- next actions;
- blockers;
- resume policy.

`checkpoint.md` keeps the more detailed structured execution state.

The capsule is projected locally from the checkpoint, so refreshing it does not consume
another model turn.

## Recovery order

When included usage returns, WAKE starts a fresh lightweight `codex exec` continuation.
The recovery prompt requires:

1. read `state.json`;
2. read `memory-capsule.md` as primary task memory;
3. inspect minimal live workspace state; probe Git before running status/diff commands;
4. read `checkpoint.md` only if more detail is needed;
5. continue from Next actions.

The continuation is forbidden from reconstructing, rereading, or summarizing the old chat.

## Pre-quota memory sealing

WAKE polls `account/rateLimits/read` locally. It records the highest returned usage
percentage across the primary/secondary windows:

- <80%: `normal`
- 80-89%: `prepare`
- 90-94%: `high`
- 95%+: `final`

At 90% or above, WAKE seals the newest checkpoint projection into the capsule. If the
checkpoint changes again, the next watcher poll creates a fresh seal.

This does not invent state that was never written to `checkpoint.md`. The active agent
therefore still updates the checkpoint after milestones and before long/risky/quota-heavy
operations.

## Desktop vs CLI wake boundary

The current v0.5 watcher still implements a **CLI continuation adapter**. A successful
capsule handoff to a new `codex exec` thread does not prove that the interrupted Codex
Desktop conversation or Goal was awakened.

A Desktop wake may be claimed only when WAKE has a supported Desktop thread/Goal bridge
and verifies the returned state on the Desktop-owned runtime. Otherwise diagnostics must
report `cli_continuation_only`.

## Why this design

- avoids Desktop active-writer conflicts;
- dramatically reduces the amount of old context needed at recovery;
- gives Codex or another AI a portable, model-neutral task-memory file;
- keeps the old chat as an archive instead of the default recovery source;
- refreshes the compact memory locally without spending a model call;
- uses `ordinaryUsageAllowed` as the authoritative recovery signal;
- handles transient capacity/network failures with bounded retry backoff.

WAKE does not bypass OpenAI usage limits, credits, rate limits, or safety controls.

## Requirements

- Codex CLI available as `codex`
- Python 3
- existing Codex authentication
- a Codex host that exposes `CODEX_THREAD_ID` when `$wake` creates the initial job

## Install

Windows:

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.cmd
```

Default Skill path:

`%USERPROFILE%\.codex\skills\wake`

Durable job data lives separately under:

`%USERPROFILE%\.codex\wake`

Reinstalling the Skill does not erase job/checkpoint/capsule history.

## Use

Inside the Codex conversation that owns the task:

```text
$wake
```

The Skill creates the job, fills the checkpoint from current task context, arms it, creates
the initial memory capsule, starts the watcher, and continues working.

Useful diagnostics:

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" doctor
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-list
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-status --job-id <job-id>
```

Force an immediate local capsule refresh:

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" memory-refresh --job-id <job-id>
```

For advanced use, `job-create` / `job-create-current` also accept `--model` and
`--reasoning-effort`; if omitted, Codex uses the normal configuration.

## Job states

- `draft` — checkpoint exists but is not armed;
- `monitoring` — current work is active and quota is watched;
- `quota_waiting` — ordinary included usage is unavailable;
- `running` — a capsule/checkpoint handoff thread is executing;
- `retry_waiting` — transient capacity/network failure; bounded backoff;
- `waiting_user` — explicit user/manual dependency;
- `needs_attention` — non-retryable or exhausted failure;
- `stopped` — automatic continuation disabled, state retained;
- `completed` — verified done.

## Development

```powershell
python -m py_compile .\watcher\wake_watcher.py
python -m unittest discover -s tests -v
```

v0.5.0 adds a portable `WAKE_MEMORY_CAPSULE_V1` layer on top of the v0.4
checkpoint-first architecture.
