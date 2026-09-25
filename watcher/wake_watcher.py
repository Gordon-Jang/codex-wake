#!/usr/bin/env python3
"""WAKE v0.4.0: checkpoint-first, job-first Codex continuation.

WAKE does not resume or take ownership of an existing Desktop thread.
It tracks a durable job, waits for ordinary included usage to return, then
starts a NEW lightweight Codex exec thread that reads only the checkpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.4.0"
SKILL_ROOT = Path.home() / ".codex" / "skills" / "wake"
WAKE_HOME = Path.home() / ".codex" / "wake"
JOBS_DIR = WAKE_HOME / "jobs"
PID_FILE = WAKE_HOME / "watcher.pid"
LOG_FILE = WAKE_HOME / "watcher.log"
THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{5,95}$")
_STOP = False
MAX_TRANSIENT_RETRIES = 8
RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 900
REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "ultra", "persistent", "max"}
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class WakeError(RuntimeError):
    pass


def now() -> int:
    return int(time.time())


def iso(ts: int | None) -> str | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def log(message: str) -> None:
    ensure_dirs()
    line = f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def hidden_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def find_codex() -> str:
    value = shutil.which("codex")
    if not value:
        raise WakeError("codex executable was not found in PATH")
    return value


def validate_thread_id(value: str) -> str:
    if not THREAD_ID_RE.match(value):
        raise WakeError("unsafe thread id")
    return value


def validate_job_id(value: str) -> str:
    if not JOB_ID_RE.match(value):
        raise WakeError("unsafe job id")
    return value


def current_thread_id(required: bool = True) -> str | None:
    value = os.environ.get("CODEX_THREAD_ID", "").strip()
    if not value:
        if required:
            raise WakeError("CODEX_THREAD_ID is unavailable; run inside the target Codex conversation")
        return None
    return validate_thread_id(value)


def new_job_id() -> str:
    return f"wake-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / validate_job_id(job_id)


def state_path(job_id: str) -> Path:
    return job_dir(job_id) / "state.json"


def checkpoint_path(job_id: str) -> Path:
    return job_dir(job_id) / "checkpoint.md"


def run_dir(job_id: str) -> Path:
    return job_dir(job_id) / "runs"


def load_job(job_id: str) -> dict[str, Any]:
    path = state_path(job_id)
    if not path.exists():
        raise WakeError(f"job not found: {job_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise WakeError(f"invalid job state: {job_id}")
    return data


def save_job(job: dict[str, Any]) -> None:
    job["updatedAt"] = now()
    atomic_json(state_path(str(job["jobId"])), job)


def all_jobs() -> list[dict[str, Any]]:
    ensure_dirs()
    jobs: list[dict[str, Any]] = []
    for path in sorted(JOBS_DIR.glob("*/state.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                jobs.append(obj)
        except Exception:
            continue
    return jobs


def find_job_for_thread(thread_id: str) -> dict[str, Any] | None:
    validate_thread_id(thread_id)
    matches = [
        job for job in all_jobs()
        if job.get("state") != "completed"
        and thread_id in {job.get("originalThreadId"), job.get("currentThreadId")}
    ]
    if not matches:
        return None
    matches.sort(key=lambda x: int(x.get("updatedAt") or 0), reverse=True)
    return matches[0]


CHECKPOINT_TEMPLATE = """# WAKE Task Checkpoint

## Goal
REPLACE_ME

## Constraints
- Preserve completed work.
- Do not reconstruct or reread the old chat unless this checkpoint explicitly requires it.

## Completed
- None recorded yet.

## Decisions
- None recorded yet.

## Files changed
- None recorded yet.

## Verification
- None recorded yet.

## Current state
Checkpoint created; fill this before arming WAKE.

## Next actions
1. REPLACE_ME

## Do not repeat
- Do not redo completed investigation without evidence it is stale.

## Blockers
- None.

