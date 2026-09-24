# wake

[![Validate skill](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml/badge.svg)](https://github.com/Gordon-Jang/codex-wake/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/Gordon-Jang/codex-wake)](https://github.com/Gordon-Jang/codex-wake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [简体中文](README.zh-CN.md)

**wake** is a state-aware Codex Skill for long-running work. v0.3.2 adds a local
quota watcher so quota recovery no longer depends on blind 15-minute model retries.

## What v0.3.2 does

- registers the exact current Codex thread from `CODEX_THREAD_ID`
- reads quota locally through `codex app-server`
- treats `ordinaryUsageAllowed` as the recovery authority
- uses `resetsAt` only to decide when to check again
- tracks `monitoring -> quota_waiting -> monitoring`
- never wakes `waiting_user` threads
- never uses `--last` or guesses a thread id
- keeps synchronized Scheduled Tasks as a conservative fallback

> [!IMPORTANT]
> WAKE does not bypass OpenAI usage limits, quotas, rate limits, credits, or safety controls.

## Requirements

- Codex CLI available as `codex`
- Python 3
- Codex authentication already configured
- a Codex host that exposes `CODEX_THREAD_ID` to shell/tool execution for exact-thread registration

## Install

Windows:

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.scriptsinstall.cmd
```

Default install path:

```text
%USERPROFILE%.codexskillswake
```

macOS/Linux:

```bash
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
./scripts/install.sh
```

## Verify quota integration

```powershell
cd $HOME.codexskillswake
python .watcherwake_watcher.py doctor
```

Working integration reports:

```text
"quotaReadOk": true
```

## Start watcher

Windows:

```powershell
.scriptsstart-watcher.cmd
.scriptsstatus-watcher.cmd
```

Then, in the Codex conversation to manage:

```text
$wake
```

The Skill should register the exact thread from inside that conversation. A normal
external terminal does not have `CODEX_THREAD_ID`, so `register-current` is
intentionally rejected there.

Check registrations:

```powershell
python $HOME.codexskillswakewatcherwake_watcher.py list
```

## State behavior

| State | Behavior |
|---|---|
| ACTIVE | Do not duplicate work |
| WAITING_USER | Pause; quota refresh must not wake it |
| QUOTA_BLOCKED | Watch locally until ordinary usage is actually allowed |
| RETRYABLE_BLOCKED | Use conservative Scheduled Task fallback |
| RUNNABLE | Continue unfinished work |
| DONE | Unregister and stop |
| UNKNOWN | Ask once, then pause |

See [docs/quota-watcher.md](docs/quota-watcher.md).

## Known limitation

Quota recovery currently launches exact `codex exec resume <thread-id>`. It is
safer than `--last`, but a detached CLI continuation may not always render in
Codex Desktop exactly like a native Desktop turn.

## License

MIT.
