# tests/test_drip.py
from __future__ import annotations
import contextlib, datetime as dt, io, pathlib, re, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import drip  # noqa: E402

D = dt.date
TUE = D(2026, 10, 6)
PIECE = "https://gutentag.world/blog/2026-08-26-hn-radio-podcast"

NOTES = ("# Facts\n\n## Numbers\n\n"
         "- 86 live episodes. Median 350 ms over 156 runs, 13x faster.\n"
         "- Slowest call 6,153 ms. Costs $0.00016 a guess.\n\n"
         "## Superseded (2026-09-20)\n\n"
         "- 80 live episodes.\n")

SOCIAL = ("---\nproject: demo\nsurface: social\n---\n\n## Curious dev\n\n**X**\n\n"
          "```x\nI can't follow the front page anymore, so I made it talk.\n```\n\n"
          "**LinkedIn**\n\n```li\nEvery morning the front page is a wall of text.\n```\n")

CTX = drip.Context(
    notes=NOTES,
    blackouts={D(2026, 10, 14), D(2026, 10, 15), D(2026, 10, 29)},
    taken={D(2026, 10, 20): "drips/2026-09-01-other.md"},
    hooks={("every", "morning", "the", "front", "page", "is"): "social.md"},
)


def scaffold(dates=None, piece=PIECE):
    dates = dates or drip.drip_dates(TUE, CTX.blackouts | set(CTX.taken))
    links = {p: drip.link_line(piece, p, "hn_radio_podcast", {}) for p in drip.PLATFORMS}
    return drip.render_drip(
        {"project": "demo", "piece": piece, "piece_type": "blog",
         "piece_title": "HN Radio", "created": "2026-09-30", "voice": "sam-style"},
        dict(zip(drip.ARCHETYPES, dates)), links, CTX.hooks)


def written(text, n, post, fact='notes.md "Numbers" (86 live episodes)', keep_beat=False):
    """Section n with its post written the way the model would: beat deleted,
    fence filled, fact line replaced."""
    section = [s for s in drip.parse_sections(text) if s.n == n][0]
    chunk = text[section.start:section.end]
    if not keep_beat:
        chunk = re.sub(r"<!--.*?-->\n\n", "", chunk, count=1, flags=re.DOTALL)
    chunk = chunk.replace("```text\n```", "```text\n%s\n```" % post, 1)
    chunk = re.sub(r"^fact: .*$", "fact: %s" % fact, chunk, count=1, flags=re.MULTILINE)
    return text[:section.start] + chunk + text[section.end:]


def set_meta(text, n, key, value):
    section = [s for s in drip.parse_sections(text) if s.n == n][0]
    chunk = text[section.start:section.end]
    chunk = re.sub(r"^%s:.*$" % key, "%s: %s" % (key, value), chunk, count=1, flags=re.MULTILINE)
    return text[:section.start] + chunk + text[section.end:]


def whats(findings, n=None):
    return [f.what for f in findings if n is None or f.where.startswith("post %d " % n)]


