# tests/test_sync.py
"""sync.py's file half: which of the seven the files prove complete.

The Asana half (ticking) is the model's and is not tested here. These tests
build a fake repo on disk, because the point of sync is reading real files
in the shapes the other scripts write them.
"""
from __future__ import annotations
import datetime as dt
import json, pathlib, shutil, subprocess, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import drip  # noqa: E402
import sync  # noqa: E402

CFG = {"blog_base_url": "https://me.example/blog",
       "utm_domains": "company.example,docs.company.example"}

PERSONAL = "https://me.example/blog/2026-09-01-thing"
CORPORATE = "https://www.company.example/learn/thing"
ELSEWHERE = "https://medium.com/@someone/thing"
VIDEO = "https://www.youtube.com/watch?v=abc123"


def fm(**pairs):
    return "---\n" + "".join("%s: %s\n" % (k, v) for k, v in pairs.items()) + "---\n"


class Repo:
    """A throwaway project repo with an advocacy/ directory."""

    def __init__(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root / "advocacy" / "content").mkdir(parents=True)
        (self.root / ".hub").mkdir()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def hub(self, public_repo=None):
        lines = ["title: Thing", "asana:", "  project: \"1\""]
        if public_repo:
            lines.append("public_repo: %s" % public_repo)
        self.write(".hub/hub.yml", "\n".join(lines) + "\n")

    def drip(self, name, piece, piece_type, written=6, live=0):
        dates = drip.drip_dates(dt.date(2026, 10, 6), set())
        links = {p: drip.link_line(piece, p, "thing", {}) for p in drip.PLATFORMS}
        text = drip.render_drip(
            {"project": "thing", "piece": piece, "piece_type": piece_type,
             "piece_title": "Thing", "created": "2026-10-01", "voice": "personal-style"},
            dict(zip(drip.ARCHETYPES, dates)), links, {})
        for n in range(1, written + 1):
            text = text.replace("```text\n```", "```text\nPost %d about the thing.\n```" % n, 1)
        for n in range(1, live + 1):
            text, _ = drip.mark_published(text, n, "https://x.com/me/status/%d" % n)
        return self.write("advocacy/content/drips/%s" % name, text)

    def evidence(self, day0=None):
        complete, unmatched = sync.evidence_from(self.root, CFG, day0)
        return {e.task: e.because for e in complete}, unmatched

    def close(self):
        shutil.rmtree(self.root)


class TestClassify(unittest.TestCase):
    def test_the_personal_blog_is_blog_base_urls_host(self):
        self.assertEqual(sync.classify_blog(PERSONAL, CFG), "Personal blog live")

    def test_a_company_domain_is_corporate_with_or_without_www(self):
        self.assertEqual(sync.classify_blog(CORPORATE, CFG), "Corporate blog live")
        self.assertEqual(sync.classify_blog("https://docs.company.example/x", CFG),
                         "Corporate blog live")

    def test_anywhere_else_is_not_guessed(self):
        self.assertIsNone(sync.classify_blog(ELSEWHERE, CFG))

    def test_no_config_means_nothing_can_be_placed(self):
        self.assertIsNone(sync.classify_blog(PERSONAL, {}))
        self.assertIsNone(sync.classify_blog(CORPORATE, {}))

    def test_host_of_tolerates_a_bare_domain(self):
        self.assertEqual(sync.host_of("company.example"), "company.example")
        self.assertEqual(sync.host_of("https://WWW.Company.Example/a"), "company.example")
        self.assertEqual(sync.host_of(""), "")


