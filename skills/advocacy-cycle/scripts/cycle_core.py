"""Pure core for advocacy-cycle.

Every function here takes data and returns data. No network, no Asana, no
writes. That is what makes the interesting half testable without a repo full
of drafts and without a token.

The seven task titles are NOT redefined here. They are imported from
advocacy-intake, which owns them, because the skill that creates the tasks
and the skill that ticks them must share one definition. A second copy would
be the copy that drifts.
"""
from __future__ import annotations

from collections import namedtuple
import datetime as dt
import pathlib
import re
import sys

_INTAKE = (pathlib.Path(__file__).resolve().parent.parent.parent
           / "advocacy-intake" / "scripts")
if str(_INTAKE) not in sys.path:
    sys.path.insert(0, str(_INTAKE))

from intake_core import SEVEN_TASKS, TITLES  # noqa: E402,F401

# X bills every URL at this many characters no matter how long it is, so a
# post counted naively reads shorter than it posts.
X_URL_BILLED_CHARS = 23

# The content files `init` scaffolds and `draft` writes, relative to
# `advocacy/`. `key` is the word the verb takes; `surface` is the frontmatter
# value and the filename stem.
ContentFile = namedtuple("ContentFile", "key surface path job")

CONTENT_FILES = (
    ContentFile(
        "blog-base", "blog-base", pathlib.PurePosixPath("content", "blog-base.md"),
        "The base post, written from notes.md. It ships to the personal blog, "
        "the company blog, or both, and every other piece points back at it."),
    ContentFile(
        "takes", "archetype-takes",
        pathlib.PurePosixPath("content", "archetype-takes.md"),
        "Six pickup briefs, one per developer archetype: what this reader "
        "wants from the piece, the fact to lead with, the angle, the call to "
        "action. A brief, not prose for publication."),
    ContentFile(
        "social", "social", pathlib.PurePosixPath("content", "social.md"),
        "Twelve undated posts: one X and one LinkedIn per archetype, in "
        "archetype order. The pool the drips may not reuse hooks from."),
)

_BY_KEY = {f.key: f for f in CONTENT_FILES}

# Files other skills or verbs own, which status and sync still read.
X_ARTICLE = pathlib.PurePosixPath("content", "x-article.md")      # x-article's
VIDEO_SCRIPT = pathlib.PurePosixPath("content", "video-script.md")  # render's input
DRIPS_DIR = pathlib.PurePosixPath("content", "drips")              # drip.py's
PUBLISHED_LOG = pathlib.PurePosixPath("content", "published.log")  # drip.py's
NOTES = pathlib.PurePosixPath("notes.md")
COMPANION = pathlib.PurePosixPath("notes.companion.md")

# Posts within a thread file are numbered headings: `## 1`, `## 2`. A rule of
# dashes is accepted as a fallback, but it is not the house format.
_POST_HEADING = re.compile(r"^#{1,6}\s*\d+\s*$", re.MULTILINE)
_POST_SEPARATOR = re.compile(r"^-{3,}[ \t]*$", re.MULTILINE)

_URL = re.compile(r"https?://\S+")

# A post carries production annotation after its text: the author's own
# character count, and blockquoted image and shot notes. None of it posts, so
# none of it counts.
_POST_ANNOTATION = re.compile(
    r"^\s*(?:>|`?\d+\s+characters`?)", re.MULTILINE)

# A code citation: a path, then a line or line range. `writers.py:271-276`.
_CITATION = re.compile(r"\b([\w./-]+\.[a-zA-Z]{1,4}):(\d+)(?:-(\d+))?\b")

# A beat: an inline HTML comment that scaffolds one section, carrying the
# section name, a word budget, the job the section has to do, and the facts
# it may use. You write into it and delete it when the section lands, so the
# beats still present are the sections still unwritten.
_BEAT = re.compile(
    r"<!--+\s*([A-Z][A-Z0-9 ,.'/&()-]{2,}?)\s*[.\-=_]{3,}", re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# Anchored on a closing --- at the start of a line rather than on a preceding
# newline, so an EMPTY frontmatter block still matches.
_FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*\n", re.DOTALL | re.MULTILINE)

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)[ \t]*$", re.MULTILINE)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TAG = re.compile(r"^\[[^\]]*\]\s*")


