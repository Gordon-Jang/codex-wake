---
name: wake
description: >
  Manage state-aware synchronized continuation for the current Codex conversation.
  Explicitly invoke with $wake, $wake start, $wake stop, or $wake status.
  Use implicitly only when a conversation already using WAKE resumes after the
  user supplies previously requested input, confirmation, approval, or a manual
  action. Do not start WAKE implicitly for unrelated tasks.
---

# WAKE

WAKE manages state-aware synchronized continuation for the CURRENT conversation.

Its job is not to blindly send "continue" every 15 minutes. Before doing work,
every scheduled WAKE run must classify the conversation state and act on that
state.

## Commands

- `$wake`
  Same as `$wake start`.

- `$wake start`
  Enable or re-enable synchronized continuation for the current conversation.

- `$wake stop`
  Disable or remove the WAKE scheduled task belonging to the current conversation.

- `$wake status`
  Report whether WAKE is enabled, paused, or stopped; include the pause reason
  and next scheduled wake when available. Do not modify the schedule.

## START

When `$wake` or `$wake start` is explicitly invoked:

1. Operate on the CURRENT conversation.
2. Do not create a new conversation or thread for continuation.
3. Check whether this conversation already has a WAKE scheduled task.
4. If one already exists, update, resume, or reuse it instead of creating a duplicate.
5. Align it to the shared quarter-hour wall-clock grid.

Use this recurrence rule when the scheduling interface accepts RRULE:

`RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0`

The intended synchronized schedule is:

- HH:00
- HH:15
- HH:30
- HH:45

Do NOT implement this as "every 15 minutes from the moment WAKE was enabled".

If an explicit start time is required, use the next upcoming quarter-hour
boundary in the user's local timezone while preserving the synchronized
quarter-hour recurrence.

If the scheduling surface does not expose RRULE directly, create the closest
equivalent schedule that still aligns runs to :00, :15, :30 and :45.

## STATE MACHINE

At the beginning of EVERY scheduled WAKE run, classify the current conversation
before doing project work.

Use exactly these conceptual states:

### ACTIVE

Use ACTIVE when meaningful work is already progressing without needing the user,
including a currently running Codex turn or an autonomous background operation
that is still making progress.

Action:

1. Do not start duplicate work.
2. Do not restart commands, tests, builds, agents, or processes that are already running.
3. Leave WAKE enabled.
4. End this scheduled run quietly and concisely.

### WAITING_USER

Use WAITING_USER when progress requires something only the user can provide or do,
including:

- answering a question
- choosing between alternatives
- granting approval or permission
- providing credentials or other missing information
- completing a manual action
- restarting an application, service, machine, process tree, or environment
- confirming that an external/manual step has completed
- responding to an explicit "waiting for you" request from the previous turn

Action:

1. PAUSE or DISABLE the current conversation's WAKE scheduled task immediately.
2. Do not continue the project task.
3. Do not create another retry task.
4. Do not keep sending periodic "still waiting" messages.
5. Emit at most one concise status message explaining what user action is awaited
   and that WAKE has been paused.
6. Preserve all existing work and state.

This state is the key anti-noise rule. A conversation waiting for the user must
not be "shaken awake" every quarter hour.

### RETRYABLE_BLOCKED

Use RETRYABLE_BLOCKED only for temporary failures that do not require user action,
including:

- usage limit reached
- quota temporarily exhausted
- rate limit
- temporary service or model unavailability
- transient network failure

Action:

1. Preserve all valid work.
2. Keep WAKE enabled.
3. Do not create additional retry schedules.
4. Let the next synchronized quarter-hour run try again.

WAKE must never attempt to bypass, evade, or defeat service limits.

### RUNNABLE

Use RUNNABLE when the original task is unfinished, no other work is already
progressing, and no user action is required.

Action:

1. Inspect the current conversation and identify the original unfinished task.
2. Inspect current files, code, worktree, configuration, runtime state, and
   relevant tests before modifying anything.
3. Preserve valid completed work.
4. Determine what remains unfinished.
5. Continue from the current state.
6. Do not restart the task from scratch.
7. Do not repeat completed steps unnecessarily.
8. Do not create another conversation.
9. Do not create another WAKE schedule.
10. Continue autonomously as far as reasonably possible.

### DONE

Use DONE only after verifying the original request is fully complete.

Before classifying DONE:

1. Review the original request and later scope changes.
2. Check the current project state.
3. Run appropriate tests or checks when applicable.
4. Verify that no requested work remains unfinished.

Action:

1. Report the final result normally.
2. Disable, cancel, or remove this conversation's WAKE scheduled task.
3. Do not continue waking after completion.

### UNKNOWN

If it is genuinely unclear whether the task can continue without the user:

1. Do not guess and do not repeatedly retry.
2. Ask one concise clarifying question.
3. Treat the conversation as WAITING_USER.
4. Pause WAKE until the user responds.

## RE-ARM AFTER USER INPUT

WAKE may be invoked implicitly only for this re-arm flow.

When the user sends a new message that clearly resolves the reason a WAKE-enabled
conversation was paused, for example:

- "已经重启好了"
- "批准"
- "选第二个"
- "凭据已经配置好了"
- "继续"

then:

1. Check whether this CURRENT conversation has a WAKE task paused because it was
   WAITING_USER.
2. If not, do not create WAKE implicitly.
3. If yes, determine whether the new user message actually resolves the blocker.
4. If the blocker is resolved and the original task remains unfinished, re-enable
   the existing WAKE task on the synchronized quarter-hour grid.
5. Continue the user's current turn normally.
6. Do not create a duplicate scheduled task.

If implicit invocation does not occur on a host/version, the user can always
re-arm explicitly with `$wake` or `$wake start`.

## SCHEDULED WAKE PROMPT REQUIREMENTS

When creating or updating the in-conversation scheduled task, ensure its prompt
contains these semantics:

- Return to this same conversation.
- Classify state BEFORE continuing work.
- WAITING_USER => pause this WAKE task and stop.
- ACTIVE => do not duplicate work.
- RETRYABLE_BLOCKED => keep WAKE enabled for the next quarter-hour.
- RUNNABLE => continue unfinished work from current state.
- DONE => remove this WAKE task.
- Never restart completed work from scratch.

## STOP

When `$wake stop` is invoked:

1. Find the WAKE scheduled task associated with THIS conversation.
2. Disable, pause, cancel, or remove that scheduled task.
3. Do not affect WAKE tasks belonging to other conversations.
4. Do not alter project files merely because WAKE is being stopped.
5. Confirm that automatic continuation for this conversation is no longer active.

## STATUS

When `$wake status` is invoked, report:

- enabled, paused, or stopped
- current state if determinable: ACTIVE / WAITING_USER / RETRYABLE_BLOCKED /
  RUNNABLE / DONE / UNKNOWN
- pause reason, if paused
- synchronized schedule: HH:00 / HH:15 / HH:30 / HH:45
- next scheduled wake, if available
- whether the original task appears complete or unfinished

Do not create, delete, or change schedules while reporting status.

## SAFETY AND IDEMPOTENCY

WAKE controls continuation scheduling only.

It must never:

- intentionally bypass usage or quota limits
- create rapid retry loops
- create duplicate scheduled tasks for the same conversation
- wake more frequently than the defined quarter-hour grid
- modify schedules belonging to other conversations
- start a new thread for scheduled continuation
- discard valid user work merely to recreate state
- keep periodic wakeups running while explicit user input is required

Treat `$wake start` as idempotent whenever possible: repeated starts for the
same conversation should still result in exactly one WAKE schedule.