class TestEvidence(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_a_bare_repo_proves_nothing(self):
        done, unmatched = self.repo.evidence()
        self.assertEqual(done, {})
        self.assertEqual(unmatched, [])

    def test_public_repo_in_hub_yml_completes_the_first_task(self):
        self.repo.hub(public_repo="https://github.com/example/thing")
        done, _ = self.repo.evidence()
        self.assertEqual(list(done), ["Public repo"])
        self.assertIn("public_repo", done["Public repo"])

    def test_a_hub_without_public_repo_does_not(self):
        self.repo.hub()
        self.assertNotIn("Public repo", self.repo.evidence()[0])

    def test_blog_base_published_on_the_personal_blog(self):
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published=PERSONAL) + "Prose.\n")
        done, unmatched = self.repo.evidence()
        self.assertEqual(list(done), ["Personal blog live"])
        self.assertEqual(unmatched, [])

    def test_blog_base_published_on_the_company_blog(self):
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published=CORPORATE) + "Prose.\n")
        self.assertEqual(list(self.repo.evidence()[0]), ["Corporate blog live"])

    def test_blog_base_live_in_both_places_completes_both(self):
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published="%s %s" % (CORPORATE, PERSONAL)))
        self.assertEqual(list(self.repo.evidence()[0]),
                         ["Personal blog live", "Corporate blog live"])

    def test_an_unplaceable_blog_url_is_reported_not_ticked(self):
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published=ELSEWHERE))
        done, unmatched = self.repo.evidence()
        self.assertEqual(done, {})
        self.assertEqual(len(unmatched), 1)
        self.assertIn(ELSEWHERE, unmatched[0])

    def test_blog_base_with_an_empty_published_line_proves_nothing(self):
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published="") + "Prose.\n")
        self.assertEqual(self.repo.evidence()[0], {})

    def test_x_article_published(self):
        self.repo.write("advocacy/content/x-article.md",
                        fm(surface="x-article", published="https://x.com/me/article/1"))
        self.assertEqual(list(self.repo.evidence()[0]), ["X Article live"])

    def test_a_fully_written_drip_completes_the_drip_task(self):
        self.repo.drip("2026-10-01-thing.md", PERSONAL, "blog", written=6)
        done, _ = self.repo.evidence()
        self.assertIn("Drip written and scheduled", done)
        self.assertIn("all 6 posts", done["Drip written and scheduled"])

    def test_a_half_written_drip_does_not(self):
        self.repo.drip("2026-10-01-thing.md", PERSONAL, "blog", written=3)
        self.assertNotIn("Drip written and scheduled", self.repo.evidence()[0])

    def test_a_drip_about_a_blog_also_proves_that_blog_live(self):
        self.repo.drip("2026-10-01-thing.md", CORPORATE, "blog", written=0)
        done, _ = self.repo.evidence()
        self.assertIn("Corporate blog live", done)
        self.assertIn("drips a blog", done["Corporate blog live"])

    def test_a_drip_about_a_video_proves_the_video_live(self):
        self.repo.drip("2026-10-01-thing-video.md", VIDEO, "video", written=0)
        done, _ = self.repo.evidence()
        self.assertEqual(list(done), ["Video live"])
        self.assertIn(VIDEO, done["Video live"])

    def test_a_video_script_with_a_published_url_proves_the_video_live(self):
        self.repo.write("advocacy/content/video-script.md",
                        fm(surface="video-script", published=VIDEO))
        self.assertEqual(list(self.repo.evidence()[0]), ["Video live"])

    def test_a_published_log_line_proves_the_drip(self):
        self.repo.write("advocacy/content/published.log",
                        "2026-10-06 x https://x.com/me/status/1 "
                        "advocacy/content/drips/2026-10-01-thing.md#1\n")
        done, _ = self.repo.evidence()
        self.assertEqual(list(done), ["Drip written and scheduled"])
        self.assertIn("1 live post", done["Drip written and scheduled"])

    def test_an_empty_published_log_proves_nothing(self):
        self.repo.write("advocacy/content/published.log", "\n")
        self.assertEqual(self.repo.evidence()[0], {})

    def test_the_review_needs_the_ledger_entry_on_or_after_the_due_date(self):
        self.repo.write(".hub/ledger.md",
                        "# ledger\n\n## 2026-11-30\n\n### [review] 90 day review\nlines\n")
        done, unmatched = self.repo.evidence(day0=dt.date(2026, 9, 1))
        self.assertEqual(list(done), ["90 day review"])
        self.assertEqual(unmatched, [])

    def test_an_early_review_is_reported_not_ticked(self):
        self.repo.write(".hub/ledger.md",
                        "## 2026-10-15\n\n### [review] 90 day review\nlines\n")
        done, unmatched = self.repo.evidence(day0=dt.date(2026, 9, 1))
        self.assertEqual(done, {})
        self.assertEqual(len(unmatched), 1)
        self.assertIn("before the due date", unmatched[0])

    def test_a_review_without_day0_asks_for_it(self):
        self.repo.write(".hub/ledger.md",
                        "## 2026-11-30\n\n### [review] 90 day review\nlines\n")
        done, unmatched = self.repo.evidence()
        self.assertEqual(done, {})
        self.assertIn("--day0", unmatched[0])

    def test_a_ledger_without_a_review_says_nothing(self):
        self.repo.write(".hub/ledger.md", "## 2026-11-30\n\n### [decision] Something\n")
        self.assertEqual(self.repo.evidence(day0=dt.date(2026, 9, 1)), ({}, []))

    def test_evidence_comes_back_in_the_order_of_the_seven(self):
        self.repo.hub(public_repo="https://github.com/example/thing")
        self.repo.write("advocacy/content/x-article.md",
                        fm(surface="x-article", published="https://x.com/me/article/1"))
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published=PERSONAL))
        self.repo.drip("2026-10-01-thing-video.md", VIDEO, "video", written=6)
        done, _ = self.repo.evidence()
        self.assertEqual(list(done), ["Public repo", "Personal blog live", "X Article live",
                                      "Drip written and scheduled", "Video live"])

    def test_one_reason_per_task_however_many_files_agree(self):
        self.repo.drip("2026-10-01-a.md", PERSONAL, "blog", written=6)
        self.repo.drip("2026-10-02-b.md", PERSONAL, "blog", written=6)
        complete, _ = sync.evidence_from(self.repo.root, CFG)
        self.assertEqual([e.task for e in complete],
                         ["Personal blog live", "Drip written and scheduled"])


