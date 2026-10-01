# tests/test_last_looks.py
from __future__ import annotations
import contextlib, io, json, os, pathlib, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import last_looks as ll  # noqa: E402
import drip  # noqa: E402

NOTES = ("# Notes\n\n## Numbers\n\n- 86 live episodes. Median 350 ms over 156 runs.\n"
         "- Slowest call 6,153 ms. Costs $0.00016 a guess. 93.78% agree.\n\n"
         "## Superseded (2026-09-20)\n\n- 80 live episodes.\n")

FM = "---\nproject: demo\nsurface: social\nstatus: drafted\npasses: [sam-style, de-slop]\n---\n\n"

OPTS = ll.Options(voice="sam-style", domains=("deepgram.com",), person_slug="sam_gutentag",
                  blog_utm_source="samgutentag_blog", net=True, ffprobe=False)


def fake_fetch(table):
    """A fetcher over a dict of url -> Response (or status int, or (status, ctype, data))."""
    calls = []

    def fetch(url, method="GET"):
        calls.append((method, url))
        value = table.get(url, 404)
        if isinstance(value, dict):
            value = value[method]
        if isinstance(value, int):
            return ll.Response(value, "text/html", b"")
        if isinstance(value, tuple):
            return ll.Response(*value)
        return value
    fetch.calls = calls
    return fetch


def png(width, height=800):
    return (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big")
            + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + bytes(4))


def jpeg(width, height=800):
    app0 = b"\xff\xe0" + (16).to_bytes(2, "big") + b"JFIF\x00" + bytes(9)
    sof0 = (b"\xff\xc0" + (17).to_bytes(2, "big") + b"\x08" + height.to_bytes(2, "big")
            + width.to_bytes(2, "big") + b"\x03" + bytes(9))
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


def gif(width, height=800):
    return b"GIF89a" + width.to_bytes(2, "little") + height.to_bytes(2, "little") + bytes(4)


