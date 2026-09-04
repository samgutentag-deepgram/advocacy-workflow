from __future__ import annotations
import shutil, subprocess, sys, tempfile, unittest, pathlib

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
from intake_core import read_signals


class TestSignals(unittest.TestCase):
    def test_dog_whisper_has_a_ledger_and_no_deploy(self):
        s = read_signals(HERE / "fixtures" / "dog_whisper")
        self.assertEqual(s.ledger_entries, 2)
        self.assertFalse(s.has_deploy)
        self.assertEqual(s.capture_plan, ".hub/capture-plan.md")
        self.assertFalse(s.has_license)

    def test_webapp_has_a_deploy_and_no_ledger(self):
        s = read_signals(HERE / "fixtures" / "webapp")
        self.assertEqual(s.ledger_entries, 0)
        self.assertTrue(s.has_deploy)
        self.assertIsNone(s.capture_plan)
        self.assertTrue(s.has_license)

    def test_missing_repo_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_signals(HERE / "fixtures" / "does_not_exist")

    def test_gate_doc_is_found_when_present(self):
        s = read_signals(HERE / "fixtures" / "gated")
        self.assertEqual(s.gate_doc, "docs/legal.md")
        self.assertTrue(s.has_license)

    def test_gate_doc_is_none_when_absent(self):
        for name in ("dog_whisper", "webapp"):
            self.assertIsNone(read_signals(HERE / "fixtures" / name).gate_doc)

    def test_git_init_with_nothing_committed_has_no_content(self):
        # git cannot track an empty directory, so a committed fixture cannot
        # represent "git init, zero files." Build the case with a real
        # empty temp dir instead.
        tmp = tempfile.mkdtemp()
        try:
            (pathlib.Path(tmp) / ".git").mkdir()
            s = read_signals(tmp)
            self.assertFalse(s.has_content)
        finally:
            shutil.rmtree(tmp)

    def test_real_fixtures_all_report_content(self):
        for name in ("dog_whisper", "webapp", "gated"):
            s = read_signals(HERE / "fixtures" / name)
            self.assertTrue(s.has_content, "%s should have content" % name)

    def test_tasks_cli_refuses_an_empty_repo(self):
        tmp = tempfile.mkdtemp()
        try:
            (pathlib.Path(tmp) / ".git").mkdir()
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "intake_core.py"),
                 "--tasks", tmp, "--surfaces", "personal_blog"],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        finally:
            shutil.rmtree(tmp)

    def test_reconcile_cli_also_refuses_an_empty_repo(self):
        # Mirrors test_tasks_cli_refuses_an_empty_repo: --reconcile reaches
        # build_tasks by the same route --tasks does, and must refuse the
        # same way rather than printing a full create/keep/untouched graph
        # for a repo with nothing in it. The titles file lives in a
        # separate temp dir so writing it does not itself give the repo
        # content and quietly defeat the test.
        repo_tmp = tempfile.mkdtemp()
        other_tmp = tempfile.mkdtemp()
        try:
            (pathlib.Path(repo_tmp) / ".git").mkdir()
            titles_file = pathlib.Path(other_tmp) / "existing-titles.txt"
            titles_file.write_text("")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "intake_core.py"),
                 "--reconcile", repo_tmp, "--surfaces", "personal_blog",
                 "--existing-titles-file", str(titles_file)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        finally:
            shutil.rmtree(repo_tmp)
            shutil.rmtree(other_tmp)


if __name__ == "__main__":
    unittest.main()