class TestDates(unittest.TestCase):
    def test_default_start_is_the_first_tuesday_at_least_five_days_out(self):
        self.assertEqual(drip.default_start(D(2026, 9, 30)), D(2026, 10, 6))
        self.assertEqual(drip.default_start(D(2026, 10, 1)), D(2026, 10, 6))
        self.assertEqual(drip.default_start(D(2026, 10, 2)), D(2026, 10, 13))

    def test_six_posts_run_tuesday_and_thursday_over_three_weeks(self):
        self.assertEqual(drip.drip_dates(TUE, set()), [
            D(2026, 10, 6), D(2026, 10, 8), D(2026, 10, 13), D(2026, 10, 15),
            D(2026, 10, 20), D(2026, 10, 22)])

    def test_week_spacing_is_two_a_week_and_never_more_than_three(self):
        dates = drip.drip_dates(TUE, set())
        by_week = {}
        for day in dates:
            by_week.setdefault(day.isocalendar()[1], []).append(day)
        self.assertEqual(sorted(len(v) for v in by_week.values()), [2, 2, 2])
        for day in dates:
            self.assertIn(day.weekday(), drip.POST_WEEKDAYS)

    def test_a_blackout_moves_the_post_to_wednesday(self):
        dates = drip.drip_dates(TUE, {D(2026, 10, 8)})
        self.assertEqual(dates[:2], [D(2026, 10, 6), D(2026, 10, 7)])

    def test_a_date_another_post_holds_is_the_same_rule_as_a_blackout(self):
        dates = drip.drip_dates(TUE, {D(2026, 10, 6)})
        self.assertEqual(dates[:2], [D(2026, 10, 7), D(2026, 10, 8)])
        self.assertNotIn(D(2026, 10, 6), dates)

    def test_a_week_with_one_free_day_gets_one_post_and_the_drip_runs_longer(self):
        """Sam's real blackouts: Oct 14 and 15 leave only the Tuesday."""
        dates = drip.drip_dates(TUE, CTX.blackouts)
        self.assertEqual(dates, [
            D(2026, 10, 6), D(2026, 10, 8), D(2026, 10, 13),
            D(2026, 10, 20), D(2026, 10, 22), D(2026, 10, 27)])

    def test_nothing_lands_on_a_blocked_date(self):
        blocked = {TUE + dt.timedelta(days=i) for i in range(0, 40, 3)}
        dates = drip.drip_dates(TUE, blocked)
        self.assertEqual(len(dates), 6)
        self.assertFalse(blocked & set(dates))
        self.assertEqual(dates, sorted(dates))

    def test_a_drip_starts_on_a_tuesday_or_not_at_all(self):
        with self.assertRaises(ValueError):
            drip.drip_dates(D(2026, 10, 7), set())

    def test_an_impossible_schedule_raises_instead_of_running_forever(self):
        blocked = {TUE + dt.timedelta(days=i) for i in range(7 * 30)}
        with self.assertRaises(ValueError):
            drip.drip_dates(TUE, blocked)

    def test_blackouts_parse_from_the_yml_value(self):
        self.assertEqual(drip.parse_blackouts("2026-10-14, 2026-10-15,"),
                         {D(2026, 10, 14), D(2026, 10, 15)})
        self.assertEqual(drip.parse_blackouts(None), set())
        with self.assertRaises(ValueError):
            drip.parse_blackouts("Oct 14")

    def test_loose_dates_in_a_series_file(self):
        """The first real series wrote 'Thu Oct 1, 9:00 AM PT' with the year
        only in a URL. A blackout named in prose is not a post."""
        text = ("# Series\n\nClear of the Oct 14 and 15 blackouts.\n\n"
                "| 1 | Thu Oct 1, 9:00 AM PT | The problem |\n\n"
                "## 2. Tue Oct 6, 9:00 AM PT · A number\n\n"
                "date: 2026-10-08\n2026-10-13 something\n"
                "- link https://gutentag.world/blog/2026-09-30-flux\n")
        self.assertEqual(drip.dates_in(text), {
            D(2026, 10, 1), D(2026, 10, 6), D(2026, 10, 8), D(2026, 10, 13)})

    def test_a_strict_date_line_parses_and_a_loose_one_does_not(self):
        self.assertEqual(drip.post_date("2026-10-07 09:00 America/Los_Angeles"), D(2026, 10, 7))
        self.assertIsNone(drip.post_date("2026-10-07"))
        self.assertIsNone(drip.post_date("2026-10-07 9am PT"))
        self.assertIsNone(drip.post_date("2026-10-07 25:00 America/Los_Angeles"))


class TestHooks(unittest.TestCase):
    def test_a_hook_is_six_words_lowercased_without_punctuation(self):
        self.assertEqual(drip.hook('"I can\'t follow" the front page, anymore.'),
                         ("i", "can't", "follow", "the", "front", "page"))

    def test_a_short_post_is_its_own_hook(self):
        self.assertEqual(drip.hook("Three words only"), ("three", "words", "only"))

    def test_hooks_come_from_the_fenced_posts_of_social_md(self):
        self.assertEqual(drip.hooks_in(SOCIAL), [
            ("i", "can't", "follow", "the", "front", "page"),
            ("every", "morning", "the", "front", "page", "is")])

    def test_a_file_without_fences_falls_back_to_numbered_posts(self):
        text = "---\n---\n# Thread\n\nPreamble.\n\n## 1\n\nFirst post here.\n\n## 2\n\nSecond post here.\n"
        self.assertEqual(drip.hooks_in(text), [
            ("first", "post", "here"), ("second", "post", "here")])

    def test_used_hooks_names_the_first_file_using_each(self):
        used = drip.used_hooks([("social.md", SOCIAL),
                                ("drips/a.md", "```text\nEvery morning the front page is here.\n```\n")])
        self.assertEqual(used[("every", "morning", "the", "front", "page", "is")], "social.md")
        self.assertEqual(len(used), 2)

    def test_a_reused_hook_is_a_finding_naming_the_file(self):
        text = written(scaffold(), 1, "Every morning the front page is 86 items long.")
        self.assertTrue(any("already used in social.md" in w for w in whats(drip.check_drip(text, CTX), 1)))

    def test_two_posts_in_one_drip_may_not_share_a_hook(self):
        text = written(scaffold(), 1, "The front page has 86 episodes now, as audio.")
        text = written(text, 2, "The front page has 86 episodes now, measured.")
        self.assertTrue(any("is also post 1's" in w for w in whats(drip.check_drip(text, CTX), 2)))


