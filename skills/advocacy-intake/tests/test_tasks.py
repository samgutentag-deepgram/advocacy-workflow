# tests/test_tasks.py
from __future__ import annotations
import datetime as dt
import sys, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import (
    DECISION_TASK, REVIEW_DAY, REVIEW_TITLE, SEVEN_TASKS, TITLES, Signals,
    build_tasks, campaign_dates, due_on, read_signals, task_by_title,
)

DAY0 = dt.date(2026, 9, 1)


class TestTheSeven(unittest.TestCase):
    def test_the_seven_titles_in_order(self):
        """Same titles, same order, every campaign. These strings are the
        reconcile key and the join sync uses, so they are asserted verbatim."""
        self.assertEqual(list(TITLES), [
            "Public repo",
            "Personal blog live",
            "Corporate blog live",
            "X Article live",
            "Drip written and scheduled",
            "Video live",
            "90 day review",
        ])

    def test_exactly_seven(self):
        self.assertEqual(len(SEVEN_TASKS), 7)

    def test_titles_are_unique(self):
        self.assertEqual(len(set(TITLES)), 7)

    def test_only_the_review_carries_a_due_day(self):
        dated = [t.title for t in SEVEN_TASKS if t.due_day is not None]
        self.assertEqual(dated, [REVIEW_TITLE])
        self.assertEqual(task_by_title(REVIEW_TITLE).due_day, REVIEW_DAY)
        self.assertEqual(REVIEW_DAY, 90)

    def test_every_task_says_when_to_tick_it(self):
        for task in SEVEN_TASKS:
            self.assertIn("Complete when", task.note, task.title)

    def test_the_review_note_carries_its_five_steps(self):
        note = task_by_title(REVIEW_TITLE).note
        for step in ("(1)", "(2)", "(3)", "(4)", "(5)"):
            self.assertIn(step, note)
        self.assertIn("Profound", note)
        self.assertIn(".hub/ledger.md", note)
        self.assertIn("published.log", note)

    def test_no_task_is_a_subtask_or_in_a_section(self):
        """Flat on purpose. The old board had sections and subtasks and
        nobody opened it."""
        for task in SEVEN_TASKS:
            self.assertEqual(set(task._fields), {"title", "note", "due_day"})

    def test_unknown_title_raises(self):
        with self.assertRaises(KeyError):
            task_by_title("Approve the blog")

    def test_no_em_dashes(self):
        for task in SEVEN_TASKS:
            self.assertNotIn("\u2014", task.title)
            self.assertNotIn("\u2014", task.note)

    def test_the_decision_task_is_hub_inits_title(self):
        self.assertEqual(DECISION_TASK, "Decide: promote or drop")
        self.assertNotIn(DECISION_TASK, TITLES)


class TestBuildTasks(unittest.TestCase):
    def test_every_repo_with_content_gets_the_same_seven(self):
        for name in ("dog_whisper", "webapp", "gated", "gated_private"):
            tasks = build_tasks(read_signals(HERE / "fixtures" / name))
            self.assertEqual([t.title for t in tasks], list(TITLES), name)

    def test_an_empty_repo_is_refused(self):
        empty = Signals(0, False, None, None, False, False, None)
        with self.assertRaises(ValueError):
            build_tasks(empty)


class TestDates(unittest.TestCase):
    def test_the_review_is_due_day_0_plus_90(self):
        self.assertEqual(due_on(task_by_title(REVIEW_TITLE), DAY0),
                         dt.date(2026, 11, 30))

    def test_the_other_six_have_no_due_date(self):
        for task in SEVEN_TASKS:
            if task.title != REVIEW_TITLE:
                self.assertIsNone(due_on(task, DAY0), task.title)

    def test_the_project_runs_day_0_to_day_90(self):
        start, due = campaign_dates(DAY0)
        self.assertEqual(start, DAY0)
        self.assertEqual(due, dt.date(2026, 11, 30))
        self.assertEqual(due, due_on(task_by_title(REVIEW_TITLE), DAY0))


if __name__ == "__main__":
    unittest.main()
