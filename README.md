# wake

**wake** is a small Codex skill for keeping long-running work alive across
interruptions.

Invoke `$wake` in a Codex conversation and the skill asks Codex to attach a
scheduled continuation to that same conversation. All WAKE-enabled conversations
use the same quarter-hour wall-clock grid:

`HH:00 · HH:15 · HH:30 · HH:45`

That avoids the common "A wakes at :02, B at :07, C at :12" drift you get from
independent "every 15 minutes from now" timers.

> [!IMPORTANT]
> WAKE does **not** bypass OpenAI usage limits, quotas, rate limits, or service
> restrictions. It only schedules another continuation attempt after normal
> availability returns.

## Why

Long Codex tasks can be interrupted by usage limits, transient network failures,
temporary service availability, or simply because work needs to continue over
multiple runs.

WAKE gives each conversation a simple lifecycle:

```text
$wake
  ↓
continue current work
  ↓
interrupted / limited
  ↓
next synchronized quarter-hour
  ↓
return to the same conversation
  ↓
continue from existing state
  ↓
task complete
  ↓
stop its own WAKE schedule
```

## Commands

| Command | Behavior |
|---|---|
| `$wake` | Start WAKE for the current conversation |
| `$wake start` | Same as `$wake` |
| `$wake stop` | Stop WAKE for the current conversation |
| `$wake status` | Show current WAKE state without changing it |

## Install

### Option A — clone and install globally

Windows PowerShell:

```powershell
git clone https://github.com/Gordon-Jang/codex-wake.git
cd codex-wake
.\scripts\install.ps1
```

macOS / Linux:

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

### Option B — use only inside one repository

Copy this repository's `SKILL.md` (and `agents/` metadata if desired) into:

```text
<your-repo>/.agents/skills/wake/
```

## Usage

In a new or existing Codex conversation:

```text
Finish the remaining work in this project.

$wake
```

You can then check it:

```text
$wake status
```

Or stop it manually:

```text
$wake stop
```

### Synchronization model

If three conversations enable WAKE at different times:

```text
A enabled at 12:01
B enabled at 12:06
C enabled at 12:11
```

the intended wake grid is still:

```text
12:15   A B C
12:30   A B C
12:45   A B C
13:00   A B C
```

rather than three independent 15-minute offsets.

Actual execution can occur slightly after the nominal scheduled time depending on
the scheduler, machine state, service availability, and account limits.

## Requirements and limitations

- A Codex/ChatGPT environment that supports skills.
- Scheduled tasks must be available for the account/workspace.
- For scheduled work that needs local files, the computer and relevant desktop
  app may need to remain running.
- WAKE cannot guarantee that a scheduled run receives model capacity.
- WAKE cannot bypass quota or rate limits.
- Scheduler behavior and product capabilities may evolve over time.

## Repository layout

```text
codex-wake/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ .github/
│  └─ workflows/
│     └─ validate.yml
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
└─ SECURITY.md
```

## How it works

The skill tells Codex to create an **in-conversation scheduled task** and to
return to the same conversation on each scheduled run. It also asks Codex to
reuse an existing WAKE task instead of creating duplicates, inspect the existing
project state before making changes, and remove its own schedule after the
original task is complete.

The preferred recurrence is:

```text
RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0
```

When a scheduling surface does not expose RRULE directly, the skill asks for the
closest equivalent aligned to the same wall-clock boundaries.

## Official references

- OpenAI — Build skills:
  https://developers.openai.com/docs/build-skills
- OpenAI — Customization / skills:
  https://developers.openai.com/docs/customization/overview
- OpenAI — Scheduled tasks / automations:
  https://developers.openai.com/docs/automations

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

This is an independent community project. It is not an official OpenAI product
and is not affiliated with or endorsed by OpenAI.

“OpenAI”, “ChatGPT”, and “Codex” may be trademarks of their respective owner.