def content_file(key):
    """Look up a content file by verb word. Raises KeyError on anything
    else, deliberately: `draft blog` is not a file and must not become one."""
    return _BY_KEY[key]


def content_path(key):
    """Where one content file lives, relative to `advocacy/`."""
    return content_file(key).path


def scaffold(key, project, created, voice="personal-style"):
    """A content file with frontmatter only. The body is written by `draft`.

    Pure: returns text. Whether to write it is the caller's call, and the
    rule there is never to overwrite a file that exists.
    """
    f = content_file(key)
    return "\n".join([
        "---",
        "project: %s" % project,
        "surface: %s" % f.surface,
        "created: %s" % created,
        "sources: [advocacy/notes.md]",
        "passes: [%s, de-slop]" % voice,
        "published:",
        "---",
        "",
    ])


def parse_frontmatter(text):
    """The frontmatter of a content file as a dict.

    Deliberately a small parser rather than a YAML dependency: the schema is
    a handful of keys and a list, and this skill has no build step to install
    one into. Unknown keys are kept as raw strings.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    data, key = {}, None
    for line in match.group(1).split("\n"):
        if not line.strip():
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(item.group(1).strip())
            continue
        pair = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if pair:
            key = pair.group(1)
            value = pair.group(2).strip()
            data[key] = value if value else []
    return data


def published_urls(text):
    """Every URL under `published:`. A fact about the world, so it lives in
    the file: no checkbox can tell you where a piece went live.

    One piece can be live in two places (the company blog and a personal
    mirror), so the value may hold several URLs, space or comma separated,
    or as a list.
    """
    value = parse_frontmatter(text).get("published")
    if not value:
        return []
    items = value if isinstance(value, list) else re.split(r"[\s,]+", value)
    return [i.strip() for i in items
            if i.strip().startswith(("http://", "https://"))]


def set_published(text, url):
    """The file with `url` recorded under `published:`.

    Appends to any URLs already there rather than replacing them, because a
    second home for a piece is not a correction of the first. Refuses a
    value that is not a URL. A file with no frontmatter gets one.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("%r is not a URL" % url)
    existing = published_urls(text)
    if url in existing:
        return text
    value = " ".join(existing + [url])
    lines = text.split("\n")
    close = None
    if lines and lines[0] == "---":
        close = next((i for i, l in enumerate(lines[1:], 1)
                      if l.rstrip() == "---"), None)
    if close is None:
        return "---\npublished: %s\n---\n%s" % (value, text)
    block, seen = [], False
    for line in lines[1:close]:
        if line.startswith("published:"):
            block.append("published: %s" % value)
            seen = True
        else:
            block.append(line)
    if not seen:
        block.append("published: %s" % value)
    return "\n".join(lines[:1] + block + lines[close:])


def open_beats(text):
    """The section labels still scaffolded, in document order.

    A beat left in the file is a section nobody has written yet, so this is
    the honest progress signal for a draft: not how long it is, but how much
    of its outline is still a comment.
    """
    return [m.group(1).strip() for m in _BEAT.finditer(text)]


def body_of(text):
    """The prose: frontmatter and every HTML comment removed."""
    return _COMMENT.sub("", _FRONTMATTER.sub("", text)).strip()


def piece_status(text):
    """One word for where a file is, derived from the file and nothing else.

    `published` when it carries a URL, `drafting` while any beat is still
    open, `empty` when nothing but frontmatter has been written, `written`
    once the prose is in and the beats are gone.
    """
    if published_urls(text):
        return "published"
    if open_beats(text):
        return "drafting"
    if not body_of(text):
        return "empty"
    return "written"


