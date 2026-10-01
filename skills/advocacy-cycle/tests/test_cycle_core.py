# tests/test_cycle_core.py
from __future__ import annotations
import datetime as dt
import sys, unittest, pathlib, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from cycle_core import (
    CONTENT_FILES, TITLES, X_URL_BILLED_CHARS, billed_length, body_of,
    check_beats, check_citation, content_file, content_path, find_citations,
    open_beats, parse_frontmatter, piece_status, post_body, published_urls,
    review_date, scaffold, set_published, split_posts,
)


class TestLayout(unittest.TestCase):
    def test_three_files_flat_under_content(self):
        """blog-base, the archetype takes, social. No branches, no
        per-surface directories, nothing one level down."""
        self.assertEqual([f.key for f in CONTENT_FILES], ["blog-base", "takes", "social"])
        self.assertEqual(str(content_path("blog-base")), "content/blog-base.md")
        self.assertEqual(str(content_path("takes")), "content/archetype-takes.md")
        self.assertEqual(str(content_path("social")), "content/social.md")
        for f in CONTENT_FILES:
            self.assertEqual(len(f.path.parts), 2, f.path)

    def test_the_surface_is_the_filename_stem(self):
        for f in CONTENT_FILES:
            self.assertEqual(f.path.stem, f.surface)

    def test_an_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            content_path("blog")

    def test_every_file_says_what_it_is_for(self):
        for f in CONTENT_FILES:
            self.assertTrue(f.job.strip(), f.key)

    def test_the_seven_titles_are_the_ones_intake_owns(self):
        """Imported, not redefined. One definition for the skill that
        creates the tasks and the skill that ticks them."""
        self.assertEqual(TITLES[0], "Public repo")
        self.assertEqual(TITLES[-1], "90 day review")
        self.assertEqual(len(TITLES), 7)


class TestScaffold(unittest.TestCase):
    def test_frontmatter_only(self):
        text = scaffold("social", "demo", "2026-10-01", "sam-style")
        fm = parse_frontmatter(text)
        self.assertEqual(fm["project"], "demo")
        self.assertEqual(fm["surface"], "social")
        self.assertEqual(fm["created"], "2026-10-01")
        self.assertEqual(fm["passes"], "[sam-style, de-slop]")
        self.assertEqual(fm["published"], [])
        self.assertEqual(body_of(text), "")
        self.assertEqual(piece_status(text), "empty")

    def test_takes_carries_its_surface_name(self):
        self.assertEqual(parse_frontmatter(scaffold("takes", "p", "2026-10-01"))["surface"],
                         "archetype-takes")

    def test_no_em_dashes(self):
        for f in CONTENT_FILES:
            self.assertNotIn("\u2014", scaffold(f.key, "p", "2026-10-01"))
            self.assertNotIn("\u2014", content_file(f.key).job)


class TestFrontmatter(unittest.TestCase):
    DOC = ("---\n"
           "surface: blog-base\n"
           "published:\n"
           "links:\n"
           "  - https://a.example/one\n"
           "  - https://a.example/two\n"
           "---\n"
           "\n# Title\n\nBody.\n")

    def test_scalars_and_lists(self):
        data = parse_frontmatter(self.DOC)
        self.assertEqual(data["surface"], "blog-base")
        self.assertEqual(data["published"], [])
        self.assertEqual(len(data["links"]), 2)

    def test_no_frontmatter_is_not_an_error(self):
        self.assertEqual(parse_frontmatter("# Just a heading\n"), {})

    def test_an_empty_frontmatter_block_still_matches(self):
        self.assertEqual(body_of("---\n---\nprose\n"), "prose")


