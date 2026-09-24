#!/usr/bin/env python3
"""Local quota watcher for WAKE v0.3.

This helper does not store OpenAI credentials and does not make model turns when
checking quota. It asks the locally installed Codex App Server for
account/rateLimits/read and only launches an exact registered thread after
ordinaryUsageAllowed becomes true.

Thread resume is intentionally explicit and experimental for Codex Desktop
sessions because host/UI synchronization can vary across Codex versions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "0.3.2"
SKILL_ROOT = Path.home() / ".codex" / "skills" / "wake"
STATE_DIR = SKILL_ROOT / ".state"
REGISTRY_FILE = STATE_DIR / "registrations.json"
PID_FILE = STATE_DIR / "watcher.pid"
LOG_FILE = STATE_DIR / "watcher.log"

DEFAULT_RECOVERY_PROMPT = (
    "[WAKE quota recovery] Included Codex usage is available again. "
    "Return to this exact conversation and classify state before acting: "
    "if WAITING_USER, pause WAKE; if ACTIVE, do not duplicate work; "
    "if DONE, stop WAKE; otherwise continue only the unfinished task."
)

THREAD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_STOP = False


def utc_now() -> int:
    return int(time.time())


def iso(ts: int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    ensure_state_dir()
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_registry() -> dict[str, dict[str, Any]]:
    ensure_state_dir()
    if not REGISTRY_FILE.exists():
        return {}
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    entries = data.get("registrations", {})
    return entries if isinstance(entries, dict) else {}


def save_registry(entries: dict[str, dict[str, Any]]) -> None:
    ensure_state_dir()
    tmp = REGISTRY_FILE.with_suffix(".tmp")
    payload = {
        "version": VERSION,
        "updatedAt": utc_now(),
        "registrations": entries,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REGISTRY_FILE)


def find_codex() -> str:
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex executable was not found in PATH")
    return codex


def app_server_commands(codex: str) -> list[list[str]]:
    return [
        [codex, "app-server"],
        [codex, "app-server", "--stdio"],
    ]


def _stderr_reader(stream: Any, sink: list[str]) -> None:
    try:
        for line in stream:
            sink.append(line.rstrip())
            if len(sink) > 200:
                del sink[:100]
    except Exception:
        pass


def _stdout_reader(stream: Any, out_queue: Any) -> None:
    try:
        for line in stream:
            out_queue.put(line)
    except Exception as exc:
        out_queue.put(exc)
    finally:
        out_queue.put(None)


def _send_json(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise RuntimeError("app-server stdin is unavailable")
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def _wait_for_response(out_queue: Any, request_id: int, timeout: float) -> dict[str, Any]:
    import queue

    deadline = time.time() + timeout
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise RuntimeError(f"timed out waiting for app-server response id={request_id}")
        try:
            item = out_queue.get(timeout=remaining)
        except queue.Empty:
            raise RuntimeError(f"timed out waiting for app-server response id={request_id}")
        if item is None:
            raise RuntimeError("app-server stdout closed before the requested response")
        if isinstance(item, Exception):
            raise RuntimeError(f"app-server stdout reader failed: {item}")
        line = str(item).strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("id") != request_id:
            continue
        if "error" in obj:
            raise RuntimeError(f"app-server error: {obj['error']}")
        result = obj.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("app-server returned a non-object result")
        return result


def read_rate_limits(timeout: int = 30) -> dict[str, Any]:
    import queue
    import threading

    codex = find_codex()
    last_error: str | None = None

    for cmd in app_server_commands(codex):
        proc: subprocess.Popen[str] | None = None
        stderr_lines: list[str] = []
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert proc.stdout is not None
            assert proc.stderr is not None

            out_queue: queue.Queue[Any] = queue.Queue()
            threading.Thread(target=_stdout_reader, args=(proc.stdout, out_queue), daemon=True).start()
            threading.Thread(target=_stderr_reader, args=(proc.stderr, stderr_lines), daemon=True).start()

            init_id = 1
            quota_id = 7
            _send_json(
                proc,
                {
                    "method": "initialize",
                    "id": init_id,
                    "params": {
                        "clientInfo": {
                            "name": "codex-wake-watcher",
                            "title": "Codex WAKE Watcher",
                            "version": VERSION,
                        }
                    },
                },
            )
            _wait_for_response(out_queue, init_id, timeout=min(timeout, 15))
            _send_json(proc, {"method": "initialized", "params": {}})
            _send_json(proc, {"method": "account/rateLimits/read", "id": quota_id})
            return _wait_for_response(out_queue, quota_id, timeout=timeout)
        except Exception as exc:
            detail = "\n".join(stderr_lines[-20:]).strip()
            last_error = f"{exc}; stderr={detail}" if detail else str(exc)
        finally:
            if proc is not None:
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

    raise RuntimeError(last_error or "unable to query Codex rate limits")


def collect_reset_times(value: Any, out: set[int]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "resetsAt" and isinstance(item, int):
                out.add(item)
            else:
                collect_reset_times(item, out)
    elif isinstance(value, list):
        for item in value:
            collect_reset_times(item, out)


def summarize_quota(result: dict[str, Any]) -> dict[str, Any]:
    ordinary = result.get("ordinaryUsageAllowed")
    if ordinary not in (True, False, None):
        ordinary = None

    resets: set[int] = set()
    collect_reset_times(result.get("rateLimits"), resets)
    collect_reset_times(result.get("rateLimitsByLimitId"), resets)

    now = utc_now()
    future = sorted(ts for ts in resets if ts > now - 2)
    return {
        "ordinaryUsageAllowed": ordinary,
        "accountPresent": bool(result.get("accountId")),
        "nextResetAt": future[0] if future else None,
        "nextResetAtUtc": iso(future[0]) if future else None,
        "allResetTimes": future,
        "rateLimits": result.get("rateLimits"),
        "rateLimitsByLimitId": result.get("rateLimitsByLimitId"),
    }


def validate_thread_id(thread_id: str) -> None:
    if not THREAD_ID_RE.match(thread_id):
        raise SystemExit(
            "Refusing unsafe thread id. Supply the exact Codex thread/session id; "
            "WAKE never guesses or uses --last."
        )


def current_thread_id(required: bool = True) -> str | None:
    value = os.environ.get("CODEX_THREAD_ID", "").strip()
    if not value:
        if required:
            raise SystemExit(
                "CODEX_THREAD_ID is not present. Run this command from a shell/tool "
                "invoked by the target Codex conversation, not from a normal terminal."
            )
        return None
    validate_thread_id(value)
    return value


def normalize_cwd(cwd: str | None) -> Path:
    path = Path(cwd or os.getcwd()).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"cwd does not exist or is not a directory: {path}")
    return path


def register_thread(thread_id: str, cwd: str | None, prompt: str) -> dict[str, Any]:
    validate_thread_id(thread_id)
    path = normalize_cwd(cwd)
    entries = load_registry()
    now = utc_now()
    old = entries.get(thread_id, {})
    entry = {
        "threadId": thread_id,
        "cwd": str(path),
        "prompt": prompt,
        "state": "monitoring",
        "registeredAt": old.get("registeredAt") or now,
        "updatedAt": now,
        "quotaBlockedObservedAt": old.get("quotaBlockedObservedAt"),
        "lastLaunchAt": old.get("lastLaunchAt"),
        "launchLog": old.get("launchLog"),
        "lastError": None,
        "pauseReason": None,
    }
    entries[thread_id] = entry
    save_registry(entries)
    return entry


def register_current(cwd: str | None, prompt: str) -> None:
    thread_id = current_thread_id(required=True)
    assert thread_id is not None
    print(json.dumps(register_thread(thread_id, cwd, prompt), ensure_ascii=False, indent=2))


def pause_thread(thread_id: str, reason: str) -> None:
    validate_thread_id(thread_id)
    entries = load_registry()
    entry = entries.get(thread_id)
    if not entry:
        raise SystemExit("thread is not registered with WAKE")
    entry["state"] = "waiting_user"
    entry["pauseReason"] = reason or "waiting for user"
    entry["updatedAt"] = utc_now()
    entries[thread_id] = entry
    save_registry(entries)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def pause_current(reason: str) -> None:
    thread_id = current_thread_id(required=True)
    assert thread_id is not None
    pause_thread(thread_id, reason)


def resume_thread(thread_id: str, cwd: str | None = None) -> None:
    validate_thread_id(thread_id)
    entries = load_registry()
    entry = entries.get(thread_id)
    if not entry:
        entry = register_thread(thread_id, cwd, DEFAULT_RECOVERY_PROMPT)
    else:
        if cwd:
            entry["cwd"] = str(normalize_cwd(cwd))
        entry["state"] = "monitoring"
        entry["pauseReason"] = None
        entry["updatedAt"] = utc_now()
        entry["lastError"] = None
        entries[thread_id] = entry
        save_registry(entries)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def resume_current(cwd: str | None = None) -> None:
    thread_id = current_thread_id(required=True)
    assert thread_id is not None
    resume_thread(thread_id, cwd)


def unregister(thread_id: str) -> None:
    validate_thread_id(thread_id)
    entries = load_registry()
    existed = entries.pop(thread_id, None)
    save_registry(entries)
    print("unregistered" if existed else "not registered")


def unregister_current() -> None:
    thread_id = current_thread_id(required=True)
    assert thread_id is not None
    unregister(thread_id)


def show_current() -> None:
    thread_id = current_thread_id(required=True)
    assert thread_id is not None
    entry = load_registry().get(thread_id)
    print(json.dumps({"threadId": thread_id, "registration": entry}, ensure_ascii=False, indent=2))


def arm_quota(thread_id: str, cwd: str, prompt: str) -> None:
    entry = register_thread(thread_id, cwd, prompt)
    entries = load_registry()
    entry["state"] = "quota_waiting"
    entry["quotaBlockedObservedAt"] = utc_now()
    entry["updatedAt"] = utc_now()
    entries[thread_id] = entry
    save_registry(entries)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def disarm(thread_id: str) -> None:
    unregister(thread_id)


def list_regs() -> None:
    print(json.dumps(load_registry(), ensure_ascii=False, indent=2))


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
            return str(pid) in completed.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def watcher_status() -> dict[str, Any]:
    pid: int | None = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = None
    entries = load_registry()
    counts: dict[str, int] = {}
    for entry in entries.values():
        state = str(entry.get("state") or "unknown")
        counts[state] = counts.get(state, 0) + 1
    return {
        "pid": pid,
        "running": bool(pid and is_process_alive(pid)),
        "registry": str(REGISTRY_FILE),
        "log": str(LOG_FILE),
        "registeredCount": len(entries),
        "stateCounts": counts,
        "currentThreadEnvPresent": bool(os.environ.get("CODEX_THREAD_ID")),
    }


def safe_name(thread_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", thread_id)[:80]


def launch_resume(entry: dict[str, Any]) -> tuple[bool, str]:
    thread_id = str(entry["threadId"])
    validate_thread_id(thread_id)
    cwd = Path(str(entry["cwd"]))
    prompt = str(entry.get("prompt") or DEFAULT_RECOVERY_PROMPT)
    if not cwd.exists():
        return False, f"cwd no longer exists: {cwd}"

    codex = find_codex()
    ensure_state_dir()
    log_path = STATE_DIR / f"resume-{safe_name(thread_id)}-{utc_now()}.log"
    stream = log_path.open("a", encoding="utf-8")
    cmd = [
        codex,
        "exec",
        "resume",
        thread_id,
        "--json",
        "--skip-git-repo-check",
        prompt,
    ]

    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "stdin": subprocess.DEVNULL,
        "stdout": stream,
        "stderr": subprocess.STDOUT,
        "close_fds": os.name != "nt",
    }
    if os.name == "nt":
        creationflags = 0
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        kwargs["creationflags"] = creationflags

    try:
        subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        stream.close()
        return False, str(exc)
    stream.close()
    return True, str(log_path)


def next_sleep_seconds(summary: dict[str, Any]) -> int:
    ordinary = summary.get("ordinaryUsageAllowed")
    if ordinary is None:
        return 60
    next_reset = summary.get("nextResetAt")
    if ordinary is False and isinstance(next_reset, int):
        until = max(5, next_reset - utc_now() + 2)
        return min(until, 300)
    return 60


def process_once() -> int:
    entries = load_registry()
    tracked = {
        k: v for k, v in entries.items()
        if v.get("state") in {"monitoring", "quota_waiting"}
    }
    if not tracked:
        return 30

    try:
        summary = summarize_quota(read_rate_limits())
    except Exception as exc:
        log(f"quota read failed: {exc}")
        return 60

    ordinary = summary.get("ordinaryUsageAllowed")
    waiting = sum(1 for v in tracked.values() if v.get("state") == "quota_waiting")
    log(
        "quota: ordinaryUsageAllowed="
        f"{ordinary} nextResetAt={summary.get('nextResetAtUtc')} "
        f"tracked={len(tracked)} quota_waiting={waiting}"
    )

    changed = False
    if ordinary is False:
        now = utc_now()
        for thread_id, entry in tracked.items():
            if entry.get("state") == "monitoring":
                entry["state"] = "quota_waiting"
                entry["quotaBlockedObservedAt"] = now
                entry["updatedAt"] = now
                entries[thread_id] = entry
                changed = True
                log(f"thread {thread_id} entered quota_waiting")
        if changed:
            save_registry(entries)
        return next_sleep_seconds(summary)

    if ordinary is not True:
        return next_sleep_seconds(summary)

    for thread_id, entry in list(entries.items()):
        if entry.get("state") != "quota_waiting":
            continue
        ok, detail = launch_resume(entry)
        if ok:
            entry["state"] = "monitoring"
            entry["lastLaunchAt"] = utc_now()
            entry["launchLog"] = detail
            entry["lastError"] = None
            entry["updatedAt"] = utc_now()
            log(f"quota recovered; launched exact thread {thread_id}; log={detail}")
        else:
            entry["lastError"] = detail
            entry["updatedAt"] = utc_now()
            log(f"failed to launch exact thread {thread_id}: {detail}")
        entries[thread_id] = entry
        changed = True

    if changed:
        save_registry(entries)
    return 30


def handle_stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def run_daemon() -> None:
    ensure_state_dir()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    signal.signal(signal.SIGINT, handle_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop)
    log(f"WAKE watcher {VERSION} started pid={os.getpid()}")
    try:
        while not _STOP:
            delay = process_once()
            end = time.time() + max(1, delay)
            while not _STOP and time.time() < end:
                time.sleep(min(1, end - time.time()))
    finally:
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
        "watcher": watcher_status(),
    }
    try:
        result["quota"] = summarize_quota(read_rate_limits())
        result["quotaReadOk"] = True
    except Exception as exc:
        result["quotaReadOk"] = False
        result["quotaError"] = str(exc)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["quotaReadOk"] else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="WAKE local quota watcher")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("quota", help="Read Codex rate limits once")
    sub.add_parser("run", help="Run the watcher loop in the foreground")
    sub.add_parser("once", help="Process registrations once")
    sub.add_parser("list", help="List exact-thread registrations")
    sub.add_parser("status", help="Show watcher process/registry status")
    sub.add_parser("doctor", help="Check Codex and quota-read integration")

    register = sub.add_parser("register", help="Register one exact thread for quota monitoring")
    register.add_argument("--thread-id", required=True)
    register.add_argument("--cwd")
    register.add_argument("--prompt", default=DEFAULT_RECOVERY_PROMPT)

    register_current_p = sub.add_parser(
        "register-current",
        help="Register CODEX_THREAD_ID from the current Codex shell/tool environment",
    )
    register_current_p.add_argument("--cwd")
    register_current_p.add_argument("--prompt", default=DEFAULT_RECOVERY_PROMPT)

    pause = sub.add_parser("pause", help="Mark one exact thread WAITING_USER")
    pause.add_argument("--thread-id", required=True)
    pause.add_argument("--reason", default="waiting for user")

    pause_current_p = sub.add_parser("pause-current", help="Mark current CODEX_THREAD_ID WAITING_USER")
    pause_current_p.add_argument("--reason", default="waiting for user")

    resume = sub.add_parser("resume-monitoring", help="Re-enable quota monitoring for one thread")
    resume.add_argument("--thread-id", required=True)
    resume.add_argument("--cwd")

    resume_current_p = sub.add_parser(
        "resume-current",
        help="Re-enable monitoring for current CODEX_THREAD_ID",
    )
    resume_current_p.add_argument("--cwd")

    unregister_p = sub.add_parser("unregister", help="Remove one exact thread registration")
    unregister_p.add_argument("--thread-id", required=True)
    sub.add_parser("unregister-current", help="Remove current CODEX_THREAD_ID registration")
    sub.add_parser("current", help="Show registration for current CODEX_THREAD_ID")

    arm = sub.add_parser("arm-quota", help="Immediately mark one exact thread quota-waiting")
    arm.add_argument("--thread-id", required=True)
    arm.add_argument("--cwd", required=True)
    arm.add_argument("--prompt", default=DEFAULT_RECOVERY_PROMPT)

    dis = sub.add_parser("disarm", help="Alias for unregister")
    dis.add_argument("--thread-id", required=True)
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "quota":
        print(json.dumps(summarize_quota(read_rate_limits()), ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        run_daemon()
        return 0
    if args.command == "once":
        delay = process_once()
        print(json.dumps({"nextCheckSeconds": delay}, indent=2))
        return 0
    if args.command == "list":
        list_regs()
        return 0
    if args.command == "status":
        print(json.dumps(watcher_status(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "doctor":
        return doctor()
    if args.command == "register":
        print(json.dumps(register_thread(args.thread_id, args.cwd, args.prompt), ensure_ascii=False, indent=2))
        return 0
    if args.command == "register-current":
        register_current(args.cwd, args.prompt)
        return 0
    if args.command == "pause":
        pause_thread(args.thread_id, args.reason)
        return 0
    if args.command == "pause-current":
        pause_current(args.reason)
        return 0
    if args.command == "resume-monitoring":
        resume_thread(args.thread_id, args.cwd)
        return 0
    if args.command == "resume-current":
        resume_current(args.cwd)
        return 0
    if args.command == "unregister":
        unregister(args.thread_id)
        return 0
    if args.command == "unregister-current":
        unregister_current()
        return 0
    if args.command == "current":
        show_current()
        return 0
    if args.command == "arm-quota":
        arm_quota(args.thread_id, args.cwd, args.prompt)
        return 0
    if args.command == "disarm":
        disarm(args.thread_id)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
