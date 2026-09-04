# tests/test_cycle_core.py
from __future__ import annotations
import sys, unittest, pathlib, tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from cycle_core import (
    STATUSES, STYLES, X_URL_BILLED_CHARS, Piece, billed_length, blocked_reason,
    check_beats, check_citation, check_limits, content_path, content_tree,
    apply_status, find_citations, gate_status, gate_task_title, open_beats,
    parent_of, parse_frontmatter, post_body, split_posts, status_from_board,
    status_of, surface_slug,
)

ALL = ["personal_blog", "personal_thread", "personal_linkedin",
       "personal_video_script", "corporate_blog", "corporate_thread",
       "corporate_linkedin"]


class TestLayout(unittest.TestCase):
    def test_a_blog_is_flat_because_it_has_no_variants(self):
        self.assertEqual(str(content_path("personal_blog")),
                         "content/personal/blog.md")

    def test_a_blog_refuses_to_name_a_variant(self):
        with self.assertRaises(ValueError):
            content_path("corporate_blog", "fun")

    def test_a_canonical_sits_at_the_top_of_its_own_directory(self):
        self.assertEqual(str(content_path("personal_thread")),
                         "content/personal/thread/thread.md")

    def test_a_variant_sits_one_level_under_its_canonical(self):
        self.assertEqual(str(content_path("personal_thread", "build-it-too")),
                         "content/personal/thread/variants/thread-build-it-too.md")

    def test_directory_depth_is_the_gate(self):
        """Gate B is everything at the top level, Gate C is everything one
        level down. That is the property the layout exists for."""
        for piece in content_tree(ALL):
            depth = len(piece.path.parts)
            if piece.gate == "B":
                self.assertEqual(depth, 4, piece.path)
            elif piece.gate == "C":
                self.assertEqual(depth, 5, piece.path)

    def test_the_style_suffix_is_the_style_key_verbatim(self):
        for style in STYLES:
            self.assertTrue(
                str(content_path("corporate_linkedin", style)).endswith(
                    "linkedin-%s.md" % style))

    def test_the_branch_is_not_repeated_in_the_filename(self):
        self.assertEqual(surface_slug("personal_video_script"), "video-script")
        self.assertEqual(surface_slug("corporate_thread"), "thread")

    def test_the_tree_is_twenty_seven_files(self):
        """Two blogs, five canonicals, twenty variants."""
        tree = content_tree(ALL)
        self.assertEqual(len(tree), 27)
        self.assertEqual(len([p for p in tree if p.gate == "A"]), 2)
        self.assertEqual(len([p for p in tree if p.gate == "B"]), 5)
        self.assertEqual(len([p for p in tree if p.gate == "C"]), 20)

    def test_every_path_is_unique(self):
        paths = [str(p.path) for p in content_tree(ALL)]
        self.assertEqual(len(paths), len(set(paths)))

    def test_a_derivative_without_its_blog_is_an_error(self):
        with self.assertRaises(ValueError):
            content_tree(["personal_thread"])

    def test_a_smaller_campaign_makes_a_smaller_tree(self):
        tree = content_tree(["personal_blog", "personal_thread"])
        self.assertEqual(len(tree), 1 + 1 + len(STYLES))


class TestFrontmatter(unittest.TestCase):
    DOC = ("---\n"
           "surface: personal-blog\n"
           "status: approved\n"
           "published:\n"
           "beats:\n"
           "  - the front page is text and I wanted it as audio\n"
           "  - why batch and not streaming\n"
           "---\n"
           "\n# Title\n\nBody.\n")

    def test_scalars_and_lists(self):
        data = parse_frontmatter(self.DOC)
        self.assertEqual(data["status"], "approved")
        self.assertEqual(data["published"], [])
        self.assertEqual(len(data["beats"]), 2)

    def test_no_frontmatter_is_not_an_error(self):
        self.assertEqual(parse_frontmatter("# Just a heading\n"), {})

    def test_status_of(self):
        self.assertEqual(status_of(self.DOC), "approved")
        self.assertIsNone(status_of("# nothing\n"))

    def test_a_misspelled_status_raises_rather_than_reading_as_unapproved(self):
        """`status: aproved` must not quietly hold the whole branch."""
        with self.assertRaises(ValueError):
            status_of("---\nstatus: aproved\n---\n")

    def test_every_declared_status_parses(self):
        for value in STATUSES:
            self.assertEqual(status_of("---\nstatus: %s\n---\n" % value), value)