class TestXLength(unittest.TestCase):
    def test_a_url_is_billed_at_23_so_a_long_link_still_fits(self):
        post = "86 episodes, all of it here: https://example.com/" + "x" * 300
        self.assertGreater(len(post), 280)
        text = set_meta(written(scaffold(), 1, post), 1, "link", "%s (body)" % PIECE)
        self.assertEqual(whats(drip.check_drip(text, CTX), 1), [])

    def test_an_over_limit_post_is_found(self):
        text = written(scaffold(), 1, "86 " + "x" * 290)
        self.assertIn("293 chars billed, limit is 280", whats(drip.check_drip(text, CTX), 1))

    def test_a_url_in_the_body_when_the_link_belongs_in_the_reply(self):
        text = written(scaffold(), 1, "86 episodes: https://example.com/a")
        self.assertIn("URL in the body but link says (reply)", whats(drip.check_drip(text, CTX), 1))

    def test_a_piece_on_x_puts_the_link_in_the_body(self):
        self.assertTrue(drip.link_line("https://x.com/sam/article/1", "x", "c", {}).endswith("(body)"))
        self.assertTrue(drip.link_line(PIECE, "x", "c", {}).endswith("(reply)"))
        self.assertTrue(drip.link_line(PIECE, "linkedin", "c", {}).endswith("(body)"))


class TestLinkedIn(unittest.TestCase):
    def post(self, body):
        return written(scaffold(), 4, body)      # Scaler is LinkedIn by default

    def test_too_short_is_found(self):
        self.assertTrue(any("at least 600" in w for w in whats(drip.check_drip(self.post("86 episodes."), CTX), 4)))

    def test_too_long_is_found(self):
        self.assertTrue(any("limit is 1500" in w for w in whats(drip.check_drip(self.post("86 " + "y" * 1600), CTX), 4)))

    def test_four_hashtags_is_one_too_many(self):
        body = "86 episodes. " + "y" * 600 + " #a #b #c #d"
        self.assertIn("4 hashtags, max is 3", whats(drip.check_drip(self.post(body), CTX), 4))

    def test_in_range_with_three_hashtags_passes(self):
        body = "86 episodes. " + "y" * 600 + " #a #b #c"
        self.assertEqual(whats(drip.check_drip(self.post(body), CTX), 4), [])

    def test_the_link_counts_at_full_length_on_linkedin(self):
        body = "86 episodes. " + "y" * 1400 + " https://example.com/" + "z" * 200
        self.assertTrue(any("limit is 1500" in w for w in whats(drip.check_drip(self.post(body), CTX), 4)))


class TestNumbers(unittest.TestCase):
    def test_numbers_are_extracted_as_written(self):
        self.assertEqual(drip.numbers_in("86 episodes, 6,153 ms, $0.00016, 9:00, 13x"),
                         ["86", "6,153", "0.00016", "9:00", "13"])

    def test_numbers_inside_urls_are_not_claims(self):
        self.assertEqual(drip.numbers_in("see https://a.co/2026-08-26-post/3"), [])

    def test_a_superseded_section_is_not_live(self):
        self.assertNotIn("80", drip.live_notes(NOTES))
        self.assertIn("86", drip.live_notes(NOTES))

    def test_a_superseded_section_ends_at_the_next_heading_of_its_level(self):
        notes = "## Superseded\n\n- 80\n\n### still superseded\n\n- 81\n\n## Live\n\n- 82\n"
        live = drip.live_notes(notes)
        self.assertNotIn("80", live)
        self.assertNotIn("81", live)
        self.assertIn("82", live)

    def test_a_number_in_notes_passes_and_one_outside_does_not(self):
        self.assertEqual(drip.untraced_numbers("86 episodes at 350 ms", NOTES), [])
        self.assertEqual(drip.untraced_numbers("80 episodes at 400 ms", NOTES), ["80", "400"])

    def test_the_token_has_to_be_literal(self):
        """6153 is not 6,153 and 0.35 is not 350 ms."""
        self.assertEqual(drip.untraced_numbers("6153 ms", NOTES), ["6153"])
        self.assertEqual(drip.untraced_numbers("0.35 s", NOTES), ["0.35"])

    def test_check_reports_each_untraced_number_once(self):
        text = written(scaffold(), 1, "Now 90 episodes, 90 of them live.")
        self.assertEqual([w for w in whats(drip.check_drip(text, CTX), 1) if "literal token" in w],
                         ["90 is not a literal token in notes.md"])