class TestFileStates(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_every_known_file_is_reported_even_when_missing(self):
        states = sync.file_states(self.repo.root)
        self.assertEqual(set(states), {
            "notes.md", "notes.companion.md", "content/blog-base.md",
            "content/archetype-takes.md", "content/social.md",
            "content/x-article.md", "content/video-script.md"})
        self.assertTrue(all(row["status"] == "missing" for row in states.values()))

    def test_states_follow_the_files(self):
        self.repo.write("advocacy/notes.md", "# Facts\n\n- 86 episodes (ledger 2026-08-05)\n")
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published="") +
                        "<!-- HOOK ........ 20 w\n-->\n")
        self.repo.write("advocacy/content/social.md", fm(surface="social", published=""))
        states = sync.file_states(self.repo.root)
        self.assertEqual(states["notes.md"]["status"], "written")
        self.assertEqual(states["content/blog-base.md"]["status"], "drafting")
        self.assertEqual(states["content/blog-base.md"]["open_beats"], ["HOOK"])
        self.assertEqual(states["content/social.md"]["status"], "empty")

    def test_drip_states_count_written_and_live(self):
        self.repo.drip("2026-10-01-thing.md", PERSONAL, "blog", written=4, live=2)
        states = sync.drip_states(self.repo.root)
        row = states["2026-10-01-thing.md"]
        self.assertEqual((row["written"], row["unwritten"], row["live"]), (4, 2, 2))
        self.assertEqual(row["piece"], PERSONAL)
        self.assertEqual(row["piece_type"], "blog")


class TestCli(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.cfg = self.repo.root / "cfg.yml"
        self.cfg.write_text('blog_base_url: "https://me.example/blog"\n'
                            'utm_domains: "company.example"\n')

    def tearDown(self):
        self.repo.close()

    def run_sync(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "sync.py"), "--repo", str(self.repo.root),
             "--config", str(self.cfg), *extra],
            capture_output=True, text=True)

    def test_prints_the_seven_and_what_the_files_prove(self):
        self.repo.hub(public_repo="https://github.com/example/thing")
        self.repo.write("advocacy/content/blog-base.md",
                        fm(surface="blog-base", published=CORPORATE))
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tasks"][-1], "90 day review")
        self.assertEqual([e["task"] for e in data["complete"]],
                         ["Public repo", "Corporate blog live"])
        self.assertEqual(data["unmatched"], [])
        self.assertIn("content/blog-base.md", data["files"])
        self.assertEqual(data["drips"], {})

    def test_day0_is_passed_through_to_the_review(self):
        self.repo.write(".hub/ledger.md", "## 2026-12-01\n\n### [review] 90 day review\n")
        data = json.loads(self.run_sync("--day0", "2026-09-01").stdout)
        self.assertEqual([e["task"] for e in data["complete"]], ["90 day review"])

    def test_a_repo_without_advocacy_is_refused(self):
        shutil.rmtree(self.repo.root / "advocacy")
        result = self.run_sync()
        self.assertEqual(result.returncode, 2)
        self.assertIn("run intake first", result.stderr)

    def test_never_writes_anything(self):
        self.repo.hub(public_repo="https://github.com/example/thing")
        before = sorted(str(p.relative_to(self.repo.root))
                        for p in self.repo.root.rglob("*") if p.is_file())
        self.run_sync()
        after = sorted(str(p.relative_to(self.repo.root))
                       for p in self.repo.root.rglob("*") if p.is_file())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
