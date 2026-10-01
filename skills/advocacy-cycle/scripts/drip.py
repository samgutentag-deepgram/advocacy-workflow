"""Drip: six dated social posts for one shipped piece, one per developer archetype.

A blog or a video goes live, and over the following weeks six posts point
back at it, each written for a different developer: the one who has never
heard of it, the one measuring, the one building, the one running it at
volume, the one carrying it into a team, and the one on an adjacent platform.
`social.md` is the undated pool that runs between pieces and `x-series.md` is
the series an X Article gets. A drip is the per-piece trigger, with a calendar
date on every post and a permalink once it is live.

The deterministic parts live here: dates, limits, hook reuse, number tracing,
the file format, the published log. The prose is the model's and goes through
the configured voice skill and de-slop before `check`.

    drip.py scaffold --repo . --piece <url> --type blog [--title ...] [--start YYYY-MM-DD]
    drip.py check advocacy/content/drips/<file>.md
    drip.py post  advocacy/content/drips/<file>.md 3 https://x.com/.../status/...

Stdlib only. The machine yml is read with advocacy-intake's config parser,
the X billing rule and beat detection come from cycle_core, and UTM tagging
comes from x-article's utm.py, so none of those rules exist twice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
import textwrap
from collections import namedtuple
from urllib.parse import urlparse

HERE = pathlib.Path(__file__).resolve().parent
_SKILLS = HERE.parent.parent
for _path in (HERE,
              _SKILLS / "advocacy-intake" / "scripts",
              _SKILLS / "x-article" / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import config as machine_config  # noqa: E402  advocacy-intake's yml reader
from cycle_core import (  # noqa: E402
    _FRONTMATTER, X_URL_BILLED_CHARS, Finding, billed_length, open_beats,
    parse_frontmatter, post_body, split_posts,
)
from utm import owned, tag_url  # noqa: E402  x-article's link tagging

# Fixed order. Section n of every drip is archetype n, so the calendar and
# the check can address a post by number without reading the heading.
ARCHETYPES = ("Curious dev", "Explorer", "Builder", "Scaler", "Champion",
              "Partner dev")

PLATFORMS = ("x", "linkedin")

DEFAULT_PLATFORM = {
    "Curious dev": "x",
    "Explorer": "x",
    "Builder": "x",
    "Scaler": "linkedin",
    "Champion": "x",
    "Partner dev": "linkedin",
}

# What each post has to do. Written into the beat so the model writing it
# sees the reader, not just the slot.
ARCHETYPE_JOB = {
    "Curious dev": (
        "A developer who has never heard of this. The wow moment in one "
        "breath: what it is and why it matters, no setup, no term they would "
        "have to look up."),
    "Explorer": (
        "A developer poking at the space. The measured number, how it was "
        "measured, and what the measurement does not cover. Honest about the "
        "edge."),
    "Builder": (
        "A developer who wants to build it too. The copyable pattern: the "
        "config, the rules, the one file. They should be able to start "
        "inside a minute."),
    "Scaler": (
        "A developer running this at volume. Cost, latency under load, spend "
        "controls, where it breaks. Numbers over adjectives."),
    "Champion": (
        "A developer carrying this into their team. The argument they can "
        "forward as is, and the invitation to fork it, extend it, or run it "
        "on their own data."),
    "Partner dev": (
        "A developer on an adjacent platform. Where this touches their "
        "stack, what the integration point is, and what their users gain. "
        "Claim only the integrations notes.md names."),
}

X_LIMIT = 280
LINKEDIN_MIN = 600
LINKEDIN_MAX = 1500
LINKEDIN_MAX_HASHTAGS = 3

# A hook is the first six words of a post. Two posts that open the same way
# read as the same post to a timeline, whatever follows.
HOOK_WORDS = 6

POST_TIME = "09:00 America/Los_Angeles"
POST_WEEKDAYS = (1, 2, 3)           # Tuesday to Thursday, Monday is 0
POSTS_PER_WEEK = 2                  # Tuesday and Thursday; Wednesday fills a gap
MIN_LEAD_DAYS = 5                   # the first Tuesday at least this far out
MAX_WEEKS = 26                      # give up rather than schedule into next year

REQUIRED_KEYS = ("project", "surface", "piece", "piece_type", "piece_title",
                 "created", "sources", "passes")
PIECE_TYPES = ("blog", "video")
META_KEYS = ("date", "platform", "link", "asset", "fact", "published")

DRIPS_DIR = pathlib.PurePosixPath("advocacy", "content", "drips")
PUBLISHED_LOG = pathlib.PurePosixPath("advocacy", "content", "published.log")
NOTES = pathlib.PurePosixPath("advocacy", "notes.md")

# Where hooks and dates already live in a project. social.md is undated and
# only contributes hooks; the series files contribute both.
HOOK_SOURCES = ("advocacy/content/social.md", "advocacy/content/x-series.md",
                "_docs/x-series.md")
DATED_SOURCES = ("advocacy/content/x-series.md", "_docs/x-series.md")

_SECTION = re.compile(r"^## (\d+)\. (.+?)[ \t]*$", re.MULTILINE)
_FENCE = re.compile(r"^```[^\n]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)
_META = re.compile(r"^(%s):[ \t]*(.*)$" % "|".join(META_KEYS), re.MULTILINE)
_DATE_LINE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) ([A-Za-z_]+/[A-Za-z_+-]+)$")
_URL = re.compile(r"https?://\S+")
_HASHTAG = re.compile(r"(?<!\w)#\w+")
_EM_DASH = "—"

# A number as a post writes it: 350, 4.55, 6,153, 9:00, 0.00016. The token
# has to appear in notes.md spelled exactly this way, which is the whole
# point: "6153" is not "6,153" and a rounded figure is a new claim.
_NUMBER = re.compile(r"(?<![\w.,:])\d+(?:[.,:]\d+)*")

# Best-effort dates in a series file, which has no strict format: an ISO
# date at the start of a line or after `date:`, or a weekday-month-day the
# way the first real series wrote them ("Thu Oct 1, 9:00 AM PT"). The year
# for the latter is the one the file's own ISO dates use.
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_LOOSE_DATE_LINE = re.compile(r"^[#\-*|\d. \t]*(\d{4}-\d{2}-\d{2})(?![\w-])",
                              re.MULTILINE)
_DATE_KEY = re.compile(r"\bdate:\s*(\d{4}-\d{2}-\d{2})(?![\w-])", re.IGNORECASE)
_MONTH_DAY = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s+"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b")
_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"), 1)}

_TRIM = "\"'“”‘’.,:;!?()[]{}<>*_`"


# --------------------------------------------------------------------------
# The file
# --------------------------------------------------------------------------

Section = namedtuple("Section", "n archetype meta text beats start end")


def parse_sections(text):
    """The numbered sections of a drip, in file order.

    Each carries its metadata lines, the text of its first fence (empty when
    the post is unwritten), the beats still open in it, and its character
    span so a caller can rewrite one line in place.
    """
    fm = _FRONTMATTER.match(text)
    heads = list(_SECTION.finditer(text, fm.end() if fm else 0))
    out = []
    for i, head in enumerate(heads):
        start = head.start()
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        chunk = text[head.end():end]
        fence = _FENCE.search(chunk)
        post = fence.group(1).strip() if fence else ""
        outside = _FENCE.sub("", chunk)
        meta = {m.group(1): m.group(2).strip() for m in _META.finditer(outside)}
        out.append(Section(int(head.group(1)), head.group(2).strip(), meta,
                           post, open_beats(outside), start, end))
    return out


def post_date(value):
    """The date of a strict `date:` value, or None if it is not one."""
    match = _DATE_LINE.match((value or "").strip())
    if not match:
        return None
    try:
        dt.time.fromisoformat(match.group(2))
        return dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None


def slugify(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


_VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "loom.com")


def slug_for(piece_url, title=None, max_words=8):
    """A filename slug from the URL path when it has one, else from the title.

    A blog URL's last segment already is a slug, minus any leading date. A
    video URL carries an opaque id instead, so the title has to supply it,
    and with neither the call is refused rather than guessed.
    """
    host = urlparse(piece_url).netloc.lower()
    if not any(host == h or host.endswith("." + h) for h in _VIDEO_HOSTS):
        last = urlparse(piece_url).path.rstrip("/").rsplit("/", 1)[-1]
        last = re.sub(r"\.(html?|md)$", "", last)
        last = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", last)
        slug = slugify(last)
        if len(slug) >= 3 and slug not in ("watch", "index", "status", "shorts", "embed"):
            return slug
    if title and slugify(title):
        return "-".join(slugify(title).split("-")[:max_words])
    raise ValueError("could not derive a slug from %s; pass --title" % piece_url)


def on_x(url):
    host = urlparse(url).netloc.lower()
    return host in ("x.com", "www.x.com", "twitter.com", "www.twitter.com")


def link_line(piece_url, platform, campaign, config_values):
    """The `link:` value for one platform.

    Owned domains get x-article's UTM scheme: the platform in utm_source, the
    person and placement in utm_content, one campaign slug per piece. Other
    hosts stay untagged. On X the link goes in the first reply unless the
    piece itself is on X; LinkedIn takes it in the body.
    """
    cfg = config_values or {}
    url = piece_url
    domains = [d.strip().lower() for d in (cfg.get("utm_domains") or "").split(",")
               if d.strip()]
    if domains and owned(url, domains):
        person = (cfg.get("person_slug") or "").strip()
        url = tag_url(url, {
            "utm_source": platform,
            "utm_medium": "social",
            "utm_campaign": campaign,
            "utm_content": "%s_post" % person if person else "post",
        })
    where = "body" if platform == "linkedin" or on_x(piece_url) else "reply"
    return "%s (%s)" % (url, where)


def _platform_note(platform):
    if platform == "x":
        return ("Platform: X. %d characters with every URL billed at %d. "
                "The link goes where link: says, and (reply) means not in "
                "the body." % (X_LIMIT, X_URL_BILLED_CHARS))
    return ("Platform: LinkedIn. %d to %s characters, at most %d hashtags, "
            "the first line is the hook." % (LINKEDIN_MIN, format(LINKEDIN_MAX, ","),
                                             LINKEDIN_MAX_HASHTAGS))


def render_beat(archetype, platform, hooks):
    """The HTML-comment beat that stands in for an unwritten post.

    Same shape as the blog beats so `open_beats` finds it: a name, a rule of
    dots, a budget, then the job. The hooks already used in the project are
    listed so the model writing the post sees what to avoid.
    """
    name = archetype.upper()
    budget = ("x, %d chars" % X_LIMIT if platform == "x"
              else "linkedin, %d-%d chars" % (LINKEDIN_MIN, LINKEDIN_MAX))
    lines = ["<!-- %s %s %s" % (name, "." * max(3, 52 - len(name)), budget)]
    wrap = lambda s: textwrap.wrap(s, 72, initial_indent="     ",  # noqa: E731
                                   subsequent_indent="     ")
    lines += wrap("Job: %s" % ARCHETYPE_JOB[archetype])
    lines += wrap(_platform_note(platform))
    lines += wrap("Facts: advocacy/notes.md only. Every number in the post "
                  "is a literal token there.")
    lines += wrap("Hooks already used in this project (first six words; "
                  "use none of them):")
    if hooks:
        width = max(len(label) for label in hooks.values())
        for words, label in hooks.items():
            lines.append("       %-*s  %s" % (width, label, " ".join(words)))
    else:
        lines.append("       (none yet)")
    lines += wrap("Write the post in the fence below, run the voice skill "
                  "and de-slop, then drip.py check, then delete this comment.")
    lines.append("-->")
    return "\n".join(lines)


def render_drip(frontmatter, dates_by_archetype, link_by_platform, hooks,
                platforms=None):
    """The whole scaffold. Strict format, because the calendar parses it."""
    fm = frontmatter
    lines = [
        "---",
        "project: %s" % fm["project"],
        "surface: drip",
        "piece: %s" % fm["piece"],
        "piece_type: %s" % fm["piece_type"],
        "piece_title: %s" % fm["piece_title"],
        "created: %s" % fm["created"],
        "sources: [advocacy/notes.md]",
        "passes: [%s, de-slop]" % fm.get("voice", "personal-style"),
        "---",
        "",
    ]
    platforms = platforms or DEFAULT_PLATFORM
    for n, archetype in enumerate(ARCHETYPES, 1):
        platform = platforms[archetype]
        lines += [
            "## %d. %s" % (n, archetype),
            "date: %s %s" % (dates_by_archetype[archetype].isoformat(), POST_TIME),
            "platform: %s" % platform,
            "link: %s" % link_by_platform[platform],
            "asset: needs: an image or clip for this post",
            "fact: needs: one fact from notes.md, as notes.md \"Heading\" (the fact)",
            "published:",
            "",
            render_beat(archetype, platform, hooks),
            "",
            "```text",
            "```",
            "",
        ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

def parse_blackouts(value):
    """`launch_blackouts` from the yml as a set of dates."""
    out = set()
    for raw in (value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.add(dt.date.fromisoformat(raw))
        except ValueError:
            raise ValueError(
                "launch_blackouts has %r, which is not YYYY-MM-DD" % raw)
    return out


def first_tuesday(on_or_after):
    day = on_or_after
    while day.weekday() != 1:
        day += dt.timedelta(days=1)
    return day


def default_start(published_on):
    """The first Tuesday at least MIN_LEAD_DAYS after the piece went live."""
    return first_tuesday(published_on + dt.timedelta(days=MIN_LEAD_DAYS))


def drip_dates(first_tue, blocked, count=len(ARCHETYPES),
               per_week=POSTS_PER_WEEK, max_weeks=MAX_WEEKS):
    """Posting dates, two a week, Tuesday and Thursday, skipping `blocked`.

    Wednesday fills in when one of the two is blocked. A week with one free
    day gets one post and the drip runs a week longer; a week with none is
    skipped. Blackouts and dates another post already holds arrive as one
    set because the rule is the same for both: never land on them.
    """
    if first_tue.weekday() != 1:
        raise ValueError("a drip starts on a Tuesday; %s is a %s"
                         % (first_tue, first_tue.strftime("%A")))
    out, week = [], first_tue
    for _ in range(max_weeks):
        if len(out) >= count:
            break
        tue, wed, thu = (week + dt.timedelta(days=i) for i in range(3))
        free = [d for d in (tue, thu, wed) if d not in blocked]
        out.extend(sorted(free[:per_week]))
        week += dt.timedelta(days=7)
    if len(out) < count:
        raise ValueError("could not place %d posts in %d weeks from %s"
                         % (count, max_weeks, first_tue))
    return out[:count]


def dates_in(text, year=None):
    """Every date a loosely formatted series file holds. Best effort."""
    body = _FRONTMATTER.sub("", text)
    found = set()
    for pattern in (_LOOSE_DATE_LINE, _DATE_KEY):
        for match in pattern.finditer(body):
            try:
                found.add(dt.date.fromisoformat(match.group(1)))
            except ValueError:
                continue
    if year is None:
        years = [int(m.group(0)[:4]) for m in _ISO.finditer(text)]
        year = (max(set(years), key=years.count) if years
                else dt.date.today().year)
    for match in _MONTH_DAY.finditer(body):
        try:
            found.add(dt.date(year, _MONTHS[match.group(1)], int(match.group(2))))
        except ValueError:
            continue
    return found


# --------------------------------------------------------------------------
# Hooks and numbers
# --------------------------------------------------------------------------

def hook(post, n=HOOK_WORDS):
    """The first `n` words of a post, lowercased and stripped of punctuation."""
    words = []
    for raw in post.split():
        word = raw.strip(_TRIM).lower()
        if word:
            words.append(word)
        if len(words) == n:
            break
    return tuple(words)


def posts_in(text):
    """The posts in any content file: its fenced blocks, or failing that
    the numbered or dash-separated posts cycle_core knows how to split."""
    body = _FRONTMATTER.sub("", text)
    fenced = [m.group(1).strip() for m in _FENCE.finditer(body) if m.group(1).strip()]
    if fenced:
        return fenced
    return [post_body(p) for p in split_posts(text) if post_body(p)]


def hooks_in(text):
    return [h for h in (hook(p) for p in posts_in(text)) if h]


def used_hooks(sources):
    """hook -> the label of the first file using it, over (label, text) pairs."""
    out = {}
    for label, text in sources:
        for h in hooks_in(text):
            out.setdefault(h, label)
    return out


def live_notes(notes_text):
    """notes.md with its Superseded sections removed.

    x-article moves replaced figures under a dated `## Superseded` heading so
    no lint can pass them again. Honoring that here is what makes the rule
    hold: a number that was true in August is not a token a post may use.
    """
    out, skipping = [], None
    for line in notes_text.split("\n"):
        head = re.match(r"^(#{1,6})\s+(.*)$", line)
        if head:
            level = len(head.group(1))
            if skipping is not None and level <= skipping:
                skipping = None
            if skipping is None and head.group(2).strip().lower().startswith("superseded"):
                skipping = level
                continue
        if skipping is None:
            out.append(line)
    return "\n".join(out)


def numbers_in(text):
    """Every number token in a text, URLs removed first."""
    return [m.group(0) for m in _NUMBER.finditer(_URL.sub(" ", text))]


def untraced_numbers(post, notes_text):
    """Numbers in the post that notes.md does not hold as the same token."""
    allowed = set(numbers_in(live_notes(notes_text)))
    seen, out = set(), []
    for token in numbers_in(post):
        if token not in allowed and token not in seen:
            out.append(token)
            seen.add(token)
    return out


# --------------------------------------------------------------------------
# Check
# --------------------------------------------------------------------------

Context = namedtuple("Context", "notes blackouts taken hooks")


def check_drip(text, ctx):
    """Every finding on one drip file. An empty list is a pass.

    Unwritten posts get their metadata checked and nothing else, because a
    scaffold is allowed to be a scaffold. A written post gets the platform
    limits, the number trace, the hook rule, the em dash rule, and the open
    beat rule.
    """
    findings = []
    fm = parse_frontmatter(text)
    for key in REQUIRED_KEYS:
        if key not in fm:
            findings.append(Finding("frontmatter", "missing %s" % key))
    if "surface" in fm and fm["surface"] != "drip":
        findings.append(Finding("frontmatter", "surface is %r, not drip" % fm["surface"]))
    if "piece_type" in fm and fm["piece_type"] not in PIECE_TYPES:
        findings.append(Finding("frontmatter", "piece_type %r, expected %s"
                                % (fm["piece_type"], " or ".join(PIECE_TYPES))))
    if "created" in fm and not isinstance(fm["created"], list):
        try:
            dt.date.fromisoformat(fm["created"])
        except ValueError:
            findings.append(Finding("frontmatter", "created %r is not a date" % fm["created"]))

    sections = parse_sections(text)
    if len(sections) != len(ARCHETYPES):
        findings.append(Finding("sections", "%d sections, expected %d, one per archetype"
                                % (len(sections), len(ARCHETYPES))))
    for i, section in enumerate(sections, 1):
        expected = ARCHETYPES[i - 1] if i <= len(ARCHETYPES) else None
        if section.n != i or section.archetype != expected:
            findings.append(Finding(
                "section %d" % i, "heading is '%d. %s', expected '%d. %s'"
                % (section.n, section.archetype, i, expected)))

    dates_seen, own_hooks = {}, {}
    for section in sections:
        where = "post %d (%s)" % (section.n, section.archetype)
        raw = section.meta.get("date")
        day = post_date(raw)
        if raw is None:
            findings.append(Finding(where, "no date line"))
        elif day is None:
            findings.append(Finding(where, "date %r is not 'YYYY-MM-DD HH:MM Area/City'" % raw))
        else:
            if day.weekday() not in POST_WEEKDAYS:
                findings.append(Finding(where, "%s is a %s; posts run Tuesday to Thursday"
                                        % (day, day.strftime("%A"))))
            if day in ctx.blackouts:
                findings.append(Finding(where, "%s is a launch blackout" % day))
            if day in ctx.taken:
                findings.append(Finding(where, "%s is already held by %s" % (day, ctx.taken[day])))
            if day in dates_seen:
                findings.append(Finding(where, "%s is also post %d's date" % (day, dates_seen[day])))
            dates_seen.setdefault(day, section.n)

        platform = section.meta.get("platform", "")
        if platform not in PLATFORMS:
            findings.append(Finding(where, "platform %r, expected x or linkedin" % platform))
        link = section.meta.get("link")
        if link is None:
            findings.append(Finding(where, "no link line"))
        elif not re.search(r"\((body|reply)\)$", link):
            findings.append(Finding(where, "link must end with (body) or (reply)"))
        for key in ("asset", "fact", "published"):
            if key not in section.meta:
                findings.append(Finding(where, "no %s line" % key))

        if not section.text:
            if section.meta.get("published"):
                findings.append(Finding(where, "published but the post is empty"))
            continue
        findings += _check_written(section, where, platform, link or "", ctx, own_hooks)
    return findings


def _check_written(section, where, platform, link, ctx, own_hooks):
    findings = []
    post = section.text
    if section.beats:
        findings.append(Finding(where, "written but still carries the beat: %s"
                                % ", ".join(section.beats)))
    if section.meta.get("fact", "").startswith("needs:"):
        findings.append(Finding(where, "fact line is still the placeholder"))
    if _EM_DASH in post:
        findings.append(Finding(where, "em dash"))
    if platform == "x":
        length = billed_length(post)
        if length > X_LIMIT:
            findings.append(Finding(where, "%d chars billed, limit is %d" % (length, X_LIMIT)))
        if _URL.search(post) and link.endswith("(reply)"):
            findings.append(Finding(where, "URL in the body but link says (reply)"))
    elif platform == "linkedin":
        length = len(post)
        if length < LINKEDIN_MIN:
            findings.append(Finding(where, "%d chars, LinkedIn wants at least %d"
                                    % (length, LINKEDIN_MIN)))
        if length > LINKEDIN_MAX:
            findings.append(Finding(where, "%d chars, LinkedIn limit is %d"
                                    % (length, LINKEDIN_MAX)))
        tags = len(_HASHTAG.findall(post))
        if tags > LINKEDIN_MAX_HASHTAGS:
            findings.append(Finding(where, "%d hashtags, max is %d" % (tags, LINKEDIN_MAX_HASHTAGS)))
    for token in untraced_numbers(post, ctx.notes):
        findings.append(Finding(where, "%s is not a literal token in notes.md" % token))
    h = hook(post)
    if h in ctx.hooks:
        findings.append(Finding(where, "hook '%s' already used in %s"
                                % (" ".join(h), ctx.hooks[h])))
    if h in own_hooks:
        findings.append(Finding(where, "hook '%s' is also post %d's"
                                % (" ".join(h), own_hooks[h])))
    own_hooks.setdefault(h, section.n)
    return findings


def mark_published(text, n, permalink):
    """The file with `published: <permalink>` written on post `n`.

    Refuses a post that is unwritten or already published. Returns the new
    text and the section, so the caller can log the platform.
    """
    if not permalink.startswith(("http://", "https://")):
        raise ValueError("permalink %r is not a URL" % permalink)
    matches = [s for s in parse_sections(text) if s.n == n]
    if not matches:
        raise ValueError("no post %d in the file" % n)
    section = matches[0]
    if not section.text:
        raise ValueError("post %d is not written yet" % n)
    if section.meta.get("published"):
        raise ValueError("post %d is already published: %s"
                         % (n, section.meta["published"]))
    chunk = text[section.start:section.end]
    fence = _FENCE.search(chunk)
    head = chunk[:fence.start()] if fence else chunk
    match = re.search(r"^published:[ \t]*$", head, re.MULTILINE)
    if not match:
        raise ValueError("post %d has no empty published: line" % n)
    chunk = chunk[:match.start()] + "published: %s" % permalink + chunk[match.end():]
    return text[:section.start] + chunk + text[section.end:], section


def log_line(on, platform, permalink, rel_path, n):
    return "%s %s %s %s#%d" % (on.isoformat(), platform, permalink, rel_path, n)


# --------------------------------------------------------------------------
# The repo. Everything below touches the filesystem.
# --------------------------------------------------------------------------

def _read(path):
    return pathlib.Path(path).read_text(errors="replace")


def hook_sources(repo, exclude=None):
    """(label, text) for every file whose hooks a new post may not reuse."""
    repo = pathlib.Path(repo)
    out = []
    for rel in HOOK_SOURCES:
        path = repo / rel
        if path.is_file():
            out.append((pathlib.PurePosixPath(rel).name if rel.startswith("advocacy/")
                        else rel, _read(path)))
    drips = repo / DRIPS_DIR
    if drips.is_dir():
        for path in sorted(drips.glob("*.md")):
            if exclude and path.resolve() == pathlib.Path(exclude).resolve():
                continue
            out.append(("drips/%s" % path.name, _read(path)))
    return out


def taken_dates(repo, exclude=None):
    """date -> label for every date another dated post in the project holds."""
    repo = pathlib.Path(repo)
    out = {}
    for rel in DATED_SOURCES:
        path = repo / rel
        if path.is_file():
            for day in dates_in(_read(path)):
                out.setdefault(day, rel)
    drips = repo / DRIPS_DIR
    if drips.is_dir():
        for path in sorted(drips.glob("*.md")):
            if exclude and path.resolve() == pathlib.Path(exclude).resolve():
                continue
            for section in parse_sections(_read(path)):
                day = post_date(section.meta.get("date"))
                if day:
                    out.setdefault(day, "drips/%s" % path.name)
    return out


def project_context(repo, drip_path=None, config_values=None):
    repo = pathlib.Path(repo)
    notes = repo / NOTES
    return Context(
        notes=_read(notes) if notes.is_file() else "",
        blackouts=parse_blackouts((config_values or {}).get("launch_blackouts")),
        taken=taken_dates(repo, exclude=drip_path),
        hooks=used_hooks(hook_sources(repo, exclude=drip_path)),
    )


def project_name(repo):
    name = pathlib.Path(repo).resolve().name
    return name[:-4] if name.endswith("-lab") else name


def repo_of(drip_path, override=None):
    """The repo a drip file belongs to, from its path unless told."""
    if override:
        return pathlib.Path(override).expanduser().resolve()
    path = pathlib.Path(drip_path).resolve()
    parents = path.parents
    if (len(parents) > 3 and parents[0].name == "drips"
            and parents[1].name == "content" and parents[2].name == "advocacy"):
        return parents[3]
    raise ValueError("%s is not under advocacy/content/drips/; pass --repo" % drip_path)


def parse_lead(value):
    if not value:
        return []
    by_lower = {a.lower(): a for a in ARCHETYPES}
    out = []
    for raw in value.split(","):
        name = by_lower.get(raw.strip().lower())
        if not name:
            raise ValueError("--lead %r is not one of %s" % (raw.strip(), ", ".join(ARCHETYPES)))
        if name not in out:
            out.append(name)
    if len(out) > 2:
        raise ValueError("--lead names at most two archetypes")
    return out


def _cfg(path_override):
    return machine_config.with_defaults(machine_config.load(path_override))


def cmd_scaffold(args):
    repo = pathlib.Path(args.repo).expanduser().resolve()
    if not (repo / "advocacy").is_dir():
        print("%s has no advocacy/ directory; run intake first" % repo, file=sys.stderr)
        return 2
    if not args.piece.startswith(("http://", "https://")):
        print("--piece %r is not a URL" % args.piece, file=sys.stderr)
        return 2
    cfg = _cfg(args.config)
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    start = (first_tuesday(dt.date.fromisoformat(args.start)) if args.start
             else default_start(today))
    slug = slug_for(args.piece, args.title)
    path = repo / DRIPS_DIR / ("%s-%s.md" % (today.isoformat(), slug))
    if path.exists():
        print("refusing to overwrite %s" % path, file=sys.stderr)
        return 1

    taken = taken_dates(repo)
    dates = drip_dates(start, parse_blackouts(cfg.get("launch_blackouts")) | set(taken))
    lead = parse_lead(args.lead)
    order = lead + [a for a in ARCHETYPES if a not in lead]
    dates_by = dict(zip(order, dates))
    campaign = slug.replace("-", "_")
    links = {p: link_line(args.piece, p, campaign, cfg) for p in PLATFORMS}
    text = render_drip(
        {"project": project_name(repo), "piece": args.piece,
         "piece_type": args.type,
         "piece_title": args.title or slug.replace("-", " "),
         "created": today.isoformat(),
         "voice": cfg.get("voice_personal") or "personal-style"},
        dates_by, links, used_hooks(hook_sources(repo)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(path.relative_to(repo).as_posix())
    for archetype in ARCHETYPES:
        print("  %-12s %s  %s" % (archetype, dates_by[archetype],
                                  DEFAULT_PLATFORM[archetype]))
    if taken:
        print("  skipped %d date(s) other posts hold" % len(taken))
    return 0


def _load(args):
    path = pathlib.Path(args.drip).expanduser().resolve()
    if not path.is_file():
        raise ValueError("no such file: %s" % args.drip)
    repo = repo_of(path, args.repo)
    ctx = project_context(repo, drip_path=path, config_values=_cfg(args.config))
    return path, repo, ctx


def _report(findings):
    for finding in findings:
        print("%s: %s" % (finding.where, finding.what))


def progress(sections):
    """(written, unwritten) sections. A scaffold is six unwritten posts and
    passes check; the summary is what keeps that from reading as done."""
    return ([s for s in sections if s.text], [s for s in sections if not s.text])


def cmd_check(args):
    path, repo, ctx = _load(args)
    text = _read(path)
    findings = check_drip(text, ctx)
    _report(findings)
    written, unwritten = progress(parse_sections(text))
    print("%s: %d written, %d unwritten"
          % (path.relative_to(repo).as_posix(), len(written), len(unwritten)))
    if unwritten:
        print("  unwritten: %s" % ", ".join(s.archetype for s in unwritten))
    return 1 if findings else 0


def cmd_post(args):
    path, repo, ctx = _load(args)
    text = _read(path)
    findings = check_drip(text, ctx)
    if findings:
        _report(findings)
        print("refusing: check fails", file=sys.stderr)
        return 1
    try:
        new_text, section = mark_published(text, args.n, args.permalink)
    except ValueError as exc:
        print("refusing: %s" % exc, file=sys.stderr)
        return 1
    rel = path.relative_to(repo).as_posix()
    on = dt.date.fromisoformat(args.on) if args.on else dt.date.today()
    line = log_line(on, section.meta["platform"], args.permalink, rel, args.n)
    log = repo / PUBLISHED_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text)
    with log.open("a") as handle:
        handle.write(line + "\n")
    print("%s#%d published: %s" % (rel, args.n, args.permalink))
    print("logged: %s" % log.relative_to(repo).as_posix())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Six dated posts per shipped piece, one per developer "
                    "archetype. Pure functions above; this only reads, writes "
                    "and prints.")
    parser.add_argument("--config", help="Override ~/.claude/advocacy-workflow.yml.")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scaffold", help="Create advocacy/content/drips/<date>-<slug>.md.")
    s.add_argument("--repo", required=True, help="The project's working repo.")
    s.add_argument("--piece", required=True, help="URL of the blog or video that shipped.")
    s.add_argument("--type", required=True, choices=PIECE_TYPES)
    s.add_argument("--title", help="The piece's title. Also the slug source.")
    s.add_argument("--start", help="First posting week, YYYY-MM-DD. Snaps to its Tuesday. "
                                   "Default: the first Tuesday at least %d days out."
                                   % MIN_LEAD_DAYS)
    s.add_argument("--lead", help="The one or two strongest archetypes for this piece, "
                                  "comma separated. They take the first slots.")
    s.add_argument("--today", help="Override today's date (tests, backfill).")
    s.set_defaults(run=cmd_scaffold)

    c = sub.add_parser("check", help="Validate one drip file. Exit 1 with one line per finding.")
    c.add_argument("drip")
    c.add_argument("--repo", help="Default: inferred from the drip path.")
    c.set_defaults(run=cmd_check)

    p = sub.add_parser("post", help="Record post n as live and append to published.log.")
    p.add_argument("drip")
    p.add_argument("n", type=int)
    p.add_argument("permalink")
    p.add_argument("--repo", help="Default: inferred from the drip path.")
    p.add_argument("--on", help="The date it went live, YYYY-MM-DD. Default: today.")
    p.set_defaults(run=cmd_post)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