class TestPublished(unittest.TestCase):
    def test_an_empty_published_line_is_no_urls(self):
        self.assertEqual(published_urls("---\npublished:\n---\nx\n"), [])

    def test_one_url(self):
        self.assertEqual(published_urls("---\npublished: https://a.example/p\n---\n"),
                         ["https://a.example/p"])

    def test_two_homes_for_one_piece(self):
        """The company blog and a personal mirror. Space or comma separated,
        or a list: all three read the same."""
        for value in ("https://a.example/p https://b.example/p",
                      "https://a.example/p, https://b.example/p"):
            self.assertEqual(published_urls("---\npublished: %s\n---\n" % value),
                             ["https://a.example/p", "https://b.example/p"])
        listed = "---\npublished:\n  - https://a.example/p\n  - https://b.example/p\n---\n"
        self.assertEqual(published_urls(listed),
                         ["https://a.example/p", "https://b.example/p"])

    def test_a_non_url_value_is_ignored(self):
        self.assertEqual(published_urls("---\npublished: pending\n---\n"), [])

    def test_set_published_fills_the_empty_line(self):
        out = set_published("---\nsurface: blog-base\npublished:\n---\nBody.\n",
                            "https://a.example/p")
        self.assertIn("published: https://a.example/p", out)
        self.assertIn("surface: blog-base", out)
        self.assertIn("Body.", out)
        self.assertEqual(out.count("published:"), 1)

    def test_set_published_appends_a_second_home(self):
        once = set_published("---\npublished:\n---\nx\n", "https://a.example/p")
        twice = set_published(once, "https://b.example/p")
        self.assertEqual(published_urls(twice),
                         ["https://a.example/p", "https://b.example/p"])
        self.assertEqual(twice.count("published:"), 1)

    def test_set_published_is_idempotent(self):
        once = set_published("---\npublished:\n---\nx\n", "https://a.example/p")
        self.assertEqual(set_published(once, "https://a.example/p"), once)

    def test_set_published_adds_frontmatter_when_there_is_none(self):
        out = set_published("# Title\n", "https://a.example/p")
        self.assertTrue(out.startswith("---\n"))
        self.assertEqual(published_urls(out), ["https://a.example/p"])

    def test_set_published_refuses_a_non_url(self):
        with self.assertRaises(ValueError):
            set_published("---\n---\nx\n", "not a url")


class TestBeats(unittest.TestCase):
    """A beat is an inline HTML comment scaffolding one section. You write
    into it and delete it when the section lands, so the beats still present
    are the sections still unwritten."""

    DRAFT = (
        "---\nsurface: blog-base\npublished:\n---\n"
        "<!-- TITLE ------------------------------------------------\n"
        "     What it is, not what it was like.\n-->\n"
        "# A title\n\n"
        "<!-- COLD OPEN ................................... 60-100 w\n"
        "     Job: the honest reaction, before the project exists.\n-->\n"
        "\n<!-- WHAT IT IS, FAST ......................... 100-140 w\n-->\n"
    )

    def test_open_beats_are_found_in_document_order(self):
        self.assertEqual(open_beats(self.DRAFT),
                         ["TITLE", "COLD OPEN", "WHAT IT IS, FAST"])

    def test_a_finished_section_leaves_no_beat(self):
        self.assertEqual(open_beats("---\n---\n# Title\n\nProse.\n"), [])

    def test_an_ordinary_comment_is_not_a_beat(self):
        text = "<!-- fix this later -->\n<!-- see also the other file -->\n"
        self.assertEqual(open_beats(text), [])

    def test_open_beats_on_a_draft_are_not_a_finding(self):
        self.assertEqual(check_beats(self.DRAFT), [])

    def test_open_beats_on_a_live_piece_are_findings(self):
        """Guide text shipping, or a section the outline asked for that
        nobody noticed was never written. It has happened."""
        live = self.DRAFT.replace("published:", "published: https://a.example/p")
        self.assertEqual([f.where for f in check_beats(live)],
                         ["TITLE", "COLD OPEN", "WHAT IT IS, FAST"])

    def test_a_live_piece_with_no_beats_is_clean(self):
        self.assertEqual(check_beats("---\npublished: https://a.example/p\n---\nProse.\n"), [])


class TestPieceStatus(unittest.TestCase):
    """Status is derived from the file and nothing else. There is no
    `status:` key to hand-write and no board to cache."""

    def test_empty(self):
        self.assertEqual(piece_status("---\nsurface: social\npublished:\n---\n"), "empty")

    def test_drafting_while_any_beat_is_open(self):
        self.assertEqual(piece_status(TestBeats.DRAFT), "drafting")
        self.assertEqual(piece_status("---\n---\n<!-- HOOK ..... 20 w\n-->\n"), "drafting")

    def test_written_once_the_beats_are_gone_and_prose_is_in(self):
        self.assertEqual(piece_status("---\n---\n# Title\n\nProse.\n"), "written")

    def test_published_beats_everything(self):
        live = TestBeats.DRAFT.replace("published:", "published: https://a.example/p")
        self.assertEqual(piece_status(live), "published")

    def test_a_plain_comment_is_not_prose(self):
        self.assertEqual(piece_status("---\n---\n<!-- todo -->\n"), "empty")


