# Quota-aware watcher design — v0.3.2

The watcher is registered before quota is exhausted. This matters because a model
turn may not be available at the exact moment the account hits its limit.

## Exact thread identity

Codex shell/tool executions receive `CODEX_THREAD_ID`. `$wake start` invokes a
local helper from the target conversation so the watcher records that exact id.

A normal external terminal does not have this variable and therefore cannot use
`register-current`. WAKE never substitutes `--last`, recency, title, or working
directory for exact identity.

## State transition

```text
$wake start
    ↓
monitoring
    ↓ ordinaryUsageAllowed == false
quota_waiting
    ↓ ordinaryUsageAllowed == true
resume exact thread once
    ↓
monitoring
```

A `waiting_user` entry is outside that transition and is not woken by quota recovery.

## Quota authority

The watcher calls `account/rateLimits/read` through local `codex app-server`.

- `ordinaryUsageAllowed == true` → recovery is allowed
- `ordinaryUsageAllowed == false` → keep waiting
- `ordinaryUsageAllowed == null` → unknown; never assume recovery
- `resetsAt` → check-time hint only

Multiple reset windows may exist. The earliest future reset is only a useful next
check time; the watcher always re-reads `ordinaryUsageAllowed` before waking anything.

## Desktop limitation

Recovery currently uses exact `codex exec resume <thread-id>`. Exact identity is
safer than `--last`, but a detached CLI continuation may not always render in
Codex Desktop exactly like a native Desktop turn. Keep Scheduled Task fallback
available where detached resume is not satisfactory.
