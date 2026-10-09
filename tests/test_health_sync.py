"""Run with: python3 -m unittest discover -s tests -v"""
import datetime as dt
import importlib.util
import json
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

    def test_reject_conflicting_markers(self):
        day = dt.date(2026, 10, 9)
        path = sync.REPO / "data/daily/2026-10-09.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Test\n\n## Training\n" + sync.START_MARKER + "\n")
        with self.assertRaises(ValueError):
            sync.update_daily(day, None)


if __name__ == "__main__":
    unittest.main()
