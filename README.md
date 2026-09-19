# wake

[![Validate skill](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml/badge.svg)](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/Gordon-Jang/codex-wake)](https://github.com/Gordon-Jang/codex-wake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md)

**wake** is a small Codex skill for keeping long-running work alive across
interruptions without repeatedly waking conversations that are waiting for the
user.

All WAKE-enabled conversations use the same quarter-hour wall-clock grid:

`HH:00 · HH:15 · HH:30 · HH:45`

> [!IMPORTANT]
> WAKE does **not** bypass OpenAI usage limits, quotas, rate limits, or service
> restrictions. It only schedules later continuation attempts after normal
> availability returns.

## What's new in v0.2

v0.1 used a simple quarter-hour continuation loop. That works for quota and
transient failures, but it can become noisy when Codex is actually waiting for
the user.

v0.2 adds a state machine:

```text
ACTIVE             → do not duplicate work
WAITING_USER       → pause WAKE
RETRYABLE_BLOCKED  → keep schedule and retry later
RUNNABLE           → continue unfinished work
DONE               → remove WAKE
UNKNOWN            → ask once, then pause
```

The important change is `WAITING_USER`.

If Codex says something like:

```text
Restart the process tree and tell me when it is ready.
```

the next WAKE run should detect that progress requires a manual user action,
pause its own schedule, and stop sending quarter-hour "continue" messages.

When the user comes back with:

```text
Restart complete, continue.
```

WAKE can re-arm the existing schedule. If implicit re-arm is not selected by the
host/model, `$wake` explicitly re-enables it.

See [docs/state-machine.md](docs/state-machine.md) for the complete lifecycle.

## Commands

| Command | Behavior |
|---|---|
| `$wake` | Start or re-arm WAKE for the current conversation |
| `$wake start` | Same as `$wake` |
| `$wake stop` | Stop WAKE for the current conversation |
| `$wake status` | Show enabled/paused/stopped state without changing it |

## Install

### Windows PowerShell

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
./scripts/install.sh
```

The installer copies the skill to:

```text
~/.agents/skills/wake/
```

Codex reads user-level skills from `~/.agents/skills`.

### Repository-local install

Copy this repository's `SKILL.md` and optional `agents/` metadata into:

```text
<your-repo>/.agents/skills/wake/
```

## Usage

Start:

```text
Finish the remaining work in this project.

$wake
```

Check status:

```text
$wake status
```

Stop:

```text
$wake stop
```

If WAKE paused because it needed you, respond to the pending request normally.
If it does not automatically re-arm, add:

```text
$wake
```

## Synchronization model

If three conversations enable WAKE at different times:

```text
A enabled at 12:01
B enabled at 12:06
C enabled at 12:11
```

the intended wake grid is:

```text
12:15   A B C
12:30   A B C
12:45   A B C
13:00   A B C
```

rather than three independent 15-minute offsets.

Actual execution can occur slightly after the nominal scheduled time depending on
the scheduler, machine state, service availability, and account limits.

## How it works

WAKE uses an **in-conversation Scheduled Task** so each run returns to the same
conversation and retains its existing context.

Before continuing project work, each scheduled run classifies the conversation:

| State | Meaning | Action |
|---|---|---|
| ACTIVE | Work is already progressing | Do not duplicate work |
| WAITING_USER | User input/manual action is required | Pause WAKE |
| RETRYABLE_BLOCKED | Quota/rate/network/service issue | Keep schedule |
| RUNNABLE | Work can continue now | Continue |
| DONE | Requested work is complete | Remove WAKE |
| UNKNOWN | User dependency is unclear | Ask once and pause |

The preferred recurrence is:

```text
RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0
```

## Why not a global supervisor yet?

Codex App Server exposes useful primitives such as non-resuming `thread/read`,
runtime thread status, approvals, and user-input requests. Those are promising
building blocks for a single supervisor that scans many threads.

WAKE v0.2 intentionally does **not** enable cross-thread supervision by default.
An external process does not currently have a documented, generally safe way to
attach to the exact active Codex Desktop runtime instance for every visible
thread. A separate App Server can inspect persisted history, but persisted state
is not always the same thing as Desktop's live runtime state.

Shipping an aggressive supervisor today could therefore wake an already-active
thread or act on stale state. The conversation-local pause/re-arm design solves
the repeated WAITING_USER wakeups without taking that risk.

See [docs/state-machine.md](docs/state-machine.md).

## Requirements and limitations

- A Codex/ChatGPT environment that supports Skills.
- Scheduled Tasks must be available for the account/workspace.
- For scheduled work that needs local files, the computer and relevant desktop
  app may need to remain running.
- One scheduled run may still appear when it first discovers WAITING_USER;
  v0.2 prevents the later repeated wakeups by pausing the schedule.
- Implicit re-arm depends on skill selection by the host/model. Explicit
  `$wake` is the reliable fallback.
- WAKE cannot guarantee model capacity.
- WAKE cannot bypass quota or rate limits.
- Scheduler and Codex product behavior may evolve.

## Repository layout

```text
codex-wake/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ docs/
│  └─ state-machine.md
├─ .github/
│  ├─ workflows/
│  │  ├─ validate.yml
│  │  └─ release.yml
│  └─ release-notes/
├─ scripts/
│  ├─ install.ps1
│  ├─ uninstall.ps1
│  ├─ install.sh
│  └─ uninstall.sh
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
├─ README.md
├─ README.zh-CN.md
├─ SECURITY.md
└─ VERSION
```

## Official references

- OpenAI — Build skills:
  https://developers.openai.com/docs/build-skills
- OpenAI — Scheduled tasks / automations:
  https://developers.openai.com/docs/automations
- OpenAI — Codex App Server:
  https://developers.openai.com/docs/app-server
- OpenAI Codex issue tracking active Desktop attachment:
  https://github.com/openai/codex/issues/25914

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is an independent community project. It is not an official OpenAI product
and is not affiliated with or endorsed by OpenAI.
