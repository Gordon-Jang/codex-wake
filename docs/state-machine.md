# WAKE v0.4 job state machine

```text
draft
  |
  | checkpoint filled + job-arm
  v
monitoring
  |
  | ordinaryUsageAllowed == false
  v
quota_waiting
  |
  | ordinaryUsageAllowed == true
  v
running
  |\
  | +--> completed
  | +--> waiting_user
  | +--> quota_waiting
  +----> needs_attention
```

## Rules

- draft: never auto-launch.
- monitoring: current source/handoff thread is working; watcher only observes quota.
- quota_waiting: no model turns are generated until quota is actually available.
- running: a fresh checkpoint-based `codex exec` is active.
- waiting_user: explicit human dependency; never auto-launch.
- needs_attention: abnormal exit while quota is available; stop instead of looping.
- stopped: user-disabled automatic continuation; checkpoint is retained.
- completed: terminal state; retained as local history.

The source thread id is provenance only. WAKE v0.4 never automatically resumes it.
