# Contributing to wake

Thanks for helping improve WAKE.

## What makes a good contribution

Useful changes generally fall into one of these categories:

- make skill behavior more deterministic
- reduce duplicate scheduled tasks
- improve completion detection
- improve compatibility with Codex product changes
- improve installation or documentation
- add reproducible test/validation coverage

## Before opening a pull request

1. Keep the skill name `wake` unless the project is intentionally being forked.
2. Preserve the four public commands:
   - `$wake`
   - `$wake start`
   - `$wake stop`
   - `$wake status`
3. Preserve synchronized wall-clock behavior at `:00 / :15 / :30 / :45`.
4. Do not add instructions that attempt to bypass usage limits, quotas or safety controls.
5. Keep `$wake start` idempotent: repeated starts should not intentionally create duplicates.
6. Update `CHANGELOG.md` when behavior changes.

## Pull requests

Please include:

- what changed
- why it changed
- how you tested it
- any known product/version assumptions

Small focused pull requests are preferred.

## Product changes

Codex and Scheduled Tasks evolve. If an OpenAI product change affects WAKE,
please link the relevant official documentation in the issue or pull request.
