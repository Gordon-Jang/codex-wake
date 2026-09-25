# wake

**wake** is a Codex Skill for long-running tasks that may span multiple quota windows.

## v0.4.0: persist the task, not the chat

Earlier WAKE versions tried to resume the original Codex thread. On Codex Desktop that
can conflict with the active writer already owned by Desktop. v0.4 changes the recovery
unit from a thread to a durable **job**.

A job stores a compact checkpoint under:

`~/.codex/wake/jobs/<job-id>/checkpoint.md`

When included usage is unavailable, WAKE waits locally without making model turns. When
`ordinaryUsageAllowed` becomes true again, WAKE starts a **new** lightweight
`codex exec` thread that reads the checkpoint first and continues only unfinished work.

## Why this design

- avoids `thread already has an active writer` conflicts;
- does not depend on Codex Desktop Goal UI automation;
- does not require the experimental Windows app-server daemon;
- avoids blindly resuming a huge old chat;
- keeps quota checks local through one hidden persistent `codex app-server`;
- never infers recovery from reset time alone.

WAKE does not bypass OpenAI usage limits, credits, rate limits, or safety controls.

## Requirements

- Codex CLI available as `codex`
- Python 3
- existing Codex authentication
- a Codex host that exposes `CODEX_THREAD_ID` to shell/tool execution when `$wake`
  creates the initial job

## Install

Windows:

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.cmd
```

Default install path:

`%USERPROFILE%\.codex\skills\wake`

Durable job/checkpoint data lives separately under:

`%USERPROFILE%\.codex\wake`

Reinstalling the Skill does not erase that job history.

## Use

In the Codex conversation that owns the task:

```text
$wake
```

The Skill creates a job, writes a compact checkpoint from the current task context, arms
the job, starts the local watcher, and continues working.

Useful diagnostics:

```powershell
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" doctor
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" status
python "$HOME\.codex\skills\wake\watcher\wake_watcher.py" job-list
```

For advanced use, `job-create` / `job-create-current` also accept `--model` and `--reasoning-effort`; if omitted, Codex uses the normal configuration.

## Job states

- `draft` — checkpoint exists but is not armed;
- `monitoring` — current work is active and quota is watched;
- `quota_waiting` — ordinary included usage is unavailable;
- `running` — a checkpoint handoff thread is executing;
- `retry_waiting` — transient capacity/network failure; retries with bounded backoff;
- `waiting_user` — explicit user/manual dependency; never auto-launched;
- `needs_attention` — continuation exited unexpectedly; never loops blindly;
- `stopped` — user disabled automatic continuation but kept the checkpoint;
- `completed` — verified done; ignored by watcher.

## Recovery contract

A handoff thread reads the checkpoint first, then normally checks only
`git status --short` and `git diff --stat`. It is explicitly told not to reconstruct,
resume, or reread the previous chat.

See [docs/quota-watcher.md](docs/quota-watcher.md) for the state machine.

## Development

```powershell
python -m py_compile .\watcher\wake_watcher.py
python -m unittest discover -s tests -v
```

v0.4.0 has been validated with unit tests plus a real Windows handoff through the recovered-quota path: a fresh Codex thread read the checkpoint, produced and byte-verified the requested artifact, updated the checkpoint, and marked the job completed.