## Handoff
Update this file after every meaningful milestone and before long-running work.
"""


def create_job(
    thread_id: str,
    cwd: str | None,
    goal: str | None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    validate_thread_id(thread_id)
    if model is not None:
        model = model.strip()
        if not MODEL_RE.match(model):
            raise WakeError("unsafe model name")
    if reasoning_effort is not None:
        reasoning_effort = reasoning_effort.strip().lower()
        if reasoning_effort not in REASONING_EFFORTS:
            raise WakeError(f"unsupported reasoning effort: {reasoning_effort}")
    existing = find_job_for_thread(thread_id)
    if existing is not None:
        result = dict(existing)
        result["alreadyExists"] = True
        return result
    root = Path(cwd or os.getcwd()).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise WakeError(f"cwd does not exist: {root}")
    jid = new_job_id()
    jdir = job_dir(jid)
    jdir.mkdir(parents=True, exist_ok=False)
    run_dir(jid).mkdir()
    cp = CHECKPOINT_TEMPLATE
    if goal:
        cp = cp.replace("## Goal\nREPLACE_ME", f"## Goal\n{goal.strip()}", 1)
    checkpoint_path(jid).write_text(cp, encoding="utf-8")
    job = {
        "version": VERSION,
        "jobId": jid,
        "originalThreadId": thread_id,
        "currentThreadId": thread_id,
        "cwd": str(root),
        "checkpointPath": str(checkpoint_path(jid)),
        "state": "draft",
        "checkpointReady": False,
        "generation": 0,
        "model": model,
        "reasoningEffort": reasoning_effort,
        "retryCount": 0,
        "nextRetryAt": None,
        "createdAt": now(),
        "updatedAt": now(),
        "lastError": None,
        "pauseReason": None,
        "lastRunPid": None,
        "lastRunLog": None,
    }
    save_job(job)
    return job


def arm_job(job_id: str) -> dict[str, Any]:
    job = load_job(job_id)
    cp_path = checkpoint_path(job_id)
    text = cp_path.read_text(encoding="utf-8")
    if "## Goal\nREPLACE_ME" in text or "1. REPLACE_ME" in text:
        raise WakeError("checkpoint still contains REPLACE_ME; fill Goal and Next actions first")
    if cp_path.stat().st_size > 65536:
        raise WakeError("checkpoint exceeds 64 KiB; compact it before arming")
    job["checkpointReady"] = True
    job["state"] = "monitoring"
    job["lastError"] = None
    save_job(job)
    return job


def pause_job(job_id: str, reason: str) -> dict[str, Any]:
    job = load_job(job_id)
    job["state"] = "waiting_user"
    job["pauseReason"] = reason.strip() or "waiting for user"
    save_job(job)
    return job


def rearm_job(job_id: str) -> dict[str, Any]:
    job = load_job(job_id)
    if job.get("state") == "completed":
        raise WakeError("completed jobs are immutable; create a new job instead")
    if not job.get("checkpointReady"):
        raise WakeError("job checkpoint is not armed")
    job["state"] = "monitoring"
    job["pauseReason"] = None
    job["lastError"] = None
    save_job(job)
    return job


def stop_job(job_id: str) -> dict[str, Any]:
    job = load_job(job_id)
    if job.get("state") == "completed":
        return job
    job["state"] = "stopped"
    job["pauseReason"] = "stopped by user"
    job["lastRunPid"] = None
    save_job(job)
    return job


def complete_job(job_id: str) -> dict[str, Any]:
    job = load_job(job_id)
    job["state"] = "completed"
    job["completedAt"] = now()
    job["lastRunPid"] = None
    save_job(job)
    return job


def is_process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            cp = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=5, check=False,
                creationflags=hidden_creationflags(),
            )
            return str(pid) in cp.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class StdioAppServer:
    """Persistent hidden app-server used only for account/rateLimits/read."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.out: queue.Queue[Any] = queue.Queue()
        self.stderr: list[str] = []
        self.next_id = 1
        self.lock = threading.RLock()

    def start(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            return
        self.close()
        self.out = queue.Queue()
        self.stderr = []
        kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
            "text": True, "encoding": "utf-8", "errors": "replace", "bufsize": 1,
        }
        flags = hidden_creationflags()
        if flags:
            kwargs["creationflags"] = flags
        self.proc = subprocess.Popen([find_codex(), "app-server"], **kwargs)
        assert self.proc.stdout is not None and self.proc.stderr is not None
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self.request("initialize", {"clientInfo": {
            "name": "codex-wake-watcher", "title": "Codex WAKE Watcher", "version": VERSION,
        }}, timeout=15, skip_start=True)
        self.notify("initialized", {}, skip_start=True)

    def _read_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for line in self.proc.stdout:
                self.out.put(line)
        except Exception as exc:
            self.out.put(exc)
        finally:
            self.out.put(None)

    def _read_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        try:
            for line in self.proc.stderr:
                self.stderr.append(line.rstrip())
                self.stderr[:] = self.stderr[-200:]
        except Exception:
            pass

    def _send(self, obj: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None or self.proc.poll() is not None:
            raise WakeError("app-server is not running")
        self.proc.stdin.write(json.dumps(obj, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def notify(self, method: str, params: dict[str, Any] | None = None, *, skip_start: bool = False) -> None:
        if not skip_start:
            self.start()
        obj: dict[str, Any] = {"method": method}
        if params is not None:
            obj["params"] = params
        self._send(obj)

    def request(self, method: str, params: dict[str, Any] | None = None, *,
                timeout: float = 30, skip_start: bool = False) -> dict[str, Any]:
        with self.lock:
            if not skip_start:
                self.start()
            req_id = self.next_id
            self.next_id += 1
            obj: dict[str, Any] = {"method": method, "id": req_id}
            if params is not None:
                obj["params"] = params
            self._send(obj)
            deadline = time.time() + timeout
            while True:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise WakeError(f"timed out waiting for {method}")
                try:
                    item = self.out.get(timeout=remaining)
                except queue.Empty as exc:
                    raise WakeError(f"timed out waiting for {method}") from exc
                if item is None:
                    raise WakeError("app-server stdout closed; " + " | ".join(self.stderr[-10:]))
                if isinstance(item, Exception):
                    raise WakeError(str(item))
                try:
                    msg = json.loads(str(item).strip())
                except json.JSONDecodeError:
                    continue
                if msg.get("id") != req_id:
                    continue
                if "error" in msg:
                    raise WakeError(f"{method} failed: {msg['error']}")
                result = msg.get("result")
                if not isinstance(result, dict):
                    raise WakeError(f"{method} returned non-object result")
                return result

    def close(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def summarize_quota(raw: dict[str, Any]) -> dict[str, Any]:
    ordinary = raw.get("ordinaryUsageAllowed")
    limits = raw.get("rateLimits")
    if not isinstance(limits, dict):
        limits = {}
    times: list[int] = []
    for key in ("primary", "secondary"):
        item = limits.get(key)
        if isinstance(item, dict) and isinstance(item.get("resetsAt"), int):
            times.append(int(item["resetsAt"]))
    future = sorted(x for x in times if x > now())
    next_reset = future[0] if future else (min(times) if times else None)
    return {
        "ordinaryUsageAllowed": ordinary if isinstance(ordinary, bool) else None,
        "accountPresent": bool(raw.get("accountId")),
        "nextResetAt": next_reset,
        "nextResetAtUtc": iso(next_reset),
        "allResetTimes": sorted(set(times)),
        "rateLimits": limits,
    }


def next_sleep(summary: dict[str, Any]) -> int:
    if summary.get("ordinaryUsageAllowed") is False:
        reset = summary.get("nextResetAt")
        if isinstance(reset, int):
            return min(max(5, reset - now() + 2), 300)
        return 300
    return 60


def continuation_prompt(job: dict[str, Any]) -> str:
    jid = str(job["jobId"])
    cp = str(job["checkpointPath"])
    cwd = str(job["cwd"])
    helper = str(SKILL_ROOT / "watcher" / "wake_watcher.py")
    return f"""Continue WAKE job {jid}. This is a checkpoint handoff, not a chat resume.

Read FIRST and treat as authoritative:
{cp}

Then inspect only the minimum live workspace state needed in:
{cwd}

If that directory is inside a Git worktree, normally inspect:
- git status --short
- git diff --stat
If it is not a Git worktree, skip Git checks without treating that as an error.

Do NOT reconstruct, resume, or reread the previous chat/thread. Do NOT repeat work listed
under Completed or Do not repeat unless verification is demonstrably stale.

Continue from Next actions and work toward the Goal. Update the checkpoint after every
meaningful milestone and before long-running or risky operations. Keep it concise.

If user input/manual action is required, update the checkpoint, then run:
python "{helper}" job-pause --job-id {jid} --reason "<short reason>"

When the Goal is fully verified complete, update the checkpoint, then run:
python "{helper}" job-complete --job-id {jid}

If usage quota stops execution, exit normally; WAKE will create the next checkpoint handoff.
"""


def launch_handoff(job: dict[str, Any]) -> dict[str, Any]:
    jid = str(job["jobId"])
    source_state = str(job.get("state") or "")
    cwd = Path(str(job["cwd"]))
    if not cwd.exists():
        raise WakeError(f"cwd no longer exists: {cwd}")
    jdir = job_dir(jid)
    run_dir(jid).mkdir(parents=True, exist_ok=True)
    generation = int(job.get("generation") or 0) + 1
    log_path = run_dir(jid) / f"run-{generation:04d}-{now()}.jsonl"
    stream = log_path.open("a", encoding="utf-8")
    cmd = [
        find_codex(), "exec", "--json", "--color", "never",
        "--sandbox", "workspace-write", "--skip-git-repo-check",
        "-C", str(cwd), "--add-dir", str(jdir),
    ]
    model = job.get("model")
    if isinstance(model, str) and model:
        cmd.extend(["-m", model])
    effort = job.get("reasoningEffort")
    if isinstance(effort, str) and effort:
        cmd.extend(["-c", f'model_reasoning_effort="{effort}"'])
    cmd.append(continuation_prompt(job))
    kwargs: dict[str, Any] = {
        "stdin": subprocess.DEVNULL, "stdout": stream, "stderr": subprocess.STDOUT,
        "cwd": str(cwd),
    }
    flags = hidden_creationflags()
    if flags:
        kwargs["creationflags"] = flags
    proc = subprocess.Popen(cmd, **kwargs)
    stream.close()
    job["generation"] = generation
    job["state"] = "running"
    if source_state == "quota_waiting":
        job["retryCount"] = 0
    job["nextRetryAt"] = None
    job["currentThreadId"] = None
    job["lastRunPid"] = proc.pid
    job["lastRunLog"] = str(log_path)
    job["lastRunStartedAt"] = now()
    job["lastError"] = None
    save_job(job)
    log(f"job {jid} launched checkpoint handoff generation={generation} pid={proc.pid}")
    return job


def discover_run_thread(job: dict[str, Any]) -> dict[str, Any]:
    path_value = job.get("lastRunLog")
    if not path_value:
        return job
    path = Path(str(path_value))
    if not path.exists():
        return job
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for index, line in enumerate(f):
                if index >= 80:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    tid = event.get("thread_id") or event.get("threadId")
                    if isinstance(tid, str) and THREAD_ID_RE.match(tid):
                        if job.get("currentThreadId") != tid:
                            job["currentThreadId"] = tid
                            save_job(job)
                        break
    except OSError:
        pass
    return job


def classify_run_failure(job: dict[str, Any]) -> tuple[bool, str]:
    path_value = job.get("lastRunLog")
    if not path_value:
        return False, "continuation exited without a run log"
    path = Path(str(path_value))
    if not path.exists():
        return False, "continuation run log is missing"

    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > 131072:
                f.seek(size - 131072)
            text = f.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return False, f"could not read run log: {exc}"

    messages: list[str] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.failed":
            err = event.get("error")
            if isinstance(err, dict) and isinstance(err.get("message"), str):
                messages.append(err["message"])
        elif event.get("type") == "error" and isinstance(event.get("message"), str):
            messages.append(event["message"])
        elif event.get("type") == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "error" and isinstance(item.get("message"), str):
                messages.append(item["message"])

    reason = messages[-1] if messages else "continuation exited without marking job complete or waiting_user"
    haystack = ("\n".join(messages) + "\n" + text[-32768:]).lower()
    retryable_patterns = (
        "selected model is at capacity",
        "request timed out",
        "timed out",
        "temporarily unavailable",
        "service unavailable",
        "connection reset",
        "connection error",
        "connection closed",
        "network error",
        "reconnecting",
        "bad gateway",
        "gateway timeout",
        "http 502",
        "http 503",
        "http 504",
    )
    return any(pattern in haystack for pattern in retryable_patterns), reason


def reconcile_running(job: dict[str, Any], ordinary: bool | None) -> None:
    jid = str(job["jobId"])
    fresh = load_job(jid)
    if fresh.get("state") != "running":
        return
    job = discover_run_thread(fresh)
    pid = job.get("lastRunPid")
    if is_process_alive(int(pid) if isinstance(pid, int) else None):
        return
    if ordinary is False:
        job["state"] = "quota_waiting"
        job["quotaBlockedObservedAt"] = now()
        job["retryCount"] = 0
        job["nextRetryAt"] = None
        job["lastRunPid"] = None
        save_job(job)
        log(f"job {jid} run ended while quota blocked; waiting for next window")
        return

    retryable, reason = classify_run_failure(job)
    if ordinary is True and retryable:
        retry_count = int(job.get("retryCount") or 0) + 1
        if retry_count <= MAX_TRANSIENT_RETRIES:
            delay = min(RETRY_BASE_SECONDS * (2 ** (retry_count - 1)), RETRY_MAX_SECONDS)
            job["state"] = "retry_waiting"
            job["retryCount"] = retry_count
            job["nextRetryAt"] = now() + delay
            job["lastRunPid"] = None
            job["lastError"] = reason
            save_job(job)
            log(f"job {jid} transient failure; retry {retry_count}/{MAX_TRANSIENT_RETRIES} in {delay}s: {reason}")
            return
        reason = f"transient retry limit exceeded ({MAX_TRANSIENT_RETRIES}): {reason}"

    job["state"] = "needs_attention"
    job["lastRunPid"] = None
    job["nextRetryAt"] = None
    job["lastError"] = reason
    save_job(job)
    log(f"job {jid} needs attention: {reason}")


def process_once(app: StdioAppServer) -> int:
    jobs = [j for j in all_jobs() if j.get("checkpointReady") and j.get("state") not in {"completed", "draft", "stopped"}]
    if not jobs:
        return 60
    try:
        summary = summarize_quota(app.request("account/rateLimits/read"))
    except Exception as exc:
        log(f"quota read failed: {exc}")
        app.close()
        return 60
    ordinary = summary.get("ordinaryUsageAllowed")
    log(f"quota ordinaryUsageAllowed={ordinary} nextResetAt={summary.get('nextResetAtUtc')} jobs={len(jobs)}")

    for job in jobs:
        jid = str(job["jobId"])
        try:
            job = load_job(jid)
        except Exception:
            continue
        state = str(job.get("state"))
        if state in {"completed", "draft", "stopped", "waiting_user", "needs_attention"}:
            continue
        if state == "running":
            reconcile_running(job, ordinary)
            continue
        if ordinary is False:
            if state != "quota_waiting":
                job["state"] = "quota_waiting"
                job["quotaBlockedObservedAt"] = now()
                job["retryCount"] = 0
                job["nextRetryAt"] = None
                job["lastError"] = None
                save_job(job)
                log(f"job {jid} entered quota_waiting")
            continue
        if ordinary is True and state in {"quota_waiting", "retry_waiting"}:
            if state == "retry_waiting":
                retry_at = job.get("nextRetryAt")
                if isinstance(retry_at, int) and now() < retry_at:
                    continue
            try:
                latest = load_job(jid)
                if latest.get("state") not in {"quota_waiting", "retry_waiting"}:
                    continue
                retry_at = latest.get("nextRetryAt")
                if latest.get("state") == "retry_waiting" and isinstance(retry_at, int) and now() < retry_at:
                    continue
                launch_handoff(latest)
            except Exception as exc:
                latest = load_job(jid)
                if latest.get("state") in {"quota_waiting", "retry_waiting"}:
                    latest["state"] = "needs_attention"
                    latest["lastError"] = str(exc)
                    latest["nextRetryAt"] = None
                    save_job(latest)
                    log(f"job {jid} handoff launch failed: {exc}")
    return next_sleep(summary)

def watcher_status() -> dict[str, Any]:
    pid: int | None = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            pid = None
    jobs = all_jobs()
    counts: dict[str, int] = {}
    for job in jobs:
        key = str(job.get("state") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "version": VERSION,
        "pid": pid,
        "running": is_process_alive(pid),
        "wakeHome": str(WAKE_HOME),
        "jobsDir": str(JOBS_DIR),
        "jobCount": len(jobs),
        "stateCounts": counts,
        "currentThreadEnvPresent": bool(os.environ.get("CODEX_THREAD_ID")),
    }


def handle_stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def run_daemon() -> None:
    ensure_dirs()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    signal.signal(signal.SIGINT, handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop)
    app = StdioAppServer()
    log(f"WAKE watcher {VERSION} started pid={os.getpid()}")
    try:
        while not _STOP:
            delay = max(1, process_once(app))
            end = time.time() + delay
            while not _STOP and time.time() < end:
                time.sleep(min(1, end - time.time()))
    finally:
        app.close()
        try:
            if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
        log("WAKE watcher stopped")


def doctor() -> int:
    result: dict[str, Any] = {
        "version": VERSION,
        "python": sys.executable,
        "codex": shutil.which("codex"),
        "windowsNoWindow": bool(hidden_creationflags()) if os.name == "nt" else None,
        "watcher": watcher_status(),
    }
    app = StdioAppServer()
    try:
        result["quota"] = summarize_quota(app.request("account/rateLimits/read"))
        result["quotaReadOk"] = True
    except Exception as exc:
        result["quotaReadOk"] = False
        result["quotaError"] = str(exc)
    finally:
        app.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("quotaReadOk") else 1


def current_job(required: bool = True) -> dict[str, Any] | None:
    tid = current_thread_id(required)
    if tid is None:
        return None
    job = find_job_for_thread(tid)
    if job is None and required:
        raise WakeError(f"no active WAKE job is associated with thread {tid}")
    return job


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description="WAKE checkpoint-first job continuation")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in (
        "run", "once", "quota", "status", "doctor", "job-list",
        "job-current", "job-stop-current", "job-rearm-current", "job-complete-current",
    ):
        sub.add_parser(name)

    jc = sub.add_parser("job-create")
    jc.add_argument("--thread-id", required=True)
    jc.add_argument("--cwd")
    jc.add_argument("--goal")
    jc.add_argument("--model")
    jc.add_argument("--reasoning-effort")
    jcc = sub.add_parser("job-create-current")
    jcc.add_argument("--cwd")
    jcc.add_argument("--goal")
    jcc.add_argument("--model")
    jcc.add_argument("--reasoning-effort")
    for name in ("job-arm", "job-status", "job-rearm", "job-stop", "job-complete"):
        sp = sub.add_parser(name)
        sp.add_argument("--job-id", required=True)
    jp = sub.add_parser("job-pause")
    jp.add_argument("--job-id", required=True)
    jp.add_argument("--reason", default="waiting for user")
    jpc = sub.add_parser("job-pause-current")
    jpc.add_argument("--reason", default="waiting for user")
    args = p.parse_args()

    if args.cmd == "run":
        run_daemon(); return 0
    if args.cmd == "status":
        print_json(watcher_status()); return 0
    if args.cmd == "doctor":
        return doctor()
    if args.cmd == "job-list":
        print_json(all_jobs()); return 0
    if args.cmd == "job-current":
        print_json(current_job(True)); return 0
    if args.cmd == "job-create":
        print_json(create_job(
            args.thread_id, args.cwd, args.goal, args.model, args.reasoning_effort
        )); return 0
    if args.cmd == "job-create-current":
        print_json(create_job(
            current_thread_id(True), args.cwd, args.goal, args.model, args.reasoning_effort
        )); return 0
    if args.cmd == "job-arm":
        print_json(arm_job(args.job_id)); return 0
    if args.cmd == "job-status":
        print_json(load_job(args.job_id)); return 0
    if args.cmd == "job-rearm":
        print_json(rearm_job(args.job_id)); return 0
    if args.cmd == "job-stop":
        print_json(stop_job(args.job_id)); return 0
    if args.cmd == "job-pause":
        print_json(pause_job(args.job_id, args.reason)); return 0
    if args.cmd == "job-complete":
        print_json(complete_job(args.job_id)); return 0
    if args.cmd == "job-rearm-current":
        print_json(rearm_job(str(current_job(True)["jobId"]))); return 0
    if args.cmd == "job-stop-current":
        print_json(stop_job(str(current_job(True)["jobId"]))); return 0
    if args.cmd == "job-pause-current":
        print_json(pause_job(str(current_job(True)["jobId"]), args.reason)); return 0
    if args.cmd == "job-complete-current":
        print_json(complete_job(str(current_job(True)["jobId"]))); return 0
    app = StdioAppServer()
    try:
        if args.cmd == "quota":
            print_json(summarize_quota(app.request("account/rateLimits/read"))); return 0
        if args.cmd == "once":
            print_json({"nextCheckSeconds": process_once(app)}); return 0
    finally:
        app.close()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