class TestPosts(unittest.TestCase):
    def test_a_url_is_billed_flat_no_matter_how_long(self):
        short = "see https://a.co"
        longer = "see https://example.com/" + "x" * 300
        self.assertEqual(billed_length(short), billed_length(longer))
        self.assertEqual(billed_length("https://a.co"), X_URL_BILLED_CHARS)

    def test_posts_are_split_on_numbered_headings(self):
        text = ("---\n---\n"
                "# X thread\n\nThis file explains itself. Not post one.\n\n"
                "## 1\n\nFirst post.\n\n## 2\n\nSecond post.\n")
        self.assertEqual(split_posts(text), ["First post.", "Second post."])

    def test_a_rule_of_dashes_still_works_as_a_fallback(self):
        self.assertEqual(split_posts("---\n---\nalpha\n\n---\n\nbeta\n"), ["alpha", "beta"])

    def test_the_post_body_stops_at_the_first_annotation(self):
        self.assertEqual(post_body("real text\n\n`99 characters` of 280\n> note"),
                         "real text")

    def test_a_post_with_no_annotation_is_unchanged(self):
        self.assertEqual(post_body("just the post"), "just the post")


class TestCitations(unittest.TestCase):
    def test_a_range_and_a_single_line_are_both_found(self):
        text = "See `writers.py:271-276` and `dg.py:14`."
        self.assertEqual(find_citations(text),
                         [("writers.py", 271, 276), ("dg.py", 14, 14)])

    def test_frontmatter_is_not_scanned(self):
        self.assertEqual(find_citations("---\nsurface: a.py:1-2\n---\nbody\n"), [])

    def test_a_live_citation_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text("a\nb\nc\nd\n")
            self.assertIsNone(check_citation(root, "w.py", 2, 3))

    def test_a_missing_file_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            finding = check_citation(pathlib.Path(tmp), "gone.py", 1, 2)
            self.assertEqual(finding.what, "no such file")

    def test_a_range_past_the_end_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text("a\nb\n")
            self.assertIn("2 lines", check_citation(root, "w.py", 271, 276).what)

    def test_a_range_that_is_now_blank_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text("a\n\n\n\nb\n")
            self.assertIn("blank", check_citation(root, "w.py", 2, 4).what)

    def test_a_citation_resolves_by_suffix_inside_a_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "hn_radio").mkdir()
            (root / "hn_radio" / "render.py").write_text("a\nb\nc\nd\ne\n")
            self.assertIsNone(check_citation(root, "render.py", 4, 5))

    def test_two_files_with_the_same_name_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for pkg in ("a", "b"):
                (root / pkg).mkdir()
                (root / pkg / "render.py").write_text("x\n" * 10)
            self.assertIn("ambiguous", check_citation(root, "render.py", 1, 2).what)


class TestReviewDate(unittest.TestCase):
    """The ledger groups entries under `## YYYY-MM-DD` day headings with
    `### [tag] title` entries beneath. The review's date is the day heading
    above it unless the review heading carries its own."""

    LEDGER = ("# demo build ledger\n\n"
              "## 2026-08-01\n\n### [decision] Ship it\nText.\n\n"
              "## 2026-11-30\n\n### [review] 90 day review\nFive lines.\n")

    def test_the_review_takes_the_day_heading_above_it(self):
        self.assertEqual(review_date(self.LEDGER), dt.date(2026, 11, 30))

    def test_a_date_in_the_review_heading_wins(self):
        text = "## 2026-08-01\n\n## 90 day review (2026-12-02)\nlines\n"
        self.assertEqual(review_date(text), dt.date(2026, 12, 2))

    def test_a_bare_review_heading_at_the_top_level_counts(self):
        text = "## 2026-12-01\n\n## 90 day review\nlines\n"
        self.assertEqual(review_date(text), dt.date(2026, 12, 1))

    def test_no_review_is_none(self):
        self.assertIsNone(review_date("## 2026-08-01\n\n### [decision] Ship it\n"))

    def test_a_review_with_no_date_anywhere_is_none(self):
        self.assertIsNone(review_date("# ledger\n\n### 90 day review\nlines\n"))

    def test_the_latest_review_wins(self):
        text = ("## 2026-11-30\n\n### [review] 90 day review\na\n\n"
                "## 2026-12-15\n\n### [review] 90 day review, second look\nb\n")
        self.assertEqual(review_date(text), dt.date(2026, 12, 15))

    def test_case_does_not_matter(self):
        self.assertEqual(review_date("## 2026-11-30\n\n### [Review] 90 Day Review\n"),
                         dt.date(2026, 11, 30))


if __name__ == "__main__":
    unittest.main()
