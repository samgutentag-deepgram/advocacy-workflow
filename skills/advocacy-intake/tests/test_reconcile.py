from __future__ import annotations
import sys, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from intake_core import Task, reconcile

DESIRED = [
    Task("gate", "Decide public, and add a LICENSE", "why", ()),
    Task("verify", "Verify every number you will quote", "why", ()),
    Task("surface:personal_blog", "Personal blog", "why", ("gate", "verify")),
]


class TestReconcile(unittest.TestCase):
    def test_empty_project_creates_everything(self):
        plan = reconcile(DESIRED, [])
        self.assertEqual(len(plan.create), 3)
        self.assertEqual(plan.keep, [])

    def test_rerun_creates_nothing(self):
        plan = reconcile(DESIRED, [t.title for t in DESIRED])
        self.assertEqual(plan.create, [])
        self.assertEqual(len(plan.keep), 3)

    def test_partial_run_creates_only_the_missing(self):
        plan = reconcile(DESIRED, ["Decide public, and add a LICENSE"])
        self.assertEqual([t.key for t in plan.create],
                         ["verify", "surface:personal_blog"])

    def test_hand_added_tasks_are_left_alone(self):
        """People type things into Asana as they occur to them. Those are not
        second-class and nothing here may propose removing them."""
        plan = reconcile(DESIRED, ["Cut the failure reel as its own clip"])
        self.assertEqual(plan.untouched, ["Cut the failure reel as its own clip"])
        self.assertEqual(len(plan.create), 3)

    def test_nothing_is_ever_marked_for_deletion(self):
        plan = reconcile(DESIRED, ["Some task nobody recognizes"])
        self.assertFalse(hasattr(plan, "delete"))


if __name__ == "__main__":
    unittest.main()


class TestDependencyResolution(unittest.TestCase):
    """A created task depends on KEYS. Asana is addressed by TITLE. Without a
    map between them the caller silently drops the wire, and an unwired
    dependency looks exactly like a task that is ready."""

    def test_title_by_key_covers_every_desired_task(self):
        plan = reconcile(DESIRED, [])
        self.assertEqual(
            plan.title_by_key,
            {t.key: t.title for t in DESIRED},
        )

    def test_every_dependency_of_a_created_task_resolves_to_a_title(self):
        plan = reconcile(DESIRED, ["Decide public, and add a LICENSE"])
        self.assertTrue(plan.create, "fixture must leave something to create")
        for task in plan.create:
            for dep_key in task.depends_on:
                self.assertIn(
                    dep_key, plan.title_by_key,
                    "dependency %r on %r resolves to no title" % (dep_key, task.key),
                )

    def test_the_map_survives_a_full_rerun(self):
        plan = reconcile(DESIRED, [t.title for t in DESIRED])
        self.assertEqual(plan.create, [])
        self.assertEqual(len(plan.title_by_key), len(DESIRED))