def webp_x(width, height=800):
    return (b"RIFF" + bytes(4) + b"WEBP" + b"VP8X" + (10).to_bytes(4, "little") + bytes(4)
            + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little"))


def webp_lossy(width, height=800):
    return (b"RIFF" + bytes(4) + b"WEBP" + b"VP8 " + bytes(4) + bytes(3) + b"\x9d\x01\x2a"
            + width.to_bytes(2, "little") + height.to_bytes(2, "little"))


def messages(results):
    return [m for _, m in results]


class TestFrontmatter(unittest.TestCase):
    def test_complete_frontmatter_passes(self):
        self.assertEqual(ll.check_frontmatter(FM + "body", "sam-style"), [])

    def test_no_frontmatter_is_found(self):
        self.assertEqual(ll.check_frontmatter("# just a heading\n", "sam-style"), [(None, "no frontmatter")])

    def test_missing_status_and_passes(self):
        text = "---\nproject: demo\n---\n"
        self.assertEqual(messages(ll.check_frontmatter(text, "sam-style")),
                         ["frontmatter missing status", "frontmatter missing passes"])

    def test_passes_must_name_the_voice_and_de_slop(self):
        text = "---\nstatus: drafted\npasses: [de-slop]\n---\n"
        self.assertEqual(messages(ll.check_frontmatter(text, "sam-style")),
                         ["passes does not list both sam-style and de-slop"])
        text = "---\nstatus: drafted\npasses:\n  - sam-style\n  - de-slop\n---\n"
        self.assertEqual(ll.check_frontmatter(text, "sam-style"), [])

    def test_a_drip_needs_no_status(self):
        text = "---\nsurface: drip\npasses: [sam-style, de-slop]\n---\n"
        self.assertEqual(ll.check_frontmatter(text, "sam-style", need_status=False), [])


class TestProse(unittest.TestCase):
    def test_em_dash_is_reported_with_the_file_line(self):
        text = FM + "clean\n\nthis — that\n"
        self.assertEqual(ll.check_em_dashes(text), [(10, "em dash")])

    def test_banned_words_match_their_inflections_case_insensitively(self):
        text = FM + "We Leverage it.\nIt unlocked a robust path.\n"
        self.assertEqual(ll.check_banned_words(text), [
            (8, 'banned word "leverage"'), (9, 'banned word "robust"'), (9, 'banned word "unlock"')])


class TestNumbers(unittest.TestCase):
    def test_numbers_in_notes_pass_and_others_do_not(self):
        text = FM + "Median 350 ms over 156 runs, but 90 of them.\n"
        self.assertEqual(ll.check_numbers(text, NOTES), [(8, "number 90 not in notes.md")])

    def test_decimals_and_thousands_are_one_token(self):
        text = FM + "6,153 ms and 93.78% and 93.79%.\n"
        self.assertEqual(messages(ll.check_numbers(text, NOTES)), ["number 93.79 not in notes.md"])

    def test_a_thousands_token_matches_its_plain_spelling(self):
        self.assertEqual(ll.check_numbers(FM + "6153 ms\n", "notes: 6,153 ms"), [])
        self.assertEqual(ll.check_numbers(FM + "6,153 ms\n", "notes: 6153 ms"), [])

    def test_budgets_counts_years_citations_and_code_are_skipped(self):
        text = (FM + "COLD OPEN 60-100 words\n274 characters\nIn 2026 and 1999.\n"
                "See render.py:120-140 and `sample_rate=24000`.\n"
                "```\nrate = 48000\n```\nhttps://example.com/p/4567?x=89\n")
        self.assertEqual(ll.check_numbers(text, NOTES), [])

    def test_single_digits_are_prose(self):
        self.assertEqual(ll.check_numbers(FM + "3 stories from a pool of 7\n", NOTES), [])

    def test_a_superseded_number_is_not_live(self):
        self.assertEqual(messages(ll.check_numbers(FM + "80 episodes\n", NOTES)),
                         ["number 80 not in notes.md"])

    def test_no_notes_is_one_finding_when_there_is_something_to_trace(self):
        self.assertEqual(ll.check_numbers(FM + "no numbers here\n", None), [])
        self.assertEqual(len(ll.check_numbers(FM + "350 ms\n", None)), 1)


SOCIAL_FENCED = FM + """## Curious dev

**X** (fact N1)

```x
I can't follow the front page anymore, so I made it talk. https://example.com/a/very/long/path/that/would/not/fit/inside/the/limit/if/counted/raw/by/python/at/all/really/truly
```

Characters: 100

**LinkedIn**

```li
%s
```
"""

SOCIAL_QUOTED = FM + """## Explorer

**X**

> Ran a 61-minute podcast through a local model. %s

**LinkedIn**

> First line.
>
> %s
"""

SOCIAL_LABELED = FM + """## 1. Builder

**Fact:** notes.md.

### X

First paragraph of the post.

Second paragraph, still the post. https://example.com/x

`214 characters` of 280 as X counts it

> **Image:** `advocacy/assets/card.png`, the share card.

### LinkedIn

%s

Second LinkedIn paragraph #one #two #three #four

Characters: 1,254
"""


class TestSocial(unittest.TestCase):
    def test_fenced_posts_are_read_and_a_url_bills_at_23(self):
        posts = ll.social_posts(SOCIAL_FENCED % ("x" * 700))
        self.assertEqual([p.platform for p in posts], ["x", "linkedin"])
        self.assertTrue(posts[0].body.startswith("I can't follow"))
        self.assertEqual(ll.billed_length(posts[0].body), len("I can't follow the front page anymore, so I made it talk. ") + 23)
        self.assertEqual([m for m in messages(ll.check_social(SOCIAL_FENCED % ("x" * 700)))
                          if "X post for" in m], [])

    def test_an_over_limit_x_post_is_found_with_its_line(self):
        long = "word " * 70
        text = SOCIAL_FENCED.replace("I can't follow the front page anymore, so I made it talk.", long) % ("x" * 700)
        found = [(l, m) for l, m in ll.check_social(text) if "X post for Curious dev" in m]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], 10)
        self.assertIn("limit 280", found[0][1])

    def test_blockquoted_posts_are_read_without_the_markup(self):
        posts = ll.social_posts(SOCIAL_QUOTED % ("tail", "y" * 600))
        self.assertEqual(posts[0].body, "Ran a 61-minute podcast through a local model. tail")
        self.assertTrue(posts[1].body.startswith("First line.\n\nyyy"))
        self.assertNotIn(">", posts[1].body)

    def test_a_labeled_post_runs_to_the_count_line_and_skips_the_image_note(self):
        posts = ll.social_posts(SOCIAL_LABELED % ("z" * 600))
        x = posts[0]
        self.assertEqual(x.platform, "x")
        self.assertEqual(x.archetype, "1. Builder")
        self.assertEqual(x.body, "First paragraph of the post.\n\nSecond paragraph, still the post. https://example.com/x")
        li = posts[1]
        self.assertTrue(li.body.startswith("z" * 600))
        self.assertIn("#four", li.body)
        self.assertNotIn("Characters", li.body)

    def test_a_wrapped_label_does_not_become_the_post(self):
        text = FM + ("## Scaler\n\n**LinkedIn** (fact N8; asset: `a.mp3`\nover a still, or needs: a capture of\n"
                     "the picker preselected)\n\n> The real post, first line.\n>\n> Second quoted paragraph.\n\n"
                     "Characters: 60\n")
        posts = ll.social_posts(text)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].body, "The real post, first line.\n\nSecond quoted paragraph.")

    def test_linkedin_range_hashtags_and_the_count_of_posts(self):
        found = messages(ll.check_social(SOCIAL_LABELED % ("z" * 600)))
        self.assertIn("found 1 X posts, expected 6", found)
        self.assertIn("found 1 LinkedIn posts, expected 6", found)
        self.assertTrue(any("has 4 hashtags, max 3" in m for m in found))
        short = messages(ll.check_social(SOCIAL_QUOTED % ("tail", "short")))
        self.assertTrue(any("wants at least 600" in m for m in short))
        long = messages(ll.check_social(SOCIAL_QUOTED % ("tail", "y" * 1600)))
        self.assertTrue(any("limit 1500" in m for m in long))