class TestCheck(unittest.TestCase):
    def test_a_fresh_scaffold_passes(self):
        self.assertEqual(drip.check_drip(scaffold(), CTX), [])

    def test_a_written_post_with_no_problems_passes(self):
        text = written(scaffold(), 1, "The front page, as 86 episodes of audio.")
        self.assertEqual(drip.check_drip(text, CTX), [])

    def test_a_missing_frontmatter_key_is_found(self):
        text = scaffold().replace("piece_title: HN Radio\n", "")
        self.assertIn("missing piece_title", whats(drip.check_drip(text, CTX)))

    def test_the_wrong_surface_or_piece_type_is_found(self):
        text = scaffold().replace("surface: drip", "surface: social").replace("piece_type: blog", "piece_type: podcast")
        found = whats(drip.check_drip(text, CTX))
        self.assertTrue(any("surface is 'social'" in w for w in found))
        self.assertTrue(any("piece_type 'podcast'" in w for w in found))

    def test_six_sections_in_archetype_order(self):
        text = scaffold().replace("## 3. Builder", "## 3. Scaler", 1)
        self.assertTrue(any("expected '3. Builder'" in w for w in whats(drip.check_drip(text, CTX))))
        five = scaffold()
        five = five[:five.index("## 6. Partner dev")]
        self.assertIn("5 sections, expected 6, one per archetype", whats(drip.check_drip(five, CTX)))

    def test_a_blackout_date_is_found(self):
        text = set_meta(scaffold(), 1, "date", "2026-10-14 09:00 America/Los_Angeles")
        self.assertIn("2026-10-14 is a launch blackout", whats(drip.check_drip(text, CTX), 1))

    def test_a_date_another_post_holds_is_found(self):
        text = set_meta(scaffold(), 1, "date", "2026-10-20 09:00 America/Los_Angeles")
        found = whats(drip.check_drip(text, CTX), 1)
        self.assertIn("2026-10-20 is already held by drips/2026-09-01-other.md", found)

    def test_two_posts_on_one_day_is_found(self):
        text = set_meta(scaffold(), 2, "date", "2026-10-06 09:00 America/Los_Angeles")
        self.assertIn("2026-10-06 is also post 1's date", whats(drip.check_drip(text, CTX), 2))

    def test_a_monday_is_found(self):
        text = set_meta(scaffold(), 1, "date", "2026-10-05 09:00 America/Los_Angeles")
        self.assertTrue(any("Monday" in w for w in whats(drip.check_drip(text, CTX), 1)))

    def test_an_unparseable_date_is_found(self):
        text = set_meta(scaffold(), 1, "date", "next Tuesday")
        self.assertTrue(any("not 'YYYY-MM-DD HH:MM Area/City'" in w for w in whats(drip.check_drip(text, CTX), 1)))

    def test_a_bad_platform_or_link_is_found(self):
        text = set_meta(set_meta(scaffold(), 1, "platform", "threads"), 1, "link", PIECE)
        found = whats(drip.check_drip(text, CTX), 1)
        self.assertTrue(any("platform 'threads'" in w for w in found))
        self.assertIn("link must end with (body) or (reply)", found)

    def test_an_em_dash_is_found(self):
        text = written(scaffold(), 1, "86 episodes — all audio.")
        self.assertIn("em dash", whats(drip.check_drip(text, CTX), 1))

    def test_a_written_post_may_not_keep_its_beat(self):
        text = written(scaffold(), 1, "86 episodes of audio.", keep_beat=True)
        self.assertTrue(any("still carries the beat: CURIOUS DEV" in w for w in whats(drip.check_drip(text, CTX), 1)))

    def test_an_unwritten_post_keeps_its_beat_without_complaint(self):
        self.assertEqual(drip.check_drip(scaffold(), CTX), [])

    def test_a_written_post_may_not_keep_the_fact_placeholder(self):
        text = written(scaffold(), 1, "86 episodes of audio.", fact="needs: one fact from notes.md")
        self.assertIn("fact line is still the placeholder", whats(drip.check_drip(text, CTX), 1))

    def test_published_with_no_post_is_found(self):
        text = set_meta(scaffold(), 1, "published", "https://x.com/s/1")
        self.assertIn("published but the post is empty", whats(drip.check_drip(text, CTX), 1))


