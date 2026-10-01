from __future__ import annotations
import sys, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import DECISION_TASK, SEVEN_TASKS, TITLES, reconcile

HUB_INIT = ["Capture the first time it works", DECISION_TASK]


class TestReconcile(unittest.TestCase):
    def test_empty_project_creates_all_seven(self):
        plan = reconcile(SEVEN_TASKS, [])
        self.assertEqual([t.title for t in plan.create], list(TITLES))
        self.assertEqual(plan.keep, [])

    def test_rerun_creates_nothing(self):
        plan = reconcile(SEVEN_TASKS, list(TITLES))
        self.assertEqual(plan.create, [])
        self.assertEqual(plan.keep, list(TITLES))

    def test_partial_run_creates_only_the_missing_in_order(self):
        plan = reconcile(SEVEN_TASKS, ["Public repo", "X Article live"])
        self.assertEqual([t.title for t in plan.create], [
            "Personal blog live", "Corporate blog live",
            "Drip written and scheduled", "Video live", "90 day review",
        ])
        self.assertEqual(plan.keep, ["Public repo", "X Article live"])

    def test_matching_is_on_the_exact_title(self):
        """Renaming a task in Asana does not stick: the original title is
        recreated on the next run and the renamed one is left alone."""
        plan = reconcile(SEVEN_TASKS, ["public repo", "Personal blog is live"])
        self.assertIn("Public repo", [t.title for t in plan.create])
        self.assertIn("Personal blog live", [t.title for t in plan.create])
        self.assertEqual(plan.untouched, ["public repo", "Personal blog is live"])

    def test_hub_inits_tasks_and_hand_added_tasks_are_left_alone(self):
        """People type things into Asana as they occur to them. Those are not
        second-class and nothing here may propose removing them."""
        plan = reconcile(SEVEN_TASKS, HUB_INIT + ["Cut the failure reel"])
        self.assertEqual(plan.untouched, HUB_INIT + ["Cut the failure reel"])
        self.assertEqual(len(plan.create), 7)

    def test_nothing_is_ever_marked_for_deletion(self):
        plan = reconcile(SEVEN_TASKS, ["Some task nobody recognizes"])
        self.assertFalse(hasattr(plan, "delete"))


if __name__ == "__main__":
    unittest.main()