class TestDrip(unittest.TestCase):
    def setUp(self):
        dates = drip.drip_dates(drip.first_tuesday(__import__("datetime").date(2026, 10, 6)), set())
        links = {p: drip.link_line("https://example.com/blog/post", p, "post", {}) for p in drip.PLATFORMS}
        self.text = drip.render_drip(
            {"project": "demo", "piece": "https://example.com/blog/post", "piece_type": "blog",
             "piece_title": "Post", "created": "2026-10-01", "voice": "sam-style"},
            dict(zip(drip.ARCHETYPES, dates)), links, {})
        self.ctx = drip.Context(notes=NOTES, blackouts=set(), taken={}, hooks={})

    def test_a_fresh_scaffold_passes_the_drip_rules(self):
        self.assertEqual(ll.check_drip_text(self.text, self.ctx), [])

    def test_drip_findings_are_reported_without_em_dashes(self):
        post = "An — odd post with 90 things " + "x" * 300
        text = self.text.replace("```text\n```", "```text\n%s\n```" % post, 1)
        found = messages(ll.check_drip_text(text, self.ctx))
        self.assertTrue(any("chars billed, limit is 280" in m for m in found))
        self.assertTrue(any("90 is not a literal token" in m for m in found))
        self.assertFalse(any(m.endswith("em dash") for m in found))
        self.assertEqual(len(ll.check_em_dashes(text)), 1)


class TestUrls(unittest.TestCase):
    def test_head_then_get_once_per_url_and_skip_hosts(self):
        ll._URL_CACHE.clear()
        fetch = fake_fetch({"https://ok.example.com/a": 200,
                            "https://get.example.com/b": {"HEAD": 405, "GET": 200}})
        text = FM + ("https://ok.example.com/a. and https://get.example.com/b, and "
                     "https://gone.example.com/c and https://x.com/u/status/1 https://api.deepgram.com/v1/listen\n"
                     "https://ok.example.com/a again\n")
        found = ll.check_urls(text, fetch)
        self.assertEqual(messages(found), ["URL does not resolve: https://gone.example.com/c"])
        self.assertEqual(fetch.calls.count(("HEAD", "https://ok.example.com/a")), 1)
        self.assertIn(("GET", "https://get.example.com/b"), fetch.calls)
        self.assertFalse(any("x.com" in u or "api.deepgram" in u for _, u in fetch.calls))