class TestPost(unittest.TestCase):
    def test_mark_published_writes_the_permalink_on_that_post_only(self):
        text = written(scaffold(), 1, "86 episodes of audio.")
        out, section = drip.mark_published(text, 1, "https://x.com/s/1")
        self.assertEqual(section.n, 1)
        self.assertEqual(section.meta["platform"], "x")
        sections = drip.parse_sections(out)
        self.assertEqual(sections[0].meta["published"], "https://x.com/s/1")
        self.assertEqual(sections[1].meta["published"], "")
        self.assertEqual(drip.check_drip(out, CTX), [])

    def test_a_published_post_is_refused_a_second_time(self):
        text = written(scaffold(), 1, "86 episodes of audio.")
        out, _ = drip.mark_published(text, 1, "https://x.com/s/1")
        with self.assertRaises(ValueError):
            drip.mark_published(out, 1, "https://x.com/s/2")

    def test_an_unwritten_post_cannot_be_published(self):
        with self.assertRaises(ValueError):
            drip.mark_published(scaffold(), 1, "https://x.com/s/1")

    def test_a_missing_post_number_and_a_non_url_are_refused(self):
        text = written(scaffold(), 1, "86 episodes of audio.")
        with self.assertRaises(ValueError):
            drip.mark_published(text, 9, "https://x.com/s/1")
        with self.assertRaises(ValueError):
            drip.mark_published(text, 1, "x.com/s/1")

    def test_the_log_line_format(self):
        self.assertEqual(
            drip.log_line(D(2026, 10, 6), "x", "https://x.com/s/1", "advocacy/content/drips/a.md", 1),
            "2026-10-06 x https://x.com/s/1 advocacy/content/drips/a.md#1")


class TestSlug(unittest.TestCase):
    def test_a_blog_url_gives_its_own_slug_minus_the_date(self):
        self.assertEqual(drip.slug_for(PIECE), "hn-radio-podcast")
        self.assertEqual(drip.slug_for(PIECE, "A title that is ignored"), "hn-radio-podcast")

    def test_a_video_url_needs_the_title(self):
        self.assertEqual(drip.slug_for("https://www.youtube.com/watch?v=abc", "HN Radio, a daily podcast"),
                         "hn-radio-a-daily-podcast")
        with self.assertRaises(ValueError):
            drip.slug_for("https://youtu.be/abc123")


