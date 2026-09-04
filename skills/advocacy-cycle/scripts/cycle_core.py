"""Pure core for advocacy-cycle.

Every function here takes data and returns data. No network, no Asana, no
writes. That is what makes the interesting half testable without a repo full
of drafts and without a token.

The gate and surface tables are NOT redefined here. They are imported from
advocacy-intake, which owns them, because two filers sharing one board must
share one definition. A second copy would be the copy that drifts.
"""
from __future__ import annotations

from collections import namedtuple
import pathlib
import re
import sys

_INTAKE = (pathlib.Path(__file__).resolve().parent.parent.parent
           / "advocacy-intake" / "scripts")
if str(_INTAKE) not in sys.path:
    sys.path.insert(0, str(_INTAKE))

from intake_core import (  # noqa: E402
    GATES, STYLES, SURFACES, blog_of, surface_by_key,
)

STATUSES = ("drafted", "approved", "published")

# X bills every URL at this many characters no matter how long it is, so a
# post counted naively reads shorter than it posts. Threads are the surface
# where that difference decides whether a post splits.
X_URL_BILLED_CHARS = 23

# More than this many links in one X post and the rest belongs in a reply.
X_MAX_LINKS_PER_POST = 2

# Posts within a thread file are numbered headings: `## 1`, `## 2`. That is
# how the threads are actually written. A rule of dashes is accepted as a
# fallback, but it is not the house format and never was: assuming it counted
# a whole nine-post thread as one 5,483 character post.
_POST_HEADING = re.compile(r"^#{1,6}\s*\d+\s*$", re.MULTILINE)
_POST_SEPARATOR = re.compile(r"^-{3,}[ \t]*$", re.MULTILINE)

_URL = re.compile(r"https?://\S+")

# A post carries production annotation after its text: the author's own
# character count, and blockquoted image and shot notes. None of it posts, so
# none of it counts. Counting it reported every post in a clean nine-post
# thread as roughly double its real length.
_POST_ANNOTATION = re.compile(
    r"^\s*(?:>|`?\d+\s+characters`?)", re.MULTILINE)

# A code citation: a path, then a line or line range. `writers.py:271-276`.
# The thing that sent an advocate to film code a module split had moved, three times.
_CITATION = re.compile(r"\b([\w./-]+\.[a-zA-Z]{1,4}):(\d+)(?:-(\d+))?\b")

# Anchored on a closing --- at the start of a line rather than on a preceding
# newline, so an EMPTY frontmatter block still matches. It did not before, and
# the regex ran on past the block and swallowed the first posts of the body.
# A beat: an inline HTML comment that scaffolds one section, carrying the
# section name, a word budget, the job the section has to do, and the facts
# it may use. You write into it and delete it when the section lands, so the
# beats still present are the sections still unwritten.
#
# Beats are NOT frontmatter and NOT a separate outline file. They live where
# the writing happens, which is the only place they get read.
_BEAT = re.compile(
    r"<!--+\s*([A-Z][A-Z0-9 ,.'/&()-]{2,}?)\s*[.\-=_]{3,}", re.MULTILINE)

_FRONTMATTER = re.compile(r"\A---\n(.*?)^---[ \t]*\n", re.DOTALL | re.MULTILINE)


def surface_slug(surface_key):
    """The on-disk name of a surface within its branch directory.

    `personal_video_script` is `video-script`: the branch is already the
    directory, so repeating it in the filename would be noise.
    """
    branch = surface_by_key(surface_key).branch
    return surface_key[len(branch) + 1:].replace("_", "-")


def content_path(surface_key, style=None):
    """Where one piece of content lives, relative to `advocacy/`.

    A canonical sits at the top of its own directory and its variants sit one
    level under it. That is not decoration: directory depth IS the gate, so
    Gate B is everything at the top level and Gate C is everything one level
    down.

    A blog is flat, with no directory and no variants, because a blog is the
    source the variants ultimately come from.
    """
    surface = surface_by_key(surface_key)
    slug = surface_slug(surface_key)
    if surface.kind == "blog":
        if style is not None:
            raise ValueError(
                "%s is a blog and has no style variants: it is the source "
                "they are derived from." % surface_key)
        return pathlib.PurePosixPath("content", surface.branch, "blog.md")
    base = pathlib.PurePosixPath("content", surface.branch, slug)
    if style is None:
        return base / ("%s.md" % slug)
    if style not in STYLES:
        raise ValueError("unknown style %r" % style)
    return base / "variants" / ("%s-%s.md" % (slug, style))


Piece = namedtuple("Piece", "surface style gate path")