class TestUtm(unittest.TestCase):
    D = ("deepgram.com",)

    def test_an_owned_link_needs_all_four_keys(self):
        self.assertEqual(ll.utm_findings("https://developers.deepgram.com/docs/x", self.D),
                         ["owned link missing utm_source, utm_medium, utm_campaign, utm_content"])
        self.assertEqual(ll.utm_findings(
            "https://deepgram.com/learn/p?utm_source=x&utm_medium=social&utm_campaign=p", self.D),
            ["owned link missing utm_content"])

    def test_a_fully_tagged_owned_link_passes_and_extra_keys_do_not(self):
        url = "https://deepgram.com/p?utm_source=x&utm_medium=social&utm_campaign=p&utm_content=sam_gutentag_post"
        self.assertEqual(ll.utm_findings(url, self.D, "sam_gutentag"), [])
        self.assertEqual(ll.utm_findings(url + "&utm_term=t", self.D, "sam_gutentag"),
                         ["owned link carries utm_term; only the four utm keys"])

    def test_the_person_goes_in_content_not_source(self):
        url = "https://deepgram.com/p?utm_source=sam_gutentag&utm_medium=social&utm_campaign=p&utm_content=sam_gutentag_post"
        self.assertEqual(ll.utm_findings(url, self.D, "sam_gutentag"),
                         ["utm_source 'sam_gutentag' names the person; the person belongs in utm_content"])
        blog = "https://deepgram.com/p?utm_source=samgutentag_blog&utm_medium=referral&utm_campaign=p&utm_content=sam_gutentag_blog"
        self.assertEqual(ll.utm_findings(blog, self.D, "sam_gutentag", "samgutentag_blog"), [])
        other = "https://deepgram.com/p?utm_source=x&utm_medium=social&utm_campaign=p&utm_content=post"
        self.assertEqual(ll.utm_findings(other, self.D, "sam_gutentag"),
                         ["utm_content 'post' should be sam_gutentag_<placement>"])

    def test_nothing_else_is_tagged(self):
        self.assertEqual(ll.utm_findings("https://github.com/o/r?utm_source=x", self.D),
                         ["tagged link on a domain that is not owned (github.com); remove utm_source"])
        self.assertEqual(ll.utm_findings("https://github.com/o/r", self.D), [])
        self.assertEqual(ll.utm_findings("https://api.deepgram.com/v1/listen?model=nova-3", self.D), [])

    def test_links_in_code_are_not_links(self):
        text = FM + "`https://deepgram.com/a`\n\n```\ncurl https://deepgram.com/b\n```\n[c](https://deepgram.com/c)\n"
        found = ll.check_utms(text, OPTS)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], 13)
        self.assertIn("https://deepgram.com/c", found[0][1])


class TestImages(unittest.TestCase):
    def test_widths_are_read_from_each_header(self):
        self.assertEqual(ll.image_info(png(1600, 900)), ("png", 1600, 900))
        self.assertEqual(ll.image_info(jpeg(1600, 900)), ("jpeg", 1600, 900))
        self.assertEqual(ll.image_info(gif(1600, 900)), ("gif", 1600, 900))
        self.assertEqual(ll.image_info(webp_x(1600, 900)), ("webp", 1600, 900))
        self.assertEqual(ll.image_info(webp_lossy(1600, 900)), ("webp", 1600, 900))
        self.assertEqual(ll.image_info(b'<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"/>'),
                         ("svg", None, None))
        self.assertIsNone(ll.image_info(b"BM" + bytes(40)))
        self.assertIsNone(ll.image_info(b"%PDF-1.4"))

    def test_local_images_exist_are_a_known_type_and_wide_enough(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "assets").mkdir()
            (root / "assets" / "wide.png").write_bytes(png(1200))
            (root / "assets" / "narrow.jpg").write_bytes(jpeg(700))
            (root / "assets" / "logo.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
            (root / "assets" / "odd.bmp").write_bytes(b"BM" + bytes(40))
            text = (FM + "![a](assets/wide.png)\n![b](assets/narrow.jpg)\n![c](assets/logo.svg)\n"
                    "<img src=\"assets/odd.bmp\" alt=\"d\">\n![e](assets/missing.png)\n")
            found = ll.check_images_md(text, root, OPTS)
            self.assertEqual(found, [
                (9, "image assets/narrow.jpg is 700 px wide, wants at least 1200"),
                (11, "image assets/odd.bmp is not PNG, JPEG, GIF, WebP or SVG"),
                (12, "image assets/missing.png does not exist")])

    def test_the_width_floor_is_adjustable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "n.png").write_bytes(png(1000))
            self.assertEqual(ll.check_images_md(FM + "![a](n.png)\n", root, OPTS._replace(min_width=1000)), [])

    def test_remote_images_fetch_as_images(self):
        fetch = fake_fetch({
            "https://cdn.example.com/a.png": (200, "image/png", png(1600)),
            "https://cdn.example.com/b.png": (200, "text/html", b"<html>"),
            "https://cdn.example.com/c.png": 404,
            "https://cdn.example.com/d.jpg": (200, "image/jpeg", jpeg(800)),
        })
        text = FM + ("![a](https://cdn.example.com/a.png)\n![b](https://cdn.example.com/b.png)\n"
                     "![c](https://cdn.example.com/c.png)\n![d](https://cdn.example.com/d.jpg)\n")
        found = messages(ll.check_images_md(text, "/nowhere", OPTS._replace(fetch=fetch)))
        self.assertEqual(found, [
            "image https://cdn.example.com/b.png is text/html, not an image content type",
            "image https://cdn.example.com/c.png returned 404",
            "image https://cdn.example.com/d.jpg is 800 px wide, wants at least 1200"])


