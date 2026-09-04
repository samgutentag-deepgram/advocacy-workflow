from __future__ import annotations
import sys, unittest, pathlib, tempfile, shutil, subprocess

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "write_advocacy.py"
sys.path.insert(0, str(HERE.parent / "scripts"))
from write_advocacy import render_advocacy_md, write_advocacy


class TestRender(unittest.TestCase):
    def render(self):
        return render_advocacy_md(
            project="dog-whisper",
            claim="A bark can be detected without a wake word.",
            reader="Anyone with a Pi and a noisy dog.",
            surfaces=["personal_blog", "personal_video_script"],
            asana_url="https://app.asana.com/0/123",
        )

    def test_carries_the_pre_public_warning(self):
        self.assertIn("before this repo goes public", self.render())

    def test_names_the_kept_surfaces(self):
        text = self.render()
        self.assertIn("personal_blog", text)
        self.assertIn("personal_video_script", text)

    def test_links_asana(self):
        self.assertIn("https://app.asana.com/0/123", self.render())

    def test_no_em_dashes(self):
        self.assertNotIn("—", self.render())


class TestWrite(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_creates_the_directory_and_the_file(self):
        p = write_advocacy(self.tmp, "hello")
        self.assertTrue(p.is_file())
        self.assertEqual(p.relative_to(self.tmp).as_posix(), "advocacy/advocacy.md")

    def test_refuses_to_clobber_an_existing_file(self):
        write_advocacy(self.tmp, "first")
        with self.assertRaises(FileExistsError):
            write_advocacy(self.tmp, "second")
        self.assertEqual((self.tmp / "advocacy" / "advocacy.md").read_text(), "first")


class TestCli(unittest.TestCase):
    """These invoke the script as a subprocess: the point is to prove the
    CLI (argument parsing, exit codes, stdout/stderr) behaves correctly end
    to end, not to re-test render_advocacy_md/write_advocacy again."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, **flags):
        args = [sys.executable, str(SCRIPT)]
        for key, value in flags.items():
            args.append("--%s" % key.replace("_", "-"))
            args.append(value)
        return subprocess.run(args, capture_output=True, text=True)

    def test_a_successful_run_creates_the_file_and_prints_its_path(self):
        result = self._run(
            repo=str(self.tmp), project="dog-whisper",
            claim="A bark can be detected without a wake word.",
            reader="Anyone with a Pi.",
            surfaces="personal_blog,personal_video_script",
            asana_url="https://app.asana.com/0/123",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.tmp / "advocacy" / "advocacy.md"
        self.assertTrue(target.is_file())
        self.assertEqual(result.stdout.strip(), str(target.resolve()))

    def test_a_second_run_fails_loudly_and_leaves_the_file_unchanged(self):
        self._run(
            repo=str(self.tmp), project="dog-whisper", claim="first claim",
            reader="first reader", surfaces="personal_blog",
            asana_url="https://x",
        )
        before = (self.tmp / "advocacy" / "advocacy.md").read_text()
        result = self._run(
            repo=str(self.tmp), project="dog-whisper", claim="second claim",
            reader="second reader", surfaces="personal_blog",
            asana_url="https://y",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")
        after = (self.tmp / "advocacy" / "advocacy.md").read_text()
        self.assertEqual(before, after)

    def test_a_missing_required_flag_exits_non_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.tmp)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_create_without_asana_url_does_not_claim_a_url_exists(self):
        result = self._run(
            repo=str(self.tmp), project="dog-whisper",
            claim="A bark can be detected without a wake word.",
            reader="Anyone with a Pi.",
            surfaces="personal_blog",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.tmp / "advocacy" / "advocacy.md").read_text()
        self.assertNotIn("https://", text)
        self.assertIn("Pending", text)

    def test_set_asana_url_updates_tracking_and_leaves_the_claim_byte_identical(self):
        self._run(
            repo=str(self.tmp), project="dog-whisper",
            claim="A bark can be detected without a wake word.",
            reader="Anyone with a Pi.",
            surfaces="personal_blog",
        )
        target = self.tmp / "advocacy" / "advocacy.md"
        claim_before = target.read_text().split("## The reader")[0]

        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.tmp),
             "--set-asana-url", "https://app.asana.com/0/999"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(target.resolve()))

        text_after = target.read_text()
        claim_after = text_after.split("## The reader")[0]
        self.assertEqual(claim_before, claim_after)
        self.assertIn("https://app.asana.com/0/999", text_after)
        self.assertNotIn("Pending", text_after)

    def test_unknown_surface_key_exits_non_zero_and_creates_no_file(self):
        result = self._run(
            repo=str(self.tmp), project="dog-whisper",
            claim="A bark can be detected without a wake word.",
            reader="Anyone with a Pi.",
            surfaces="personal_blog,not_a_real_surface",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")
        self.assertFalse((self.tmp / "advocacy").exists())

    def test_set_asana_url_against_a_missing_file_exits_non_zero_and_creates_nothing(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.tmp),
             "--set-asana-url", "https://app.asana.com/0/999"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stderr.strip(), "")
        self.assertFalse((self.tmp / "advocacy").exists())


if __name__ == "__main__":
    unittest.main()
