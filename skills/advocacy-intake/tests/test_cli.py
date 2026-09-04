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
import unittest
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "intake_core.py"

sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import build_tasks, derive_spine, read_signals


class TestCli(unittest.TestCase):
    def test_signals_prints_json_with_two_ledger_entries(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--signals",
             str(HERE / "fixtures" / "dog_whisper")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["ledger_entries"], 2)

    def test_tasks_length_matches_the_whole_graph(self):
        """A kept derivative is a canonical, a variant parent and four
        variants, not one task. The CLI emits the whole graph, both filers'
        share of it."""
        repo = HERE / "fixtures" / "dog_whisper"
        kept = "personal_blog,personal_video_script"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--tasks", str(repo),
             "--surfaces", kept],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        expected = build_tasks(read_signals(repo), kept.split(","))
        self.assertEqual(len(data), len(expected))

    def test_tasks_carry_the_gate_and_parent_the_caller_needs(self):
        """gate picks the Asana section. parent decides whether this is a
        task or a subtask under one."""
        repo = HERE / "fixtures" / "dog_whisper"
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--tasks", str(repo),
             "--surfaces", "personal_blog,personal_thread"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        gates = {row["gate"] for row in data}
        self.assertEqual(gates, {None, "A", "B", "C"})
        subtasks = [row for row in data if row["parent"]]
        self.assertEqual(len(subtasks), 4)
        by_key = {row["key"]: row for row in data}
        for row in subtasks:
            self.assertIn(row["parent"], by_key)
            self.assertIsNone(by_key[row["parent"]]["parent"])

    def test_tasks_carry_the_offset_the_caller_needs_to_date_them(self):
        """The core has no clock. It hands out drop_day and offset and the
        caller, which knows day 0, does the arithmetic."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--tasks",
             str(HERE / "fixtures" / "dog_whisper"),
             "--surfaces", "personal_blog"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        steps = [row for row in data if row["key"].startswith("gate:")]
        prep = [row for row in data if not row["key"].startswith("gate:")]
        self.assertTrue(steps)
        for row in steps:
            self.assertEqual(row["drop_day"], 1)
            self.assertEqual(row["offset"], 0)
        for row in prep:
            self.assertIsNone(row["drop_day"])
            self.assertIsNone(row["offset"])

    def test_missing_repo_exits_non_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--signals",
             str(HERE / "fixtures" / "does_not_exist")],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")

    def test_unknown_surface_exits_non_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--tasks",
             str(HERE / "fixtures" / "dog_whisper"),
             "--surfaces", "not_a_real_surface"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")

    def _reconcile(self, repo, surfaces, existing_titles, tmp_path, filer=None):
        titles_file = tmp_path / "existing-titles.txt"
        titles_file.write_text("\n".join(existing_titles))
        argv = [sys.executable, str(SCRIPT), "--reconcile", str(repo),
                "--surfaces", surfaces,
                "--existing-titles-file", str(titles_file)]
        if filer:
            argv += ["--filer", filer]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_reconcile_fresh_project_creates_everything(self):
        import tempfile
        repo = HERE / "fixtures" / "dog_whisper"
        with tempfile.TemporaryDirectory() as tmp:
            data = self._reconcile(repo, "personal_blog", [], pathlib.Path(tmp))
        expected = len(build_tasks(read_signals(repo), ["personal_blog"]))
        self.assertEqual(len(data["create"]), expected)
        self.assertEqual(data["keep"], [])
        self.assertEqual(data["untouched"], [])

    def test_reconcile_full_rerun_creates_nothing(self):
        import tempfile
        repo = HERE / "fixtures" / "dog_whisper"
        with tempfile.TemporaryDirectory() as tmp:
            first = self._reconcile(repo, "personal_blog", [], pathlib.Path(tmp))
            titles = [t["title"] for t in first["create"]]
            second = self._reconcile(repo, "personal_blog", titles, pathlib.Path(tmp))
        self.assertEqual(second["create"], [])
        self.assertEqual(len(second["keep"]), len(titles))

    def test_reconcile_hand_added_title_appears_in_untouched(self):
        import tempfile
        repo = HERE / "fixtures" / "dog_whisper"
        with tempfile.TemporaryDirectory() as tmp:
            data = self._reconcile(
                repo, "personal_blog",
                ["Cut the failure reel as its own clip"],
                pathlib.Path(tmp),
            )
        self.assertEqual(
            data["untouched"], ["Cut the failure reel as its own clip"]
        )

    def test_filer_splits_the_board_and_still_resolves_across_it(self):
        """intake creates gates A and B. cycle creates C and D. Both see the
        whole title_by_key, because a Gate C task depends on a Gate B task
        the other skill filed."""
        import tempfile
        repo = HERE / "fixtures" / "dog_whisper"
        kept = "personal_blog,personal_video_script"
        with tempfile.TemporaryDirectory() as tmp:
            intake = self._reconcile(repo, kept, [], pathlib.Path(tmp), "intake")
            cycle = self._reconcile(repo, kept, [], pathlib.Path(tmp), "cycle")
            whole = self._reconcile(repo, kept, [], pathlib.Path(tmp))

        intake_gates = {t["gate"] for t in intake["create"]}
        cycle_gates = {t["gate"] for t in cycle["create"]}
        self.assertEqual(intake_gates, {None, "A", "B"})
        self.assertEqual(cycle_gates, {"C", "D"})

        self.assertEqual(len(intake["create"]) + len(cycle["create"]),
                         len(whole["create"]))
        for plan in (intake, cycle):
            self.assertEqual(plan["title_by_key"], whole["title_by_key"])


if __name__ == "__main__":
    unittest.main()