PAGE = """<!doctype html><html><head>
<meta property="og:image" content="%s">
%s
</head><body>
<img src="/img/hero.png"><img src="https://cdn.example.com/missing.png">
<img src="data:image/png;base64,AAAA">
<a href="https://developers.deepgram.com/docs/x">docs</a>
<a href="https://github.com/o/r">repo</a>
</body></html>"""


class TestPage(unittest.TestCase):
    def test_a_live_page_checks_every_image_and_the_social_cards(self):
        ll._URL_CACHE.clear()
        fetch = fake_fetch({
            "https://example.com/img/hero.png": (200, "image/png", png(1600)),
            "https://example.com/cover.png": (200, "image/png", png(2000)),
            "https://cdn.example.com/missing.png": 404,
            "https://developers.deepgram.com/docs/x": 200,
            "https://github.com/o/r": 200,
        })
        text = PAGE % ("https://example.com/cover.png", '<meta name="twitter:image" content="/cover.png">')
        found = messages(ll.check_page(text, "https://example.com/blog/post", OPTS._replace(fetch=fetch)))
        self.assertIn("image https://cdn.example.com/missing.png returned 404", found)
        self.assertIn("twitter:image must be an absolute https URL, got /cover.png", found)
        self.assertTrue(any(m.startswith("owned link missing") and "developers.deepgram.com" in m for m in found))
        self.assertFalse(any("hero.png" in m for m in found))
        self.assertFalse(any("github.com" in m for m in found))

    def test_missing_cards_are_found(self):
        fetch = fake_fetch({})
        text = "<html><head><title>t</title></head><body></body></html>"
        self.assertEqual(messages(ll.check_page(text, "https://example.com/p", OPTS._replace(fetch=fetch))),
                         ["no og:image meta tag", "no twitter:image meta tag"])

    def test_check_url_reports_a_page_that_does_not_load(self):
        fetch = fake_fetch({"https://example.com/p": 500})
        found = ll.check_url("https://example.com/p", OPTS._replace(fetch=fetch))
        self.assertEqual([f.message for f in found], ["page returned 500"])


SCRIPT_MD = """# Demo video

## What it is
Say a line, hear it back.

## How it works
One websocket.

## Why you'd use it
Because.

## Next steps
Fork it. Sign up: https://console.deepgram.com/signup?utm_source=youtube&utm_medium=video&utm_campaign=demo&utm_content=sam_gutentag_video
"""


