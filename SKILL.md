---
name: wake
description: >
  Manage synchronized continuation scheduling for the current Codex conversation.
  Explicitly invoke with $wake, $wake start, $wake stop, or $wake status.
  Use this skill when the user wants a long-running Codex task to automatically
  continue after usage limits, quota limits, interruptions, or temporary failures.
---

# WAKE

WAKE manages a synchronized scheduled continuation task for the CURRENT
conversation only.

## Commands

- `$wake`
  Same as `$wake start`.

- `$wake start`
  Enable synchronized continuation for the current conversation.

- `$wake stop`
  Disable or remove the WAKE scheduled task belonging to the current conversation.

- `$wake status`
  Report whether WAKE is currently enabled for this conversation and, when
  available, its next scheduled wake time. Do not modify the schedule.

## START

When `$wake` or `$wake start` is invoked:

1. Operate on the CURRENT conversation.
2. Do not create a new conversation or thread for continuation.
3. Check whether this conversation already has a WAKE scheduled task.
4. If one already exists, update or reuse it instead of creating a duplicate.
5. Create an in-conversation scheduled task aligned to the shared quarter-hour
   wall-clock grid.

Use this recurrence rule when the scheduling interface accepts RRULE:

`RRULE:FREQ=HOURLY;BYMINUTE=0,15,30,45;BYSECOND=0`

The intended synchronized schedule is:

- HH:00
- HH:15
- HH:30
- HH:45

Do NOT implement this as "every 15 minutes from the moment WAKE was enabled".
That causes different conversations to drift onto different schedules.

If an explicit start time is required, use the next upcoming quarter-hour
boundary in the user's local timezone while preserving the synchronized
quarter-hour recurrence.

If the scheduling surface does not expose RRULE directly, create the closest
equivalent schedule that still aligns runs to :00, :15, :30 and :45.

## SCHEDULED WAKE BEHAVIOR

Every scheduled run must return to THIS SAME conversation and use its existing
conversation context.

On every wake:

1. Inspect the current conversation and identify the original unfinished task.
2. Inspect the current project state, files, code, worktree and relevant test
   results before making changes.
3. Preserve valid work already completed.
4. Determine what remains unfinished.
5. If meaningful unfinished work exists, continue it from the current state.
6. Do not restart the task from scratch.
7. Do not repeat completed steps unnecessarily.
8. Do not create another conversation.
9. Do not create another WAKE schedule.
10. Continue autonomously as far as reasonably possible.

If execution is blocked because of:

- usage limit
- quota exhausted
- rate limit
- temporary service or model unavailability
- transient network failure

then:

1. Do not destroy or roll back valid existing work.
2. Keep the WAKE schedule enabled.
3. Do not create additional retry schedules.
4. Allow the next synchronized quarter-hour wake to try again.

WAKE is intended to resume work after normal availability returns. It must not
attempt to bypass, evade or defeat service limits.

## COMPLETION

Before deciding that the original task is finished:

1. Review the user's original request and any later changes to scope.
2. Check the current project state.
3. Run appropriate tests or checks when applicable.
4. Verify that no requested work remains unfinished.

If the original task is fully complete:

1. Report the final result normally.
2. Disable, pause, cancel or remove this conversation's WAKE scheduled task.
3. Do not continue waking after completion.

If completion is genuinely uncertain, keep WAKE enabled and continue on the next
scheduled run rather than declaring completion prematurely.

## STOP

When `$wake stop` is invoked:

1. Find the WAKE scheduled task associated with THIS conversation.
2. Disable, pause, cancel or remove that scheduled task.
3. Do not affect WAKE tasks belonging to other conversations.
4. Do not alter project files merely because WAKE is being stopped.
5. Confirm that automatic continuation for this conversation is no longer active.

## STATUS

When `$wake status` is invoked, report:

- enabled or disabled
- synchronized schedule: HH:00 / HH:15 / HH:30 / HH:45
- next scheduled wake, if available
- whether the current task appears complete or unfinished

Do not create, delete or change schedules while reporting status.

## SAFETY AND IDEMPOTENCY

WAKE controls continuation scheduling only.

It must never:

- intentionally bypass usage or quota limits
- create rapid retry loops
- create duplicate scheduled tasks for the same conversation
- wake more frequently than the defined quarter-hour grid
- modify schedules belonging to other conversations
- start a new thread for a scheduled continuation
- discard valid user work merely to recreate state

Whenever possible, treat `$wake start` as idempotent: running it more than once
for the same conversation should still result in exactly one WAKE schedule.
