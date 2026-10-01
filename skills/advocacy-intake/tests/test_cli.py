# tests/test_cli.py
"""Tests for the intake_core.py command line.

These invoke the script as a subprocess rather than importing it, because the
CLI is a thin wrapper and the point is to prove the wrapper (argument
parsing, JSON printing, exit codes) works end to end, not to re-test the pure
functions it calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "intake_core.py"
REPO = HERE / "fixtures" / "dog_whisper"

sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import DECISION_TASK, TITLES


def run(*argv):
    return subprocess.run([sys.executable, str(SCRIPT), *argv],
                          capture_output=True, text=True)


class TestCli(unittest.TestCase):
    def test_signals_prints_json_with_two_ledger_entries(self):
        result = run("--signals", str(REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["ledger_entries"], 2)
        self.assertIsNone(data["public_repo"])

    def test_tasks_is_the_seven_in_order(self):
        result = run("--tasks", str(REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([row["title"] for row in data], list(TITLES))
        for row in data:
            self.assertIsNone(row["due_on"])

    def test_day0_dates_the_review_and_nothing_else(self):
        result = run("--tasks", str(REPO), "--day0", "2026-09-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        dated = {row["title"]: row["due_on"] for row in data if row["due_on"]}
        self.assertEqual(dated, {"90 day review": "2026-11-30"})

    def test_missing_repo_exits_non_zero(self):
        result = run("--signals", str(HERE / "fixtures" / "does_not_exist"))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")

    def test_a_bad_day0_exits_non_zero(self):
        result = run("--tasks", str(REPO), "--day0", "yesterday")
        self.assertNotEqual(result.returncode, 0)

    def _reconcile(self, existing_titles, *extra):
        with tempfile.TemporaryDirectory() as tmp:
            titles_file = pathlib.Path(tmp) / "existing-titles.txt"
            titles_file.write_text("\n".join(existing_titles))
            result = run("--reconcile", str(REPO),
                         "--existing-titles-file", str(titles_file), *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_reconcile_fresh_project_creates_all_seven(self):
        data = self._reconcile([])
        self.assertEqual([t["title"] for t in data["create"]], list(TITLES))
        self.assertEqual(data["keep"], [])
        self.assertEqual(data["untouched"], [])
        self.assertIsNone(data["decision_task"])

    def test_reconcile_full_rerun_creates_nothing(self):
        first = self._reconcile([])
        second = self._reconcile([t["title"] for t in first["create"]])
        self.assertEqual(second["create"], [])
        self.assertEqual(len(second["keep"]), 7)

    def test_reconcile_reports_hub_inits_decision_task_when_present(self):
        data = self._reconcile([DECISION_TASK, "Capture the first time it works"])
        self.assertEqual(data["decision_task"], DECISION_TASK)
        self.assertEqual(data["untouched"],
                         [DECISION_TASK, "Capture the first time it works"])

    def test_reconcile_with_day0_dates_the_project_and_the_review(self):
        data = self._reconcile([], "--day0", "2026-09-01")
        self.assertEqual(data["project"],
                         {"start_on": "2026-09-01", "due_on": "2026-11-30"})
        review = [t for t in data["create"] if t["title"] == "90 day review"][0]
        self.assertEqual(review["due_on"], "2026-11-30")

    def test_reconcile_requires_the_titles_file(self):
        result = run("--reconcile", str(REPO))
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