class TestBeats(unittest.TestCase):
    def test_markdown_headings_cover_the_four_beats_in_order(self):
        found, missing, in_order = ll.beat_coverage(ll.beat_names(SCRIPT_MD, ".md"))
        self.assertEqual(missing, [])
        self.assertTrue(in_order)
        self.assertEqual(list(found), [b for b, _ in ll.BEATS])

    def test_synonyms_match_case_insensitively(self):
        names = [(0, "The Demo"), (1, "Under the Hood"), (2, "The problem"), (3, "Ideas")]
        self.assertEqual(ll.beat_coverage(names)[1], [])
        names = [(0, "WHAT WE BUILT"), (1, "Architecture"), (2, "When to use"), (3, "Extending it")]
        self.assertEqual(ll.beat_coverage(names)[1], [])

    def test_missing_and_out_of_order_beats(self):
        names = [(0, "How it works"), (1, "What this is"), (2, "Why")]
        found, missing, in_order = ll.beat_coverage(names)
        self.assertEqual(missing, ["examples for expansion"])
        self.assertFalse(in_order)

    def test_json_beats_give_their_directions_and_titles(self):
        data = {"take": {"title": "What it is", "beats": [
            ["How it works, diagram on screen", "One websocket."],
            {"dir": "Why: the problem, to camera", "text": "Because."},
            ["Next steps card", "Fork it."]]}}
        found, missing, in_order = ll.beat_coverage(ll.beat_names(json.dumps(data), ".json"))
        self.assertEqual(missing, [])
        self.assertTrue(in_order)

    def test_python_beats_module_gives_its_strings(self):
        text = ('CUTS = [("A", "the demo", "sub", [beat("How it works"), beat("Why bother"), '
                'beat("What else you could build")])]')
        self.assertEqual(ll.beat_coverage(ll.beat_names(text, ".py"))[1], [])

    def test_storyboard_table_cells_and_bold_labels_are_beat_names(self):
        text = ("**What it is:** a maze you steer by voice.\n\n## Storyboard\n\n"
                "| # | Time | Scene | On screen |\n|---|---|---|---|\n"
                "| 1 | 0-4 | Under the hood | A long caption that says why, which is prose |\n"
                "| 2 | 4-8 | Why bother | More |\n| 3 | 8-12 | What else | More |\n")
        found, missing, in_order = ll.beat_coverage(ll.beat_names(text, ".md"))
        self.assertEqual(missing, [])
        self.assertTrue(in_order)

    def test_plain_text_has_no_beats(self):
        self.assertEqual(ll.beat_names("Why you would want this. The demo.", ".txt"), [])


class TestCta(unittest.TestCase):
    def test_a_tagged_console_signup_passes(self):
        self.assertEqual(ll.cta_findings(SCRIPT_MD, "demo", "sam_gutentag"), [])
        self.assertEqual(ll.cta_findings(SCRIPT_MD.replace("utm_campaign=demo", "utm_campaign=demo"),
                                         "demo-lab"[:-4], "sam_gutentag"), [])

    def test_hyphen_and_underscore_slugs_are_the_same_campaign(self):
        text = SCRIPT_MD.replace("utm_campaign=demo", "utm_campaign=hn_radio")
        self.assertEqual(ll.cta_findings(text, "hn-radio", "sam_gutentag"), [])

    def test_a_missing_cta_is_found(self):
        self.assertEqual(ll.cta_findings("no links here", "demo", "sam_gutentag"),
                         ["console CTA missing: no console.deepgram.com link"])

    def test_an_untagged_cta_names_each_problem(self):
        text = "Sign up: https://console.deepgram.com/?utm_source=x&utm_medium=social&utm_campaign=other"
        found = ll.cta_findings(text, "demo", "sam_gutentag")
        self.assertEqual(len(found), 1)
        for part in ("points at /, the signup is /signup", "utm_medium is 'social', want video",
                     "utm_campaign is 'other', want demo", "utm_content is '', want sam_gutentag_video"):
            self.assertIn(part, found[0])

    def test_the_configured_signup_url_is_honored(self):
        text = "https://console.example.com/join?utm_source=x&utm_medium=video&utm_campaign=demo&utm_content=jane_video"
        self.assertEqual(ll.cta_findings(text, "demo", "jane", "https://console.example.com/join"), [])


