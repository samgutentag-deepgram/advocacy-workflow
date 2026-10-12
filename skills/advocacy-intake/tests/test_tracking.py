"""Where a campaign is tracked, read from advocacy.md's tracking line.

A campaign is one parent task on a shared board. A file still pointing at an
old per-repo project has to say so loudly, never sync into the wrong place.
"""
from __future__ import annotations
import json, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from intake_core import (  # noqa: E402
    find_parent, migration_message, read_tracking, tracking_from_url,
)
from write_advocacy import render_advocacy_md  # noqa: E402

TASK = "https://app.asana.com/1/411/project/1213689635611715/task/1219426228267446"
BARE_TASK = "https://app.asana.com/1/411/task/1219426228267446"
OLD_TASK = "https://app.asana.com/0/1213689635611715/1219426228267446"
PROJECT = "https://app.asana.com/1/411/project/1219052330259865"
OLD_PROJECT = "https://app.asana.com/0/1219052330259865/list"


class TestClassify(unittest.TestCase):
    def test_every_task_url_shape_names_the_task(self):
        for url in (TASK, BARE_TASK, OLD_TASK, OLD_TASK + "/f"):
            t = tracking_from_url(url)
            self.assertEqual((t.kind, t.gid), ("task", "1219426228267446"), url)

    def test_a_project_url_is_the_old_model(self):
        for url in (PROJECT, OLD_PROJECT, "https://app.asana.com/0/1219052330259865"):
            t = tracking_from_url(url)
            self.assertEqual((t.kind, t.gid), ("project", "1219052330259865"), url)

    def test_the_pending_line_is_missing(self):
        pending = render_advocacy_md("p", "claim", "reader")
        path = pathlib.Path(tempfile.mkdtemp())
        try:
            (path / "advocacy").mkdir()
            (path / "advocacy" / "advocacy.md").write_text(pending)
            self.assertEqual(read_tracking(path).kind, "missing")
        finally:
            shutil.rmtree(path)

    def test_no_advocacy_md_is_missing(self):
        path = pathlib.Path(tempfile.mkdtemp())
        try:
            self.assertEqual(read_tracking(path).kind, "missing")
        finally:
            shutil.rmtree(path)


class TestMigration(unittest.TestCase):
    def test_a_parent_task_needs_nothing(self):
        self.assertIsNone(migration_message(tracking_from_url(TASK)))

    def test_an_old_project_is_told_how_to_migrate(self):
        msg = migration_message(tracking_from_url(PROJECT))
        self.assertIn(PROJECT, msg)
        self.assertIn("--set-asana-url", msg)
        self.assertIn("parent task", msg)

    def test_no_url_is_told_to_run_intake(self):
        self.assertIn("intake", migration_message(tracking_from_url(None)))

    def test_no_em_dashes(self):
        for url in (PROJECT, None):
            self.assertNotIn("—", migration_message(tracking_from_url(url)))


class TestFindParent(unittest.TestCase):
    def test_the_bare_slug_or_slug_colon_is_the_parent(self):
        self.assertEqual(find_parent("jev", ["x", "jev"]), "jev")
        self.assertEqual(find_parent("jev", ["jev: Flux eager end-of-turn demo"]),
                         "jev: Flux eager end-of-turn demo")

    def test_a_title_that_only_starts_with_the_slug_is_someone_elses(self):
        self.assertIsNone(find_parent("jev", ["jevons paradox notes", "Jev"]))


class TestCli(unittest.TestCase):
    def test_tracking_prints_kind_gid_and_migrate(self):
        path = pathlib.Path(tempfile.mkdtemp())
        try:
            (path / "advocacy").mkdir()
            (path / "advocacy" / "advocacy.md").write_text(
                render_advocacy_md("p", "claim", "reader", PROJECT))
            out = subprocess.run(
                [sys.executable, str(SCRIPTS / "intake_core.py"), "--tracking", str(path)],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            data = json.loads(out.stdout)
            self.assertEqual(data["kind"], "project")
            self.assertIn("Migrate", data["migrate"])
        finally:
            shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
