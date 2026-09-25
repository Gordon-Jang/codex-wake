# Changelog

All notable changes to this project will be documented here.

## [0.4.0] - 2026-09-26

### Changed

- Replaced thread-resume recovery with checkpoint-first job continuation.
- WAKE now persists durable jobs under `~/.codex/wake/jobs/<job-id>`.
- Quota recovery launches a new lightweight `codex exec` thread instead of reopening the old chat.
- The watcher uses one hidden persistent `codex app-server` for quota reads.
- Skill reinstall no longer owns or deletes durable job history.

### Added

- Compact `checkpoint.md` handoff contract.
- Job states: draft, monitoring, quota_waiting, running, retry_waiting, waiting_user, needs_attention, stopped, completed.
- Commands: `job-create-current`, `job-arm`, `job-status`, `job-list`, `job-pause`, `job-rearm`, `job-stop`, `job-complete`.
- Optional per-job model and reasoning-effort overrides.
- Bounded retries for temporary capacity/network failures.
- Unit tests for checkpoint lifecycle, quota transitions, handoff launch, and transient retries.

### Removed

- Automatic `codex exec resume <thread-id>`.
- Dependency on Desktop Goal owner/control-socket recovery for the primary path.

## [0.3.2] - 2026-09-24

### Added

- Local quota watcher backed by `codex app-server`.
- Exact current-thread registration from `CODEX_THREAD_ID`.
- Current-thread register/pause/resume/unregister helpers for Windows, macOS, and Linux.
- Account-level quota transition handling: `monitoring -> quota_waiting -> monitoring`.
- Windows `.cmd` wrappers so PowerShell execution policy does not block common operations.

### Changed

- `ordinaryUsageAllowed` is the authoritative quota-recovery signal.
- `resetsAt` is used only to schedule the next check.
- Default Skill installation path is `~/.codex/skills/wake`.
- WAITING_USER registrations are excluded from quota recovery.

### Fixed

- Correct App Server `initialize -> initialized -> account/rateLimits/read` handshake.
- Keep watcher state under `~/.codex/skills/wake/.state`.
- Do not wake newly registered threads immediately while quota is healthy.
- Do not print the raw account id in normal quota summaries.

### Known limitation

- Exact quota recovery used detached `codex exec resume <thread-id>`; v0.4.0 replaces that path with checkpoint-first job continuation.

## [0.2.0] - 2026-09-19

### Added

- State-aware WAKE lifecycle with ACTIVE, WAITING_USER, RETRYABLE_BLOCKED,
  RUNNABLE, DONE, and UNKNOWN states.
- Automatic pause when progress requires user input, approval, credentials,
  confirmation, restart, or another manual action.
- Re-arm flow after the user resolves a WAITING_USER blocker.
- Optional implicit invocation for re-arming an already-paused WAKE conversation.
- State-machine documentation and central-supervisor design notes.

### Changed

- WAKE no longer treats every unfinished conversation as immediately runnable.
- Scheduled runs classify state before doing project work.
- `$wake status` now reports paused state and pause reason when available.

## [0.1.0] - 2026-09-18

### Added

- Initial public WAKE skill.
- `$wake`, `$wake start`, `$wake stop`, and `$wake status`.
- Shared quarter-hour synchronization at `:00 / :15 / :30 / :45`.
- Duplicate-schedule prevention guidance.
- Windows PowerShell install/uninstall scripts.
- macOS/Linux install/uninstall scripts.
