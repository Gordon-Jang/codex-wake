# Changelog

All notable changes to this project will be documented here.

The project follows a lightweight interpretation of Keep a Changelog.

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
- README documentation now explains why a central cross-thread supervisor is not
  enabled by default yet.

### Fixed

- Prevent repeated quarter-hour "continue" wakeups when Codex is actually waiting
  for the user to answer a question or complete a manual step.

## [0.1.0] - 2026-09-18

### Added

- Initial public WAKE skill.
- `$wake`, `$wake start`, `$wake stop`, and `$wake status`.
- Shared quarter-hour synchronization at `:00 / :15 / :30 / :45`.
- Duplicate-schedule prevention guidance.
- Automatic stop guidance after task completion.
- Windows PowerShell install/uninstall scripts.
- macOS/Linux install/uninstall scripts.
- English and Simplified Chinese documentation.
- GitHub Actions validation.