class TestVideoProject(unittest.TestCase):
    def test_a_repo_with_both_videos_and_full_scripts_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "demo-lab"
            (repo / "advocacy").mkdir(parents=True)
            (repo / "brag-output").mkdir()
            (repo / "brag-output" / "brag.mp4").write_bytes(b"\x00")
            (repo / "brag-output" / "brag-plan.md").write_text(SCRIPT_MD)
            (repo / "video").mkdir()
            (repo / "video" / "remotion.config.ts").write_text("export {}")
            (repo / "video" / "out").mkdir()
            (repo / "video" / "out" / "demo.mp4").write_bytes(b"\x00")
            (repo / "video" / "SCRIPT.md").write_text(SCRIPT_MD)
            findings, notes = ll.check_video(repo, OPTS)
            self.assertEqual(findings, [])
            self.assertEqual(notes, [])

    def test_missing_videos_beats_and_cta_are_each_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "demo-lab"
            (repo / "advocacy").mkdir(parents=True)
            findings, _ = ll.check_video(repo, OPTS)
            self.assertEqual(findings, [
                "missing brag video (brag-output*/brag*.mp4)",
                "missing Remotion video (no remotion.config.*, no render under video/ or renders/)"])
            (repo / "brag-output").mkdir()
            (repo / "brag-output" / "brag.mp4").write_bytes(b"\x00")
            (repo / "brag-output" / "brag-plan.md").write_text("# Plan\n\n## What it is\n\n## How it works\n")
            (repo / "brag-output" / "brag-v2.mp4").write_bytes(b"\x00")
            (repo / "renders").mkdir()
            (repo / "renders" / "take.mp4").write_bytes(b"\x00")
            (repo / "episodes").mkdir()
            (repo / "episodes" / "script.json").write_text(json.dumps({"beats": [["Why you'd use it", "x"]]}))
            findings, _ = ll.check_video(repo, OPTS)
            self.assertEqual(len([m for m in findings if m.startswith("brag: beats missing")]), 1)
            self.assertFalse(any("episodes/script.json" in m for m in findings))
            self.assertTrue(any(m.startswith("brag: beats missing in brag-output/brag-plan.md: why you'd use it, examples for expansion") for m in findings))
            self.assertIn("brag: console CTA missing: no console.deepgram.com link", findings)
            self.assertTrue(any(m.startswith("remotion: no script or beat file") for m in findings))

    def test_a_remotion_project_without_a_render_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "demo-lab"
            (repo / ".claude" / "worktrees" / "remotion" / "video").mkdir(parents=True)
            (repo / ".claude" / "worktrees" / "remotion" / "video" / "package.json").write_text(
                '{"dependencies": {"remotion": "4.0.0"}}')
            found = ll.find_videos(repo)
            self.assertEqual(len(found["remotion"]), 1)
            self.assertIsNone(found["remotion"][0][0])
            findings, _ = ll.check_video(repo, OPTS)
            self.assertTrue(any("has no render" in m for m in findings))

    def test_frame_size_rule(self):
        self.assertTrue(ll.frame_ok(1920, 1080))
        self.assertTrue(ll.frame_ok(1080, 1920))
        self.assertTrue(ll.frame_ok(3840, 2160))
        self.assertFalse(ll.frame_ok(1280, 720))
        self.assertFalse(ll.frame_ok(1080, 1080))


