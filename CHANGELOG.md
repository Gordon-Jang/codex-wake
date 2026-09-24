# Changelog

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

- Exact quota recovery currently resumes through detached `codex exec resume <thread-id>`;
  Codex Desktop UI synchronization may vary by version.

## [0.2.0] - 2026-09-19

### Added

- State-aware WAKE lifecycle with ACTIVE, WAITING_USER, RETRYABLE_BLOCKED,
  RUNNABLE, DONE, and UNKNOWN states.
- Automatic pause when progress requires user input, approval, credentials,
  confirmation, restart, or another manual action.
- Re-arm flow after the user resolves a WAITING_USER blocker.
- State-machine documentation.

### Fixed

- Prevent repeated quarter-hour wakeups while Codex is waiting for the user.

## [0.1.0] - 2026-09-18

### Added

- Initial public WAKE skill.
- `$wake`, `$wake start`, `$wake stop`, and `$wake status`.
- Shared quarter-hour synchronization at `:00 / :15 / :30 / :45`.
- Windows/macOS/Linux install scripts.
- English and Simplified Chinese documentation.
- GitHub Actions validation.
