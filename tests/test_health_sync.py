"""Run with: python3 -m unittest discover -s tests -v"""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "health-daily-sync.py"
SPEC = importlib.util.spec_from_file_location("health_sync", SCRIPT)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo_patch = mock.patch.object(sync, "REPO", Path(self.temp.name))
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)

    def test_response_validation(self):
        for bad in ([], {"res": "error"}, {"success": False, "res": {"trains": []}},
                    {"res": {"trains": {}}}):
            with self.assertRaises(ValueError):
                sync.validate_response(bad)
        self.assertEqual(sync.validate_response({"res": {"trains": []}})["res"]["trains"], [])

    def test_preserve_manual_notes_and_other_sections(self):
        day = dt.date(2026, 10, 9)
        path = sync.REPO / "data/daily/2026-10-09.md"
        path.parent.mkdir(parents=True)
        path.write_text("# 2026-10-09\n\n## Training\n- Ran 5km\n\n## Notes\n- Felt good\n")
        sync.update_daily(day, "- Squat: 60kg x 8 x 3")
        sync.update_daily(day, "- Squat: 65kg x 8 x 3")
        result = path.read_text()
        self.assertIn("- Ran 5km", result)
        self.assertIn("- Felt good", result)
        self.assertIn("65kg", result)
        self.assertNotIn("60kg", result)
        self.assertEqual(result.count(sync.START_MARKER), 1)

    def test_zero_weight_and_reps(self):
        path = sync.REPO / "workout.json"
        path.write_text(json.dumps({"res": {"trains": [{
            "title": "Lift", "movements": [{"name": "Exercise", "sets": [
                {"done": True, "weight": 0, "reps": 0}
            ]}]
        }]}}))
        self.assertIn("0kg x 0 x 1", sync.summarize_workouts(path))

    def test_last_seven_calendar_days(self):
        day = dt.date(2026, 10, 9)
        for date in (day - dt.timedelta(days=10), day - dt.timedelta(days=1)):
            path = sync.REPO / "data/workouts" / f"{date}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"res": {"trains": [{"title": "Gym", "movements": []}]}}))
            log = sync.REPO / "data/daily" / f"{date}.md"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(f"# {date}\n\n## Training\n- Logged\n")
        sync.build_summary(day)
        summary = (sync.REPO / "SUMMARY.md").read_text()
        self.assertIn("Trained 1 of the last 7 calendar days", summary)

    def test_cache_timestamp_ignores_worktree_mtime(self):
        day = dt.date(2026, 10, 9)
        now = dt.datetime(2026, 10, 9, 18, 0, tzinfo=dt.timezone.utc)
        dest = sync.REPO / "data/workouts/2026-10-09.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps({"res": {"trains": []}}))
        sync.cache_metadata_path(day).write_text(json.dumps({
            "date": "2026-10-09", "fetched_at": now.isoformat(), "source": "SynFit"
        }))
        # Git checkout or file copying can change file mtime independently.
        os.utime(dest, (1, 1))
        with mock.patch.object(sync, "local_now", return_value=now):
            self.assertTrue(sync.cache_is_fresh(day))
            with mock.patch.object(sync, "urlopen", side_effect=AssertionError("unexpected API call")):
                self.assertEqual(sync.fetch_workouts(day, "dummy"), dest)

    def test_cache_requires_valid_metadata(self):
        day = dt.date(2026, 10, 9)
        now = dt.datetime(2026, 10, 9, 18, 0, tzinfo=dt.timezone.utc)
        dest = sync.REPO / "data/workouts/2026-10-09.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps({"res": {"trains": []}}))
        with mock.patch.object(sync, "local_now", return_value=now):
            self.assertFalse(sync.cache_is_fresh(day))
            metadata = sync.cache_metadata_path(day)
            metadata.write_text('{"date":"2026-10-09","fetched_at":"2026-10-08T18:00:00+00:00"}')
            self.assertFalse(sync.cache_is_fresh(day))
            metadata.write_text('{"date":"2026-10-09","fetched_at":"2026-10-09T18:00:00"}')
            self.assertFalse(sync.cache_is_fresh(day))

    def test_parse_github_push_remote(self):
        for raw in (
            "git@github.com:ZhenhaoLi00/ai-health-log-private.git",
            "ssh://git@github.com/ZhenhaoLi00/ai-health-log-private.git",
            "https://github.com/ZhenhaoLi00/ai-health-log-private.git",
        ):
            self.assertEqual(sync.parse_github_remote(raw), "ZhenhaoLi00/ai-health-log-private")
        for bad in ("https://evil.example.com/foo/bar", "/tmp/local.git",
                    "https://github.com/a/b/extra", "https://token@github.com/a/b.git"):
            with self.assertRaises(RuntimeError):
                sync.parse_github_remote(bad)

    def test_public_remote_rejected(self):
        with mock.patch.object(sync, "git", return_value=mock.Mock(
                stdout="git@github.com:ZhenhaoLi00/ai-health-log.git\n")), \
             mock.patch.object(sync, "github_api_token", return_value="test-token"), \
             mock.patch.object(sync, "urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{"private":false}'
            with self.assertRaisesRegex(RuntimeError, "Refusing to push"):
                sync.assert_private_push_remote()

    def test_private_remote_allowed(self):
        with mock.patch.object(sync, "git", return_value=mock.Mock(
                stdout="git@github.com:ZhenhaoLi00/ai-health-log-private.git\n")), \
             mock.patch.object(sync, "github_api_token", return_value="test-token"), \
             mock.patch.object(sync, "urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = b'{"private":true}'
            sync.assert_private_push_remote()

    def test_undetermined_visibility_fails_closed(self):
        with mock.patch.object(sync, "git", return_value=mock.Mock(
                stdout="git@github.com:ZhenhaoLi00/ai-health-log-private.git\n")), \
             mock.patch.object(sync, "github_api_token", return_value="test-token"), \
             mock.patch.object(sync, "urlopen", side_effect=OSError("offline")):
            with self.assertRaisesRegex(RuntimeError, "Cannot verify"):
                sync.assert_private_push_remote()

    def test_reject_conflicting_markers(self):
        day = dt.date(2026, 10, 9)
        path = sync.REPO / "data/daily/2026-10-09.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Test\n\n## Training\n" + sync.START_MARKER + "\n")
        with self.assertRaises(ValueError):
            sync.update_daily(day, None)


if __name__ == "__main__":
    unittest.main()
