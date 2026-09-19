# WAKE state machine

WAKE v0.2 replaces blind periodic continuation with a small state machine.

```text
                         ┌───────────────┐
                         │   RUNNABLE    │
                         └───────┬───────┘
                                 │ continue
                                 ▼
                         ┌───────────────┐
                         │     work      │
                         └───────┬───────┘
                                 │
               ┌─────────────────┼──────────────────┐
               ▼                 ▼                  ▼
          ┌─────────┐      ┌──────────────┐    ┌─────────┐
          │ ACTIVE  │      │ WAITING_USER │    │  DONE   │
          └────┬────┘      └──────┬───────┘    └────┬────┘
               │                  │                  │
          no duplicate         pause WAKE        remove WAKE
               │                  │
               │              user replies
               │                  │
               └──────────────┬───┘
                              ▼
                         re-arm WAKE

          RETRYABLE_BLOCKED → keep schedule → retry next quarter-hour
```

## Why WAITING_USER pauses

A scheduled message is already visible by the time a scheduled run begins.
Therefore a prompt-only guard cannot prevent the *first* wake that discovers
the conversation is waiting for the user.

The useful goal is to prevent every later quarter-hour wake.

When a run determines that progress requires user input or a manual action,
it pauses its own WAKE schedule immediately. The conversation should then stay
quiet until the user responds.

## Re-arm

When the user provides the requested answer, approval, confirmation, or manual
completion, WAKE can re-arm the existing schedule.

WAKE enables implicit invocation only for this re-arm path. It must not start
WAKE implicitly in unrelated conversations.

If implicit invocation is not selected by the host/model, the fallback is:

```text
$wake
```

or:

```text
$wake start
```

## State definitions

| State | Meaning | Scheduled-task action |
|---|---|---|
| ACTIVE | Work is already progressing without user action | Do not duplicate work; leave schedule enabled |
| WAITING_USER | A user answer, approval, credential, restart, or manual step is required | Pause WAKE |
| RETRYABLE_BLOCKED | Quota, rate limit, temporary service/network failure | Keep WAKE enabled |
| RUNNABLE | Unfinished work can proceed now | Continue from current state |
| DONE | Original request has been verified complete | Remove WAKE |
| UNKNOWN | It is unclear whether user action is required | Ask once, then pause as WAITING_USER |

## Central supervisor status

A future WAKE backend may use Codex App Server as a central supervisor. The
official App Server protocol exposes non-resuming thread reads, runtime status,
and user-input/approval events.

WAKE does not enable that backend by default yet. An external process does not
currently have a documented, generally safe way to attach to the exact active
Codex Desktop runtime instance for every user-visible local thread. Starting a
separate App Server can read persisted threads, but that is not equivalent to
observing the Desktop process's live runtime state.

Until that boundary is supported reliably, v0.2 prefers the safer
conversation-local state machine over cross-thread automation that might resume
the wrong or already-active thread.

References:

- https://developers.openai.com/docs/app-server
- https://developers.openai.com/docs/automations
- https://github.com/openai/codex/issues/25914