class TestNothingDerivesFromAnUnapprovedParent(unittest.TestCase):
    def setUp(self):
        self.tree = {(p.surface, p.style): p for p in content_tree(ALL)}

    def test_a_blog_answers_to_nothing(self):
        self.assertIsNone(parent_of(self.tree[("personal_blog", None)]))

    def test_a_canonical_answers_to_its_branch_blog(self):
        parent = parent_of(self.tree[("personal_thread", None)])
        self.assertEqual(str(parent.path), "content/personal/blog.md")

    def test_a_variant_answers_to_its_canonical(self):
        parent = parent_of(self.tree[("corporate_linkedin", "fun")])
        self.assertEqual(str(parent.path),
                         "content/corporate/linkedin/linkedin.md")

    def test_the_branches_never_cross(self):
        for piece in content_tree(ALL):
            parent = parent_of(piece)
            if parent is None:
                continue
            self.assertIn("/%s/" % piece.path.parts[1], "/%s/" % parent.path.parts[1])

    def test_an_approved_parent_unblocks(self):
        piece = self.tree[("personal_thread", None)]
        self.assertIsNone(blocked_reason(
            piece, {"content/personal/blog.md": "approved"}))

    def test_a_published_parent_also_unblocks(self):
        piece = self.tree[("personal_thread", None)]
        self.assertIsNone(blocked_reason(
            piece, {"content/personal/blog.md": "published"}))

    def test_a_drafted_parent_blocks(self):
        piece = self.tree[("personal_thread", None)]
        reason = blocked_reason(piece, {"content/personal/blog.md": "drafted"})
        self.assertIn("not approved", reason)

    def test_a_missing_parent_blocks(self):
        piece = self.tree[("personal_thread", None)]
        self.assertIn("does not exist", blocked_reason(piece, {}))

    def test_an_approved_canonical_does_not_unblock_from_a_drafted_blog(self):
        """The chain is checked one link at a time on purpose: a variant asks
        its canonical, and the canonical asks the blog."""
        canonical = self.tree[("personal_thread", None)]
        self.assertIsNotNone(blocked_reason(
            canonical, {"content/personal/blog.md": "drafted"}))


class TestLimits(unittest.TestCase):
    def test_a_url_is_billed_flat_no_matter_how_long(self):
        short = "see https://a.co"
        longer = "see https://example.com/" + "x" * 300
        self.assertEqual(billed_length(short), billed_length(longer))

    def test_billing_is_what_decides_whether_a_post_fits(self):
        """A post counted naively reads far longer than it posts, and gets
        cut for nothing."""
        post = "Read it: https://example.com/" + "x" * 300
        self.assertGreater(len(post), 280)
        self.assertLess(billed_length(post), 280)
        self.assertEqual(check_limits("---\n---\n" + post, "personal_thread"), [])

    def test_an_over_limit_post_is_found(self):
        text = "---\n---\n" + "x" * 300
        findings = check_limits(text, "personal_thread")
        self.assertEqual(len(findings), 1)
        self.assertIn("limit is 280", findings[0].what)

    def test_each_post_in_a_thread_is_counted_separately(self):
        text = "---\n---\nfine\n\n---\n\n" + "x" * 300 + "\n\n---\n\nalso fine\n"
        findings = check_limits(text, "personal_thread")
        self.assertEqual([f.where for f in findings], ["post 2"])

    def test_three_links_in_one_post_is_a_finding(self):
        post = "a https://a.co b https://b.co c https://c.co"
        findings = check_limits("---\n---\n" + post, "personal_thread")
        self.assertTrue(any("belongs in a reply" in f.what for f in findings))

    def test_two_links_is_fine(self):
        post = "a https://a.co b https://b.co"
        self.assertEqual(check_limits("---\n---\n" + post, "personal_thread"), [])

    def test_a_blog_is_counted_in_words_once_not_per_post(self):
        text = "---\n---\n" + ("word " * 1300)
        findings = check_limits(text, "personal_blog")
        self.assertEqual(len(findings), 1)
        self.assertIn("1200", findings[0].what)

    def test_frontmatter_does_not_count_toward_the_limit(self):
        body = "x" * 270
        text = "---\nsurface: personal-thread\nstatus: drafted\n---\n" + body
        self.assertEqual(check_limits(text, "personal_thread"), [])

    def test_linkedin_gets_its_own_larger_limit(self):
        text = "---\n---\n" + "x" * 2900
        self.assertEqual(check_limits(text, "personal_linkedin"), [])