class TestCLI(unittest.TestCase):
    """scaffold, check and post against a throwaway repo. Never a real one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.tmp.name) / "demo-lab"
        (self.repo / "advocacy" / "content").mkdir(parents=True)
        (self.repo / "advocacy" / "notes.md").write_text(NOTES)
        (self.repo / "advocacy" / "content" / "social.md").write_text(SOCIAL)
        (self.repo / "_docs").mkdir()
        (self.repo / "_docs" / "x-series.md").write_text(
            "# Series\n\n## 1. Tue Oct 6, 9:00 AM PT\n\n```\nEvery voice agent answers two.\n```\n"
            "- link https://gutentag.world/blog/2026-09-30-flux\n")
        self.cfg = pathlib.Path(self.tmp.name) / "cfg.yml"
        self.cfg.write_text('launch_blackouts: "2026-10-14,2026-10-15,2026-10-29"\n'
                            'voice_personal: "sam-style"\nperson_slug: "sam_gutentag"\n'
                            'utm_domains: "deepgram.com"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = drip.main(["--config", str(self.cfg)] + [str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def scaffold(self, *extra, piece=PIECE):
        return self.run_cli("scaffold", "--repo", self.repo, "--piece", piece, "--type", "blog",
                            "--today", "2026-09-30", *extra)

    @property
    def drip_path(self):
        return self.repo / "advocacy" / "content" / "drips" / "2026-09-30-hn-radio-podcast.md"

    def test_scaffold_writes_the_file_in_the_spec_format(self):
        code, out, err = self.scaffold("--title", "HN Radio, a daily podcast nobody records")
        self.assertEqual(code, 0, err)
        text = self.drip_path.read_text()
        self.assertTrue(text.startswith(
            "---\nproject: demo\nsurface: drip\npiece: %s\npiece_type: blog\n"
            "piece_title: HN Radio, a daily podcast nobody records\ncreated: 2026-09-30\n"
            "sources: [advocacy/notes.md]\npasses: [sam-style, de-slop]\n---\n\n## 1. Curious dev\n"
            % PIECE), text[:400])
        sections = drip.parse_sections(text)
        self.assertEqual([s.archetype for s in sections], list(drip.ARCHETYPES))
        self.assertEqual([s.meta["platform"] for s in sections], ["x", "x", "x", "linkedin", "x", "linkedin"])
        for s in sections:
            self.assertEqual(list(s.meta), list(drip.META_KEYS))
            self.assertEqual(s.text, "")
            self.assertEqual(s.beats, [s.archetype.upper()])
            self.assertTrue(s.meta["date"].endswith(" 09:00 America/Los_Angeles"))

    def test_scaffold_dates_skip_blackouts_and_the_series(self):
        """Oct 6 is the series' day, Oct 14, 15 and 29 are blackouts."""
        self.scaffold()
        dates = [drip.post_date(s.meta["date"]) for s in drip.parse_sections(self.drip_path.read_text())]
        self.assertEqual(dates, [D(2026, 10, 7), D(2026, 10, 8), D(2026, 10, 13),
                                 D(2026, 10, 20), D(2026, 10, 22), D(2026, 10, 27)])

    def test_lead_archetypes_take_the_first_slots(self):
        self.scaffold("--lead", "Builder,Scaler")
        by = {s.archetype: drip.post_date(s.meta["date"]) for s in drip.parse_sections(self.drip_path.read_text())}
        self.assertEqual(by["Builder"], D(2026, 10, 7))
        self.assertEqual(by["Scaler"], D(2026, 10, 8))
        self.assertEqual(by["Curious dev"], D(2026, 10, 13))

    def test_start_names_the_first_week(self):
        self.scaffold("--start", "2026-11-02")
        first = drip.post_date(drip.parse_sections(self.drip_path.read_text())[0].meta["date"])
        self.assertEqual(first, D(2026, 11, 3))

    def test_the_beats_list_every_hook_already_used(self):
        self.scaffold()
        text = self.drip_path.read_text()
        self.assertIn("social.md          i can't follow the front page", text)
        self.assertIn("social.md          every morning the front page is", text)
        self.assertIn("_docs/x-series.md  every voice agent answers two", text)

    def test_a_second_drip_avoids_the_first_ones_dates_and_hooks(self):
        self.scaffold()
        text = written(self.drip_path.read_text(), 1, "The front page as 86 episodes of audio.")
        self.drip_path.write_text(text)
        code, out, err = self.scaffold(piece="https://gutentag.world/blog/2026-09-01-second-post")
        self.assertEqual(code, 0, err)
        second = (self.drip_path.parent / "2026-09-30-second-post.md").read_text()
        first_dates = {drip.post_date(s.meta["date"]) for s in drip.parse_sections(text)}
        second_dates = {drip.post_date(s.meta["date"]) for s in drip.parse_sections(second)}
        self.assertFalse(first_dates & second_dates)
        self.assertIn("drips/2026-09-30-hn-radio-podcast.md  the front page as 86 episodes", second)

    def test_scaffold_refuses_to_overwrite(self):
        self.assertEqual(self.scaffold()[0], 0)
        code, out, err = self.scaffold()
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", err)

    def test_scaffold_refuses_a_repo_with_no_advocacy_dir(self):
        code, out, err = self.run_cli("scaffold", "--repo", self.tmp.name, "--piece", PIECE, "--type", "blog")
        self.assertEqual(code, 2)

    def test_a_video_without_a_title_is_refused(self):
        code, out, err = self.scaffold(piece="https://youtu.be/abc123")
        self.assertEqual(code, 2)
        self.assertIn("--title", err)

    def test_owned_links_carry_the_x_article_utm_scheme(self):
        self.scaffold(piece="https://deepgram.com/learn/hn-radio")
        text = (self.drip_path.parent / "2026-09-30-hn-radio.md").read_text()
        self.assertIn("link: https://deepgram.com/learn/hn-radio?utm_source=x&utm_medium=social"
                      "&utm_campaign=hn_radio&utm_content=sam_gutentag_post (reply)", text)
        self.assertIn("utm_source=linkedin&utm_medium=social&utm_campaign=hn_radio"
                      "&utm_content=sam_gutentag_post (body)", text)

    def test_a_link_off_the_owned_domains_stays_untagged(self):
        self.assertEqual(self.scaffold()[0], 0)
        self.assertIn("link: %s (reply)" % PIECE, self.drip_path.read_text())

    def test_check_passes_a_fresh_scaffold_and_fails_a_bad_post(self):
        self.scaffold()
        code, out, err = self.run_cli("check", self.drip_path)
        self.assertEqual(code, 0, out)
        self.assertIn("ok: advocacy/content/drips/2026-09-30-hn-radio-podcast.md", out)
        text = written(self.drip_path.read_text(), 1, "Every morning the front page is 90 items — long.")
        self.drip_path.write_text(text)
        code, out, err = self.run_cli("check", self.drip_path)
        self.assertEqual(code, 1)
        lines = [l for l in out.splitlines() if l.startswith("post 1 (Curious dev): ")]
        self.assertEqual(len(lines), 3, out)
        self.assertTrue(any("em dash" in l for l in lines))
        self.assertTrue(any("90 is not a literal token" in l for l in lines))
        self.assertTrue(any("already used in social.md" in l for l in lines))

    def test_post_sets_published_and_appends_to_the_log(self):
        self.scaffold()
        self.drip_path.write_text(written(self.drip_path.read_text(), 1, "The front page as 86 episodes of audio."))
        code, out, err = self.run_cli("post", self.drip_path, 1, "https://x.com/sam/status/1", "--on", "2026-10-07")
        self.assertEqual(code, 0, err)
        self.assertEqual(drip.parse_sections(self.drip_path.read_text())[0].meta["published"],
                         "https://x.com/sam/status/1")
        log = (self.repo / "advocacy" / "content" / "published.log").read_text()
        self.assertEqual(log, "2026-10-07 x https://x.com/sam/status/1 "
                              "advocacy/content/drips/2026-09-30-hn-radio-podcast.md#1\n")
        code, out, err = self.run_cli("check", self.drip_path)
        self.assertEqual(code, 0, out)

    def test_post_refuses_a_second_time_and_leaves_the_log_alone(self):
        self.scaffold()
        self.drip_path.write_text(written(self.drip_path.read_text(), 1, "The front page as 86 episodes of audio."))
        self.run_cli("post", self.drip_path, 1, "https://x.com/sam/status/1", "--on", "2026-10-07")
        code, out, err = self.run_cli("post", self.drip_path, 1, "https://x.com/sam/status/2")
        self.assertEqual(code, 1)
        self.assertIn("already published", err)
        log = (self.repo / "advocacy" / "content" / "published.log").read_text()
        self.assertEqual(log.count("\n"), 1)

    def test_post_refuses_an_unwritten_post(self):
        self.scaffold()
        code, out, err = self.run_cli("post", self.drip_path, 2, "https://x.com/sam/status/2")
        self.assertEqual(code, 1)
        self.assertIn("not written yet", err)
        self.assertFalse((self.repo / "advocacy" / "content" / "published.log").exists())

    def test_post_refuses_while_check_fails(self):
        self.scaffold()
        self.drip_path.write_text(written(self.drip_path.read_text(), 1, "Now 90 episodes of audio."))
        before = self.drip_path.read_text()
        code, out, err = self.run_cli("post", self.drip_path, 1, "https://x.com/sam/status/1")
        self.assertEqual(code, 1)
        self.assertIn("check fails", err)
        self.assertEqual(self.drip_path.read_text(), before)
        self.assertFalse((self.repo / "advocacy" / "content" / "published.log").exists())

    def test_the_repo_is_inferred_from_the_drip_path(self):
        self.assertEqual(drip.repo_of(self.repo / "advocacy/content/drips/x.md"), self.repo.resolve())
        with self.assertRaises(ValueError):
            drip.repo_of(self.repo / "elsewhere/x.md")


if __name__ == "__main__":
    unittest.main()