def content_tree(kept_surface_keys):
    """Every content file a campaign owns, in gate order.

    Ordered so that reading the list top to bottom is reading the cycle in
    the order it happens.
    """
    kept = list(kept_surface_keys)
    for key in kept:
        surface_by_key(key)                     # raises on a typo
    blogs = [k for k in kept if surface_by_key(k).kind == "blog"]
    derivatives = [k for k in kept if surface_by_key(k).kind == "derivative"]

    for key in derivatives:
        if blog_of(surface_by_key(key).branch) not in blogs:
            raise ValueError(
                "%s was kept but its branch's blog was not. A derivative "
                "projects from its blog." % key)

    pieces = [Piece(k, None, "A", content_path(k)) for k in blogs]
    pieces += [Piece(k, None, "B", content_path(k)) for k in derivatives]
    for key in derivatives:
        pieces += [Piece(key, s, "C", content_path(key, s)) for s in STYLES]
    return pieces


def parse_frontmatter(text):
    """The frontmatter of a content file as a dict.

    Deliberately a small parser rather than a YAML dependency: the schema is
    four keys and a list, and this skill has no build step to install one
    into. Unknown keys are kept as raw strings.
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


def gate_task_title(piece):
    """The Asana task whose completion IS this piece's approval.

    The join between the board and the tree. These strings are built the same
    way `advocacy-intake` builds them, from the same `SURFACES` table this
    module imports, so they match by construction rather than by anyone
    remembering to keep two lists in step.
    """
    label = surface_by_key(piece.surface).label
    if piece.style is not None:
        return "Gate C: %s, %s variant" % (label, piece.style)
    return "Gate %s: %s, edit to publish ready" % (piece.gate, label)


def status_from_board(pieces, completed_titles, published_by_path=None,
                      existing_paths=None):
    """Gate state, read from Asana rather than from the files.

    **Asana is the source of truth.** A gate task marked complete IS that
    piece being approved: the board already said so, and keeping a second
    answer in the file only created something to disagree with.

    The failure modes are why it is this way round and not the other. If the
    board is right and a file is stale, nothing breaks, because nothing reads
    the file for this. If a FILE were right and the board stale, the skill
    would refuse to write variants for work the user considers approved, and they
    would go hunting for why a tool is arguing with them. One direction fails
    quietly and harmlessly; the other fails loudly at the worst moment.

    `published` is not a gate state. It is a fact about the world, so it
    comes from the file's `published:` URL, which no checkbox can tell you.
    """
    done = set(completed_titles)
    published = published_by_path or {}
    out = {}
    for piece in pieces:
        key = str(piece.path)
        if existing_paths is not None and key not in existing_paths:
            continue                    # not written yet; blocked_reason says so
        if published.get(key):
            out[key] = "published"
        elif gate_task_title(piece) in done:
            out[key] = "approved"
        else:
            out[key] = "drafted"
    return out


def apply_status(text, status, synced_on):
    """Write the board's answer into a file's frontmatter as a cache.

    One direction only. `status` is OUTPUT here and never input, so the file
    and the board cannot drift into disagreeing about who is right. Same rule
    as syncing a published piece from its live page: the source of truth
    writes to the copy, never the other way.

    `status_synced` is stamped so a reader can tell how old the cached answer
    is, which matters when the board could not be reached.
    """
    if status not in STATUSES:
        raise ValueError("unknown status %r" % status)
    lines = text.split("\n")
    if lines and lines[0] == "---":
        close = next((i for i, l in enumerate(lines[1:], 1)
                      if l.rstrip() == "---"), None)
    else:
        close = None
    if close is None:                   # no frontmatter, give it one
        return "---\nstatus: %s\nstatus_synced: %s\n---\n%s" % (
            status, synced_on, text)
    block = lines[1:close]
    out, seen = [], {"status": False, "status_synced": False}
    for line in block:
        if line.startswith("status:"):
            out.append("status: %s" % status); seen["status"] = True
        elif line.startswith("status_synced:"):
            out.append("status_synced: %s" % synced_on); seen["status_synced"] = True
        else:
            out.append(line)
    if not seen["status"]:
        out.append("status: %s" % status)
    if not seen["status_synced"]:
        out.append("status_synced: %s" % synced_on)
    return "\n".join(lines[:1] + out + lines[close:])


def status_of(text):
    """A piece's CACHED status, or None if it does not declare one.

    This is the copy, not the source. It is what the board said as of
    `status_synced`, and it is authoritative only when the board cannot be
    reached, in which case the caller must say out loud that it is reading a
    cache and how old it is.

    An unknown value is an error rather than a shrug: `status: aproved` must
    not read as "not approved yet" and silently hold the whole branch.
    """
    value = parse_frontmatter(text).get("status")
    if not value or isinstance(value, list):
        return None
    if value not in STATUSES:
        raise ValueError(
            "unknown status %r. Must be one of %s." % (value, ", ".join(STATUSES)))
    return value


def parent_of(piece):
    """The piece this one may not run ahead of, or None at the root.

    A variant's parent is its canonical. A canonical's parent is its
    branch's blog. A blog answers to nothing.
    """
    surface = surface_by_key(piece.surface)
    if piece.style is not None:
        return Piece(piece.surface, None,
                     "B" if surface.kind == "derivative" else "A",
                     content_path(piece.surface))
    if surface.kind == "derivative":
        blog = blog_of(surface.branch)
        return Piece(blog, None, "A", content_path(blog))
    return None


def blocked_reason(piece, status_by_path):
    """Why this piece may not be written yet, or None if it may.

    The rule the whole model exists to enforce: nothing derives from an
    unapproved parent, at any level. Writing variants before the canonical
    is signed off means rewriting all of them when it changes.
    """
    parent = parent_of(piece)
    if parent is None:
        return None
    parent_status = status_by_path.get(str(parent.path))
    if parent_status in ("approved", "published"):
        return None
    if parent_status is None:
        return "%s does not exist yet" % parent.path
    return "%s is %s, not approved" % (parent.path, parent_status)


def billed_length(text, url_chars=X_URL_BILLED_CHARS):
    """Character count as the platform bills it, not as Python counts it.

    X charges a flat rate per URL regardless of length, so a post with three
    long links counts far shorter than it looks and a naive count rejects
    posts that would have fit.
    """
    return len(_URL.sub("u" * url_chars, text))


def split_posts(text):
    """A thread file's posts, in order.

    Numbered headings first, because that is how the threads are written. The
    prose before the first heading is the file's own preamble explaining
    itself, not post one, so it is dropped: counting it as a post reports a
    five thousand character violation on a thread that is fine.
    """
    body = _FRONTMATTER.sub("", text)
    if _POST_HEADING.search(body):
        return [p.strip() for p in _POST_HEADING.split(body)[1:] if p.strip()]
    return [p.strip() for p in _POST_SEPARATOR.split(body) if p.strip()]


def post_body(post):
    """Just the text that posts, with the production notes removed.

    The annotation always follows the post rather than interleaving with it,
    so the body is everything before the first annotated line.
    """
    match = _POST_ANNOTATION.search(post)
    return (post[:match.start()] if match else post).strip()


Finding = namedtuple("Finding", "where what")


def check_limits(text, surface_key):
    """Every post within the surface's limit, billed the way the platform
    bills it. Returns findings; an empty list is a pass."""
    surface = surface_by_key(surface_key)
    findings = []
    posts = (split_posts(text) if surface_slug(surface_key) == "thread"
             else [_FRONTMATTER.sub("", text).strip()])
    for index, raw in enumerate(posts, 1):
        post = post_body(raw)
        if surface.limit_kind == "chars":
            length = billed_length(post)
            if length > surface.limit:
                findings.append(Finding(
                    "post %d" % index,
                    "%d chars billed, limit is %d" % (length, surface.limit)))
            links = len(_URL.findall(post))
            if surface_slug(surface_key) == "thread" and links > X_MAX_LINKS_PER_POST:
                findings.append(Finding(
                    "post %d" % index,
                    "%d links, max is %d. The rest belongs in a reply."
                    % (links, X_MAX_LINKS_PER_POST)))
        elif surface.limit_kind == "words":
            words = len(_FRONTMATTER.sub("", text).split())
            if words > surface.limit:
                findings.append(Finding(
                    "the piece",
                    "%d words, limit is %d" % (words, surface.limit)))
            break
    return findings


def open_beats(text):
    """The section labels still scaffolded, in document order.

    A beat left in the file is a section nobody has written yet, so this is
    the honest progress signal for a draft: not how long it is, but how much
    of its outline is still a comment.
    """
    return [m.group(1).strip() for m in _BEAT.finditer(text)]


def check_beats(text, status=None):
    """Findings only when a piece claims to be finished and is not.

    An open beat on a `drafted` piece is the normal state of a draft and says
    nothing worth reporting. The same beat on something marked `approved` or
    `published` means guide text shipped, or a section the outline asked for
    never got written and nobody noticed. That has already happened once.
    """
    if status is None:
        status = status_of(text)
    if status not in ("approved", "published"):
        return []
    return [Finding(label, "section still scaffolded, beat not deleted")
            for label in open_beats(text)]


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

    This is the check that pays for itself. A rotted `file.py:271-276` in a
    shoot script reads exactly like a live one and sends you to film the
    wrong code, which is a reshoot rather than a typo.
    """
    root = pathlib.Path(repo_root)
    target = root / path
    if not target.exists():
        # A citation is written the way a person says it, so `render.py:4-5`
        # means the render.py in this repo, not one at the root. Resolve by
        # suffix before calling it rotted, or every module inside a package
        # reads as a dead reference and the check cries wolf.
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


def gate_status(pieces, status_by_path):
    """How far each gate has got. What the status verb reports."""
    out = {}
    for gate in GATES:
        mine = [p for p in pieces if p.gate == gate.key]
        if not mine:
            continue
        counts = {s: 0 for s in STATUSES}
        missing = 0
        for piece in mine:
            status = status_by_path.get(str(piece.path))
            if status is None:
                missing += 1
            else:
                counts[status] += 1
        out[gate.key] = dict(counts, missing=missing, total=len(mine))
    return out