Finding = namedtuple("Finding", "where what")


def check_beats(text):
    """Findings only when a piece is live and still carries scaffolding.

    An open beat on a draft is the normal state of a draft and says nothing
    worth reporting. The same beat on something with a `published:` URL
    means guide text shipped, or a section the outline asked for never got
    written and nobody noticed. That has already happened once.
    """
    if not published_urls(text):
        return []
    return [Finding(label, "section still scaffolded, beat not deleted")
            for label in open_beats(text)]


def billed_length(text, url_chars=X_URL_BILLED_CHARS):
    """Character count as X bills it, not as Python counts it."""
    return len(_URL.sub("u" * url_chars, text))


def split_posts(text):
    """A thread file's posts, in order.

    Numbered headings first, because that is how the threads are written. The
    prose before the first heading is the file's own preamble explaining
    itself, not post one, so it is dropped.
    """
    body = _FRONTMATTER.sub("", text)
    if _POST_HEADING.search(body):
        return [p.strip() for p in _POST_HEADING.split(body)[1:] if p.strip()]
    return [p.strip() for p in _POST_SEPARATOR.split(body) if p.strip()]


def post_body(post):
    """Just the text that posts, with the production notes removed."""
    match = _POST_ANNOTATION.search(post)
    return (post[:match.start()] if match else post).strip()


def find_citations(text):
    """Every `path:line` or `path:line-line` reference in a piece.

    Returns (path, start, end) triples. Resolving them against a repo is the
    caller's job because it touches the filesystem.
    """
    out = []
    for match in _CITATION.finditer(_FRONTMATTER.sub("", text)):
        path, start, end = match.group(1), int(match.group(2)), match.group(3)
        out.append((path, start, int(end) if end else start))
    return out


def check_citation(repo_root, path, start, end):
    """One citation resolved against the repo, or a finding saying why not.

    A rotted `file.py:271-276` in a shoot script reads exactly like a live
    one and sends you to film the wrong code, which is a reshoot rather than
    a typo.
    """
    root = pathlib.Path(repo_root)
    target = root / path
    if not target.exists():
        # A citation is written the way a person says it, so `render.py:4-5`
        # means the render.py in this repo, not one at the root. Resolve by
        # suffix before calling it rotted.
        matches = [m for m in root.rglob(path) if ".git" not in m.parts]
        if len(matches) == 1:
            target = matches[0]
        elif len(matches) > 1:
            return Finding("%s:%d-%d" % (path, start, end),
                           "ambiguous: %d files match" % len(matches))
        else:
            return Finding("%s:%d-%d" % (path, start, end), "no such file")
    try:
        lines = target.read_text(errors="replace").splitlines()
    except OSError as exc:
        return Finding("%s:%d-%d" % (path, start, end), "unreadable: %s" % exc)
    if start < 1 or end > len(lines):
        return Finding("%s:%d-%d" % (path, start, end),
                       "file has %d lines" % len(lines))
    if not any(line.strip() for line in lines[start - 1:end]):
        return Finding("%s:%d-%d" % (path, start, end),
                       "that range is blank now")
    return None


def review_date(ledger_text, title="90 day review"):
    """The date of the ledger's review entry, or None if there is none.

    The ledger groups entries under `## YYYY-MM-DD` day headings with
    `### [tag] title` entries beneath them, so the date is taken from the
    review heading itself when it carries one and from the nearest day
    heading above it otherwise. The latest dated review wins.
    """
    current, found = None, []
    for match in _HEADING.finditer(ledger_text):
        heading = match.group(2).strip()
        iso = _ISO_DATE.search(heading)
        day = None
        if iso:
            try:
                day = dt.date.fromisoformat(iso.group(0))
            except ValueError:
                day = None
        if day and not _TAG.sub("", heading).lower().startswith(title.lower()):
            current = day
            continue
        if _TAG.sub("", heading).lower().startswith(title.lower()):
            if day or current:
                found.append(day or current)
    return max(found) if found else None