class TestBeats(unittest.TestCase):
    """A beat is an inline HTML comment scaffolding one section. You write
    into it and delete it when the section lands, so the beats still present
    are the sections still unwritten."""

    DRAFT = (
        "---\nstatus: drafted\n---\n"
        "<!-- TITLE ------------------------------------------------\n"
        "     What it was like, not what it is.\n-->\n"
        "# A title\n\n"
        "<!-- COLD OPEN ................................... 60-100 w\n"
        "     Job: the honest reaction, before the project exists.\n-->\n"
        "\n<!-- WHAT IT IS, FAST ......................... 100-140 w\n-->\n"
    )

    def test_open_beats_are_found_in_document_order(self):
        self.assertEqual(open_beats(self.DRAFT),
                         ["TITLE", "COLD OPEN", "WHAT IT IS, FAST"])

    def test_a_finished_section_leaves_no_beat(self):
        self.assertEqual(open_beats("---\nstatus: drafted\n---\n# Title\n\nProse.\n"), [])

    def test_an_ordinary_comment_is_not_a_beat(self):
        """Only a section scaffold counts. A note to self is not one."""
        text = "<!-- fix this later -->\n<!-- see also the other file -->\n"
        self.assertEqual(open_beats(text), [])

    def test_open_beats_on_a_draft_are_not_a_finding(self):
        """That is just what a draft looks like."""
        self.assertEqual(check_beats(self.DRAFT), [])

    def test_open_beats_on_an_approved_piece_are_findings(self):
        """Guide text shipping, or a section the outline asked for that
        nobody noticed was never written. It has happened."""
        approved = self.DRAFT.replace("status: drafted", "status: approved")
        findings = check_beats(approved)
        self.assertEqual([f.where for f in findings],
                         ["TITLE", "COLD OPEN", "WHAT IT IS, FAST"])

    def test_a_published_piece_with_no_beats_is_clean(self):
        text = "---\nstatus: published\n---\n# Title\n\nProse.\n"
        self.assertEqual(check_beats(text), [])

    def test_status_can_be_passed_in_rather_than_parsed(self):
        self.assertEqual(len(check_beats(self.DRAFT, status="published")), 3)


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
        """The reshoot case: a module split moved the code and the range now
        points past the end of a file that still exists."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text("a\nb\n")
            finding = check_citation(root, "w.py", 271, 276)
            self.assertIn("2 lines", finding.what)

    def test_a_range_that_is_now_blank_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "w.py").write_text("a\n\n\n\nb\n")
            finding = check_citation(root, "w.py", 2, 4)
            self.assertIn("blank", finding.what)


class TestGateStatus(unittest.TestCase):
    def test_an_untouched_campaign_is_all_missing(self):
        pieces = content_tree(ALL)
        status = gate_status(pieces, {})
        self.assertEqual(status["A"]["missing"], 2)
        self.assertEqual(status["C"]["total"], 20)

    def test_counts_land_in_the_right_gate(self):
        pieces = content_tree(ALL)
        status = gate_status(pieces, {"content/personal/blog.md": "approved"})
        self.assertEqual(status["A"]["approved"], 1)
        self.assertEqual(status["A"]["missing"], 1)


if __name__ == "__main__":
    unittest.main()


class TestRealFormatsFoundByMigration(unittest.TestCase):
    """Both of these passed the synthetic tests and were wrong about how the
    content is actually written. Migrating a real campaign found them."""

    def test_posts_are_split_on_numbered_headings(self):
        text = ("---\nstatus: approved\n---\n"
                "# X thread\n\nThis file explains itself. Not post one.\n\n"
                "## 1\n\nFirst post.\n\n## 2\n\nSecond post.\n")
        self.assertEqual(split_posts(text), ["First post.", "Second post."])

    def test_the_preamble_is_not_counted_as_a_post(self):
        """Counting it reported a 5,483 character violation on a thread that
        was fine."""
        text = ("---\n---\n# Title\n\n" + "x" * 400 +
                "\n\n## 1\n\nshort post\n")
        self.assertEqual(check_limits(text, "personal_thread"), [])

    def test_a_rule_of_dashes_still_works_as_a_fallback(self):
        text = "---\n---\nalpha\n\n---\n\nbeta\n"
        self.assertEqual(split_posts(text), ["alpha", "beta"])

    def test_a_citation_resolves_by_suffix_inside_a_package(self):
        """`render.py:4-5` means the render.py in this repo, not one sitting
        at the root. Otherwise every module inside a package reads as rotted."""
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
            finding = check_citation(root, "render.py", 1, 2)
            self.assertIn("ambiguous", finding.what)

    def test_a_genuinely_missing_file_is_still_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            finding = check_citation(pathlib.Path(tmp), "writers.py", 271, 276)
            self.assertEqual(finding.what, "no such file")

    def test_production_notes_do_not_count_toward_a_post(self):
        """A post carries its own character count and blockquoted image notes
        after the text. None of it posts, so none of it counts. Counting it
        reported every post in a clean nine-post thread as double its length."""
        text = ("---\nstatus: approved\n---\n"
                "## 1\n\n" + "x" * 250 + "\n\n"
                "`251 characters` of 280\n\n"
                "> **Image:** the meme, same one that opens the blog, at\n"
                "> assets/cold-open-meme.png. Already captured. Alternative if\n"
                "> the meme reads as too casual for a first impression.\n")
        self.assertEqual(check_limits(text, "personal_thread"), [])

    def test_the_post_body_stops_at_the_first_annotation(self):
        self.assertEqual(post_body("real text\n\n`99 characters` of 280\n> note"),
                         "real text")

    def test_a_post_with_no_annotation_is_unchanged(self):
        self.assertEqual(post_body("just the post"), "just the post")

    def test_an_over_limit_post_is_still_caught_after_stripping(self):
        text = "---\nstatus: approved\n---\n## 1\n\n" + "x" * 400 + "\n\n`400 characters`\n"
        findings = check_limits(text, "personal_thread")
        self.assertEqual(len(findings), 1)
        self.assertIn("400 chars", findings[0].what)


class TestTheBoardIsTheSourceOfTruth(unittest.TestCase):
    """Asana owns gate state. A gate task marked complete IS that piece being
    approved. The file carries a cache of that answer and never the reverse."""

    def setUp(self):
        self.tree = content_tree(ALL)
        self.by = {(p.surface, p.style): p for p in self.tree}

    def test_titles_match_the_ones_intake_files(self):
        self.assertEqual(gate_task_title(self.by[("personal_blog", None)]),
                         "Gate A: Personal blog, edit to publish ready")
        self.assertEqual(gate_task_title(self.by[("personal_thread", None)]),
                         "Gate B: Personal thread, edit to publish ready")
        self.assertEqual(gate_task_title(self.by[("personal_thread", "build-it-too")]),
                         "Gate C: Personal thread, build-it-too variant")

    def test_every_piece_maps_to_a_distinct_task(self):
        """A collision would make one task approve two pieces."""
        titles = [gate_task_title(p) for p in self.tree]
        self.assertEqual(len(titles), len(set(titles)))

    def test_a_completed_task_approves_its_piece(self):
        paths = {str(p.path) for p in self.tree}
        status = status_from_board(
            self.tree, ["Gate B: Personal thread, edit to publish ready"],
            existing_paths=paths)
        self.assertEqual(status["content/personal/thread/thread.md"], "approved")

    def test_an_incomplete_task_leaves_the_piece_drafted(self):
        paths = {str(p.path) for p in self.tree}
        status = status_from_board(self.tree, [], existing_paths=paths)
        self.assertEqual(status["content/personal/thread/thread.md"], "drafted")

    def test_a_file_that_does_not_exist_is_absent_not_drafted(self):
        """blocked_reason has to be able to say 'does not exist yet', which
        is a different problem from 'exists and is not approved'."""
        status = status_from_board(self.tree, [], existing_paths=set())
        self.assertEqual(status, {})

    def test_published_comes_from_the_file_not_the_board(self):
        """A live URL is a fact about the world. No checkbox can tell you."""
        paths = {str(p.path) for p in self.tree}
        status = status_from_board(
            self.tree, [], existing_paths=paths,
            published_by_path={"content/personal/blog.md": "https://example.com/x"})
        self.assertEqual(status["content/personal/blog.md"], "published")

    def test_the_board_unblocks_a_derivative(self):
        """The whole point: complete the Gate A task, and Gate B opens."""
        piece = self.by[("personal_thread", None)]
        paths = {str(p.path) for p in self.tree}
        blocked = status_from_board(self.tree, [], existing_paths=paths)
        self.assertIsNotNone(blocked_reason(piece, blocked))
        open_ = status_from_board(
            self.tree, ["Gate A: Personal blog, edit to publish ready"],
            existing_paths=paths)
        self.assertIsNone(blocked_reason(piece, open_))


class TestTheFileIsOnlyACache(unittest.TestCase):
    def test_the_cache_is_written_with_the_date_it_was_synced(self):
        out = apply_status("---\nsurface: personal-blog\n---\nProse.\n",
                           "approved", "2026-08-28")
        self.assertIn("status: approved", out)
        self.assertIn("status_synced: 2026-08-28", out)
        self.assertEqual(status_of(out), "approved")

    def test_rewriting_replaces_rather_than_appends(self):
        once = apply_status("---\nstatus: drafted\n---\nx\n", "approved", "2026-08-28")
        twice = apply_status(once, "published", "2026-08-29")
        lines = twice.split("\n")
        self.assertEqual(len([l for l in lines if l.startswith("status:")]), 1)
        self.assertEqual(len([l for l in lines if l.startswith("status_synced:")]), 1)
        self.assertIn("status_synced: 2026-08-29", twice)
        self.assertEqual(status_of(twice), "published")

    def test_the_rest_of_the_frontmatter_survives(self):
        out = apply_status(
            "---\nsurface: personal-blog\npublished: https://example.com/x\n---\nBody.\n",
            "published", "2026-08-28")
        self.assertIn("surface: personal-blog", out)
        self.assertIn("published: https://example.com/x", out)
        self.assertIn("Body.", out)

    def test_a_file_with_no_frontmatter_gets_one(self):
        out = apply_status("# Title\n\nProse.\n", "drafted", "2026-08-28")
        self.assertTrue(out.startswith("---\n"))
        self.assertEqual(status_of(out), "drafted")

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(ValueError):
            apply_status("---\n---\nx\n", "aproved", "2026-08-28")
