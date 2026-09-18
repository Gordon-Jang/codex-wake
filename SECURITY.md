# Security

WAKE is an instruction-based Codex skill. It does not require credentials,
tokens, API keys, or elevated system privileges.

## Reporting a problem

If you discover behavior that could unexpectedly:

- delete or overwrite user work,
- create runaway scheduled tasks,
- affect unrelated conversations,
- expose secrets,
- or encourage bypassing platform limits,

please open a GitHub issue with the minimum reproducible example.

Do not include passwords, API keys, private repository contents, personal data,
or other secrets in public issues.

## Security expectations

WAKE should:

- operate only on the current conversation's continuation schedule,
- avoid duplicate retry schedules,
- preserve valid work when execution is interrupted,
- never attempt to bypass usage quotas or rate limits,
- and avoid modifying unrelated project files merely as part of scheduling.