class TestFiles(unittest.TestCase):
    def test_kinds_follow_the_file_name(self):
        self.assertEqual(ll.kind_of("https://example.com/p"), "url")
        self.assertEqual(ll.kind_of("site/post.html"), "html")
        self.assertEqual(ll.kind_of("advocacy/notes.md"), "notes")
        self.assertEqual(ll.kind_of("advocacy/content/drips/2026-10-01-x.md"), "drip")
        self.assertEqual(ll.kind_of("advocacy/content/social.md"), "social")
        self.assertEqual(ll.kind_of("advocacy/content/blog-base.md"), "prose")
        self.assertEqual(ll.kind_of("advocacy/content/archetype-takes.md"), "takes")
        self.assertEqual(ll.kind_of("brag-output/brag.mp4"), "video")

    def test_takes_and_notes_skip_the_utm_and_length_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._project(pathlib.Path(tmp))
            takes = repo / "advocacy" / "content" / "archetype-takes.md"
            takes.write_text(FM + "# Takes\n\n### X\n\n" + "lorem " * 60
                             + "— 42 [docs](https://developers.deepgram.com/docs/x)\n")
            found = ll.check_file(takes, ll.kind_of(takes), OPTS._replace(net=False))
            self.assertEqual([f.message for f in found],
                             ["em dash", "number 42 not in notes.md"])
            notes = repo / "advocacy" / "notes.md"
            notes.write_text(NOTES + "\nSource: https://developers.deepgram.com/docs/x\n")
            found = ll.check_file(notes, ll.kind_of(notes), OPTS._replace(net=False))
            self.assertEqual([f.message for f in found], [])

    def _project(self, root):
        repo = root / "demo-lab"
        (repo / "advocacy" / "content" / "drips").mkdir(parents=True)
        (repo / "advocacy" / "assets").mkdir()
        (repo / "advocacy" / "notes.md").write_text(NOTES)
        (repo / "advocacy" / "assets" / "hero.png").write_bytes(png(1600))
        (repo / "advocacy" / "content" / "blog-base.md").write_text(
            FM + "# Post\n\nMedian 350 ms. The 42 thing — yes.\n\n![hero](../assets/hero.png)\n\n"
            "[docs](https://developers.deepgram.com/docs/x) and [repo](https://github.com/o/r)\n")
        return repo

    def test_check_file_finds_notes_and_assets_relative_to_the_file(self):
        ll._URL_CACHE.clear()
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._project(pathlib.Path(tmp))
            fetch = fake_fetch({"https://developers.deepgram.com/docs/x": 200, "https://github.com/o/r": 404})
            found = ll.check_file(repo / "advocacy" / "content" / "blog-base.md", "prose", OPTS._replace(fetch=fetch))
            lines = [ll.format_finding(f, base=repo) for f in found]
            self.assertEqual(lines, [
                "advocacy/content/blog-base.md:10: em dash",
                "advocacy/content/blog-base.md:10: number 42 not in notes.md",
                "advocacy/content/blog-base.md:14: owned link missing utm_source, utm_medium, utm_campaign, utm_content: https://developers.deepgram.com/docs/x",
                "advocacy/content/blog-base.md:14: URL does not resolve: https://github.com/o/r"])

    def test_the_notes_override_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._project(pathlib.Path(tmp))
            other = pathlib.Path(tmp) / "other-notes.md"
            other.write_text("42 and 350")
            found = ll.check_file(repo / "advocacy" / "content" / "blog-base.md", "prose",
                                  OPTS._replace(net=False, notes=str(other)))
            self.assertFalse(any("number" in f.message for f in found))

    def test_main_prints_findings_a_verdict_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._project(pathlib.Path(tmp))
            cfg = pathlib.Path(tmp) / "cfg.yml"
            cfg.write_text('voice_personal: "sam-style"\nutm_domains: "deepgram.com"\nperson_slug: "sam_gutentag"\n')
            clean = repo / "advocacy" / "content" / "archetype-takes.md"
            clean.write_text(FM + "# Takes\n\nMedian 350 ms.\n")
            out = io.StringIO()
            cwd = os.getcwd()
            os.chdir(repo)
            try:
                with contextlib.redirect_stdout(out):
                    code = ll.main(["advocacy/content/blog-base.md", str(clean), "--no-net", "--no-video",
                                    "--config", str(cfg)])
            finally:
                os.chdir(cwd)
            self.assertEqual(code, 1)
            text = out.getvalue()
            self.assertIn("advocacy/content/blog-base.md:10: em dash\n", text)
            self.assertIn("advocacy/content/blog-base.md: 3 findings, not ship-ready\n", text)
            self.assertIn("advocacy/content/archetype-takes.md: ship-ready\n", text)
            self.assertTrue(text.rstrip().endswith("3 findings in 2 files"))

    def test_video_findings_are_reminders_for_prose_and_block_a_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._project(pathlib.Path(tmp))
            cfg = pathlib.Path(tmp) / "cfg.yml"
            cfg.write_text('voice_personal: "sam-style"\nutm_domains: "deepgram.com"\n')
            clean = repo / "advocacy" / "content" / "archetype-takes.md"
            clean.write_text(FM + "# Takes\n\nMedian 350 ms.\n")
            (repo / "brag-output").mkdir()
            mp4 = repo / "brag-output" / "brag.mp4"
            mp4.write_bytes(b"\x00")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ll.main([str(clean), "--no-net", "--config", str(cfg)])
            self.assertEqual(code, 0)
            self.assertIn("video reminders (demo): missing Remotion video", out.getvalue())
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ll.main([str(mp4), "--no-net", "--config", str(cfg)])
            self.assertEqual(code, 1)
            self.assertIn("video (demo): missing Remotion video", out.getvalue())
            self.assertIn("not ship-ready", out.getvalue())


if __name__ == "__main__":
    unittest.main()
