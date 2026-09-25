import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).parents[1] / "watcher" / "wake_watcher.py"
spec = importlib.util.spec_from_file_location("wake_watcher", MODULE_PATH)
wake = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(wake)


class FakeApp:
    def __init__(self, ordinary):
        self.ordinary = ordinary

    def request(self, method):
        assert method == "account/rateLimits/read"
        return {
            "ordinaryUsageAllowed": self.ordinary,
            "accountId": "x",
            "rateLimits": {
                "primary": {"usedPercent": 10, "resetsAt": wake.now() + 60},
                "secondary": {"usedPercent": 20, "resetsAt": wake.now() + 3600},
            },
        }

    def close(self):
        pass


class WakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.old = (wake.WAKE_HOME, wake.JOBS_DIR, wake.PID_FILE, wake.LOG_FILE)
        wake.WAKE_HOME = root / "wake"
        wake.JOBS_DIR = wake.WAKE_HOME / "jobs"
        wake.PID_FILE = wake.WAKE_HOME / "watcher.pid"
        wake.LOG_FILE = wake.WAKE_HOME / "watcher.log"
        self.cwd = root / "repo"
        self.cwd.mkdir()

    def tearDown(self):
        wake.WAKE_HOME, wake.JOBS_DIR, wake.PID_FILE, wake.LOG_FILE = self.old
        self.tmp.cleanup()

    def create_ready_job(self):
        job = wake.create_job("thread-12345678", str(self.cwd), "Finish the project")
        cp = wake.checkpoint_path(job["jobId"])
        text = cp.read_text(encoding="utf-8").replace("1. REPLACE_ME", "1. Run tests")
        cp.write_text(text, encoding="utf-8")
        return wake.arm_job(job["jobId"])

    def test_create_job_is_draft_and_durable(self):
        job = wake.create_job("thread-12345678", str(self.cwd), "Ship it")
        self.assertEqual(job["state"], "draft")
        self.assertFalse(job["checkpointReady"])
        self.assertTrue(wake.checkpoint_path(job["jobId"]).exists())

    def test_arm_rejects_placeholder(self):
        job = wake.create_job("thread-12345678", str(self.cwd), None)
        with self.assertRaises(wake.WakeError):
            wake.arm_job(job["jobId"])

    def test_arm_pause_rearm_complete(self):
        job = self.create_ready_job()
        jid = job["jobId"]
        self.assertEqual(wake.pause_job(jid, "need approval")["state"], "waiting_user")
        self.assertEqual(wake.rearm_job(jid)["state"], "monitoring")
        self.assertEqual(wake.complete_job(jid)["state"], "completed")
        with self.assertRaises(wake.WakeError):
            wake.rearm_job(jid)

    def test_duplicate_thread_reuses_existing_job(self):
        first = wake.create_job("thread-12345678", str(self.cwd), "One")
        second = wake.create_job("thread-12345678", str(self.cwd), "Two")
        self.assertEqual(first["jobId"], second["jobId"])
        self.assertTrue(second["alreadyExists"])

    def test_stop_prevents_auto_launch(self):
        job = self.create_ready_job()
        wake.stop_job(job["jobId"])
        with mock.patch.object(wake, "launch_handoff") as launch:
            wake.process_once(FakeApp(True))
            launch.assert_not_called()
        self.assertEqual(wake.load_job(job["jobId"])["state"], "stopped")

    def test_quota_false_moves_monitoring_to_waiting(self):
        job = self.create_ready_job()
        delay = wake.process_once(FakeApp(False))
        self.assertGreaterEqual(delay, 5)
        self.assertEqual(wake.load_job(job["jobId"])["state"], "quota_waiting")

    def test_quota_recovery_launches_new_handoff(self):
        job = self.create_ready_job()
        job["state"] = "quota_waiting"
        wake.save_job(job)
        with mock.patch.object(wake, "launch_handoff") as launch:
            launch.side_effect = lambda j: j
            wake.process_once(FakeApp(True))
            launch.assert_called_once()
            self.assertEqual(launch.call_args.args[0]["jobId"], job["jobId"])

    def test_dead_run_needs_attention_when_quota_available(self):
        job = self.create_ready_job()
        job["state"] = "running"
        job["lastRunPid"] = 99999999
        wake.save_job(job)
        with mock.patch.object(wake, "is_process_alive", return_value=False):
            wake.process_once(FakeApp(True))
        self.assertEqual(wake.load_job(job["jobId"])["state"], "needs_attention")

    def test_dead_run_returns_to_waiting_when_blocked(self):
        job = self.create_ready_job()
        job["state"] = "running"
        job["lastRunPid"] = 99999999
        wake.save_job(job)
        with mock.patch.object(wake, "is_process_alive", return_value=False):
            wake.process_once(FakeApp(False))
        self.assertEqual(wake.load_job(job["jobId"])["state"], "quota_waiting")

    def test_prompt_is_checkpoint_first(self):
        job = self.create_ready_job()
        prompt = wake.continuation_prompt(job)
        self.assertIn(job["checkpointPath"], prompt)
        self.assertIn("Do NOT reconstruct, resume, or reread", prompt)
        self.assertIn("job-complete", prompt)
        self.assertIn("job-pause", prompt)

    def test_launch_handoff_creates_new_exec_not_resume(self):
        job = self.create_ready_job()
        fake_proc = mock.Mock(pid=4242)
        with mock.patch.object(wake, "find_codex", return_value="codex"), \
             mock.patch.object(wake.subprocess, "Popen", return_value=fake_proc) as popen:
            result = wake.launch_handoff(job)
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[1], "exec")
        self.assertNotIn("resume", cmd)
        self.assertIn("--add-dir", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertEqual(result["state"], "running")
        self.assertEqual(result["lastRunPid"], 4242)

    def test_transient_capacity_failure_enters_retry_waiting(self):
        job = self.create_ready_job()
        runlog = wake.run_dir(job["jobId"]) / "run.jsonl"
        runlog.write_text(
            '{"type":"turn.failed","error":{"message":"Selected model is at capacity. Please try a different model."}}\n',
            encoding="utf-8",
        )
        job["state"] = "running"
        job["lastRunPid"] = 99999999
        job["lastRunLog"] = str(runlog)
        wake.save_job(job)
        with mock.patch.object(wake, "is_process_alive", return_value=False):
            wake.process_once(FakeApp(True))
        result = wake.load_job(job["jobId"])
        self.assertEqual(result["state"], "retry_waiting")
        self.assertEqual(result["retryCount"], 1)
        self.assertGreater(result["nextRetryAt"], wake.now())

    def test_retry_waiting_launches_when_due(self):
        job = self.create_ready_job()
        job["state"] = "retry_waiting"
        job["retryCount"] = 1
        job["nextRetryAt"] = wake.now() - 1
        wake.save_job(job)
        with mock.patch.object(wake, "launch_handoff") as launch:
            launch.side_effect = lambda j: j
            wake.process_once(FakeApp(True))
            launch.assert_called_once()

    def test_launch_honors_optional_model_and_effort(self):
        job = wake.create_job(
            "thread-model-12345678", str(self.cwd), "Finish",
            model="gpt-5.6-luna", reasoning_effort="low",
        )
        cp = wake.checkpoint_path(job["jobId"])
        cp.write_text(cp.read_text(encoding="utf-8").replace("1. REPLACE_ME", "1. Test"), encoding="utf-8")
        job = wake.arm_job(job["jobId"])
        fake_proc = mock.Mock(pid=4243)
        with mock.patch.object(wake, "find_codex", return_value="codex"), \
             mock.patch.object(wake.subprocess, "Popen", return_value=fake_proc) as popen:
            wake.launch_handoff(job)
        cmd = popen.call_args.args[0]
        self.assertIn("gpt-5.6-luna", cmd)
        self.assertIn('model_reasoning_effort="low"', cmd)

    def test_summarize_quota_hides_account_id(self):
        future = wake.now() + 120
        result = wake.summarize_quota({
            "ordinaryUsageAllowed": False,
            "accountId": "secret",
            "rateLimits": {"primary": {"resetsAt": future}, "secondary": {}},
        })
        self.assertFalse(result["ordinaryUsageAllowed"])
        self.assertTrue(result["accountPresent"])
        self.assertEqual(result["nextResetAt"], future)
        self.assertNotIn("accountId", result)


if __name__ == "__main__":
    unittest.main()

