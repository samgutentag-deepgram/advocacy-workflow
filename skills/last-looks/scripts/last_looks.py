"""Last looks: the mechanical checks that run right before a piece ships.

A draft that has been through the voice skill and de-slop still has to clear
the things a script can see and a tired reader cannot: a number that is not in
notes.md, a link that 404s, an owned link with no UTM, a 700 px hero image, an
em dash. This is the one implementation of those checks. The command center's
lint imports it; the drip verb's own rules are imported here rather than
copied.

    last_looks.py advocacy/content/blog-base.md advocacy/content/social.md
    last_looks.py advocacy/content/drips/2026-10-01-hn-radio.md
    last_looks.py site/post.html https://example.com/blog/post --min-width 1600
    last_looks.py brag-output/brag.mp4            # the project's video standard

Exit 1 while any finding is open. One line per finding, `file:line: message`,
then a verdict per file. Stdlib only: pure functions over text, a thin layer
that reads files and the network, and argparse.
"""
from __future__ import annotations

import argparse
import html.parser
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple
from typing import NamedTuple

HERE = pathlib.Path(__file__).resolve().parent
_SKILLS = HERE.parent.parent
for _path in (_SKILLS / "advocacy-cycle" / "scripts",
              _SKILLS / "advocacy-intake" / "scripts",
              _SKILLS / "x-article" / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import config as machine_config  # noqa: E402  advocacy-intake's yml reader
import drip  # noqa: E402  the drip file rules, owned by advocacy-cycle
from cycle_core import _FRONTMATTER, billed_length, parse_frontmatter  # noqa: E402
from utm import owned  # noqa: E402  x-article's domain rule

VERSION = "0.3.0"

BANNED = ("leverage", "delve", "nuanced", "robust", "seamlessly", "elevate",
          "streamline", "supercharge", "empower", "unlock", "comprehensive")
EM_DASH = "—"

X_LIMIT = drip.X_LIMIT
LINKEDIN_MIN = drip.LINKEDIN_MIN
LINKEDIN_MAX = drip.LINKEDIN_MAX
LINKEDIN_MAX_HASHTAGS = drip.LINKEDIN_MAX_HASHTAGS
SOCIAL_POSTS_PER_PLATFORM = len(drip.ARCHETYPES)

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_content")
DEFAULT_CONSOLE_URL = "https://console.deepgram.com/signup"
DEFAULT_MIN_WIDTH = 1200
IMAGE_TYPES = ("png", "jpeg", "gif", "webp", "svg")

# Hosts that answer bots with 402, 999 or 401 by design, and dev URLs that are
# not meant to resolve from here. Checked by hand, never by script.
SKIP_HOSTS = ("x.com", "twitter.com", "linkedin.com", "api.deepgram.com",
              "localhost", "127.0.0.1")

_URL = re.compile(r"https?://[^\s<>\"')\]`]+")
_URL_TRIM = ".,;:"
_HASHTAG = re.compile(r"(?<!\w)#\w+")
_FENCE = re.compile(r"^```.*?^```[ \t]*$", re.DOTALL | re.MULTILINE)
_INLINE_CODE = re.compile(r"`[^`\n]*`")

# A number as a claim writes it: 350, 4.55, 6,153. Two digits or more, so
# "3 stories" is prose and "350 ms" is a measurement. Not preceded by a word
# character, a slash, a dot, a comma, a colon or a dash, which keeps the line
# half of `render.py:120-140` and the digits of a version out of it.
_NUMBER = re.compile(r"(?<![\w/.,:-])(\d{2,}(?:[.,]\d+)*)(?![\w/-])(?![.,]\d)")
_YEAR = re.compile(r"^(19|20)\d\d$")
# Word budgets, character counts and dates are targets, not facts about the build.
_BUDGET_LINE = re.compile(r"\b(words?|chars?|characters|length|20\d\d-\d\d)\b", re.I)

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_HTML_IMG = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)

Finding = namedtuple("Finding", "path line message")
Response = namedtuple("Response", "status content_type data")
Post = namedtuple("Post", "platform archetype body line")


class Options(NamedTuple):
    notes: str | None = None            # --notes override, a path
    min_width: int = DEFAULT_MIN_WIDTH
    voice: str = "personal-style"       # voice_personal from the yml
    domains: tuple = ()                 # utm_domains from the yml
    person_slug: str = ""
    blog_utm_source: str = ""
    console_url: str = DEFAULT_CONSOLE_URL
    fetch: object = None                # (url, method) -> Response, None for the network
    net: bool = True
    ffprobe: bool = True
    config: dict = {}


# --------------------------------------------------------------------------
# Text checks. Each takes text and returns [(line, message)].
# --------------------------------------------------------------------------

def body_and_offset(text):
    """The text after the frontmatter, and how many lines the frontmatter took,
    so findings report file line numbers rather than body offsets."""
    match = _FRONTMATTER.match(text)
    if not match:
        return text, 0
    return text[match.end():], text[:match.end()].count("\n")


def passes_of(fm):
    """`passes:` as a list, whether written inline or as YAML items."""
    value = fm.get("passes")
    if value is None:
        return None
    if isinstance(value, list):
        return [v.strip() for v in value]
    return [p.strip() for p in value.strip("[]").split(",") if p.strip()]


def check_frontmatter(text, voice, need_status=True):
    if not _FRONTMATTER.match(text):
        return [(None, "no frontmatter")]
    fm = parse_frontmatter(text)
    out = []
    if need_status and "status" not in fm:
        out.append((None, "frontmatter missing status"))
    passes = passes_of(fm)
    if passes is None:
        out.append((None, "frontmatter missing passes"))
    elif "de-slop" not in passes or voice not in passes:
        out.append((None, "passes does not list both %s and de-slop" % voice))
    return out


def check_em_dashes(text):
    body, off = body_and_offset(text)
    return [(n, "em dash") for n, line in enumerate(body.split("\n"), 1 + off)
            if EM_DASH in line]


def check_banned_words(text):
    body, off = body_and_offset(text)
    out = []
    for n, line in enumerate(body.split("\n"), 1 + off):
        for word in BANNED:
            if re.search(r"\b%s\w*" % word, line, re.I):
                out.append((n, 'banned word "%s"' % word))
    return out


def notes_numbers(notes_text):
    """Every number token the live part of notes.md holds. Superseded
    sections are not live, the same rule drip.py applies."""
    live = drip.live_notes(notes_text)
    tokens = set(re.findall(r"\d+(?:[.,]\d+)*", live))
    # A thousands separator is formatting, not a new claim, in either direction.
    return tokens | {t.replace(",", "") for t in tokens}


def untraced_numbers(text, allowed):
    """(line, token) for every number in the body that notes.md does not hold.

    Skips budget lines, inline code, fenced code and URLs: a number there is
    a reference or a target, not a claim about the build.
    """
    body, off = body_and_offset(text)
    out = []
    in_fence = False
    for n, line in enumerate(body.split("\n"), 1 + off):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or _BUDGET_LINE.search(line):
            continue
        stripped = _URL.sub(" ", _INLINE_CODE.sub("", line))
        for match in _NUMBER.finditer(stripped):
            num = match.group(1)
            if num in allowed or num.replace(",", "") in allowed or _YEAR.match(num):
                continue
            out.append((n, num))
    return out


def check_numbers(text, notes_text):
    if notes_text is None:
        has = untraced_numbers(text, set())
        return [(None, "no advocacy/notes.md found, so %d number(s) cannot be "
                       "traced; pass --notes" % len(has))] if has else []
    return [(n, "number %s not in notes.md" % num)
            for n, num in untraced_numbers(text, notes_numbers(notes_text))]


# --------------------------------------------------------------------------
# Social posts. social.md layouts vary by project, so the parser is loose.
# --------------------------------------------------------------------------

_HEADING = re.compile(r"^#{2,3}\s+(.*)")
_LABEL = re.compile(r"^\**\s*(X|LinkedIn)\b.*?\**:?\s*$", re.I)
_ANNOTATION = re.compile(
    r"^[*_]*(Fact|Link|Characters?|Asset|BLOCKER|No blocker|Uses|Points at|"
    r"Archetype|Needs|Image|Dependency)\b", re.I)
_COUNT = re.compile(r"^[(`]?\s*[\d,]+\s+(chars?|characters)\b", re.I)
_RULE = re.compile(r"^(-{3,}|\*{3,})$")
_TRAILING_COUNT = re.compile(r"\(?\b\d{2,3} chars?\)?\s*$", re.I)


def _post_body(buf):
    """The text that posts, out of the lines under one platform label.

    The first fenced block when there is one. Otherwise a blockquoted post is
    the first quoted run that is not an annotation (a `> **Image:**` note is
    one), which survives a label whose parenthetical wrapped onto the lines
    before it. Failing that, the plain paragraphs up to the first annotation
    (a Fact:, Link:, Characters: or image line, or a character count) or the
    first blockquote.
    """
    joined = "\n".join(buf)
    fence = re.search(r"```[^\n]*\n(.*?)```", joined, re.S)
    if fence:
        return fence.group(1).strip()
    items = []
    for para in re.split(r"\n\s*\n", joined):
        if not para.strip() or _RULE.match(para.strip()):
            continue
        is_quote = all(l.lstrip().startswith(">") for l in para.strip().split("\n"))
        text = re.sub(r"^\s*> ?", "", para, flags=re.M).strip()
        items.append((is_quote, text, bool(_ANNOTATION.match(text) or _COUNT.match(text))))
    quoted = [i for i, (q, _, a) in enumerate(items) if q and not a]
    out = []
    if quoted:
        for is_quote, text, annotated in items[quoted[0]:]:
            if not is_quote or annotated:
                break
            out.append(text)
        return "\n\n".join(out)
    for is_quote, text, annotated in items:
        if annotated:
            if out:
                break
            continue                            # a leading label line
        if is_quote:
            break
        out.append(text)
    return "\n\n".join(out)


def social_posts(text):
    """Every X and LinkedIn post in a social.md, in file order.

    A `##`/`###` heading that is not a platform names the archetype. A
    platform is a `### X` heading, a `**LinkedIn**` label (with or without a
    parenthetical), or a bare `X:` line. The post runs to the next heading or
    label.
    """
    body, off = body_and_offset(text)
    out, arche, plat, buf, start = [], None, None, [], 0
    lines = body.split("\n") + ["## end"]
    for i, line in enumerate(lines, 1 + off):
        head = _HEADING.match(line)
        label = _LABEL.match(line.strip())
        if head or label:
            if plat and buf:
                out.append(Post(plat, arche, _post_body(buf), start))
            buf = []
            if head and not re.match(r"^(X|LinkedIn)\b", head.group(1), re.I):
                arche, plat = head.group(1).strip(), None
            else:
                plat = (label.group(1) if label else head.group(1).split()[0]).lower()
                start = i
            continue
        if plat:
            buf.append(line)
    return out


def check_social(text):
    posts = social_posts(text)
    out = []
    for platform, label in (("x", "X"), ("linkedin", "LinkedIn")):
        n = sum(1 for p in posts if p.platform == platform)
        if n < SOCIAL_POSTS_PER_PLATFORM:
            out.append((None, "found %d %s posts, expected %d"
                        % (n, label, SOCIAL_POSTS_PER_PLATFORM)))
    for post in posts:
        who = post.archetype or "post"
        if post.platform == "x":
            core = _TRAILING_COUNT.sub("", post.body.strip())
            length = billed_length(core)
            if length > X_LIMIT:
                out.append((post.line, "X post for %s is %d chars (URLs billed at %d), limit %d"
                            % (who, length, drip.X_URL_BILLED_CHARS, X_LIMIT)))
        else:
            length = len(post.body)
            if not post.body:
                out.append((post.line, "LinkedIn post for %s is empty" % who))
            elif length < LINKEDIN_MIN:
                out.append((post.line, "LinkedIn post for %s is %d chars, wants at least %d"
                            % (who, length, LINKEDIN_MIN)))
            elif length > LINKEDIN_MAX:
                out.append((post.line, "LinkedIn post for %s is %d chars, limit %d"
                            % (who, length, LINKEDIN_MAX)))
            tags = len(_HASHTAG.findall(post.body))
            if tags > LINKEDIN_MAX_HASHTAGS:
                out.append((post.line, "LinkedIn post for %s has %d hashtags, max %d"
                            % (who, tags, LINKEDIN_MAX_HASHTAGS)))
    return out


def check_drip_text(text, ctx):
    """drip.py's own rules on a drip file. Em dashes are left to
    check_em_dashes, which reports them with a line number."""
    return [(None, "%s: %s" % (f.where, f.what))
            for f in drip.check_drip(text, ctx) if f.what != "em dash"]


# --------------------------------------------------------------------------
# URLs and UTMs
# --------------------------------------------------------------------------

def host_of(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def skip_host(url):
    host = host_of(url)
    return any(host == h or host.endswith("." + h) for h in SKIP_HOSTS)


def urls_in(text, with_lines=True, prose_only=False):
    """(line, url) for every URL in the text. `prose_only` drops fenced and
    inline code first, because a URL in code is not a link a reader follows."""
    body, off = body_and_offset(text)
    if prose_only:
        body = _FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), body)
        body = _INLINE_CODE.sub("", body)
    out = []
    for n, line in enumerate(body.split("\n"), 1 + off):
        for match in _URL.finditer(line):
            out.append((n, match.group(0).rstrip(_URL_TRIM)))
    return out


def utm_findings(url, domains, person_slug="", blog_utm_source=""):
    """Why one link breaks the x-article scheme, or [] if it does not.

    Owned domains carry all four utm keys and nothing else; the person goes in
    utm_content, never utm_source. Other hosts carry no utm at all.
    """
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query, keep_blank_values=True)
    utm = {k: v[-1] for k, v in query.items() if k.startswith("utm_")}
    if skip_host(url):
        return []
    if not (domains and owned(url, list(domains))):
        if utm:
            return ["tagged link on a domain that is not owned (%s); remove %s"
                    % (host_of(url), ", ".join(sorted(utm)))]
        return []
    out = []
    missing = [k for k in UTM_KEYS if not utm.get(k)]
    if missing:
        out.append("owned link missing %s" % ", ".join(missing))
    extra = sorted(k for k in utm if k not in UTM_KEYS)
    if extra:
        out.append("owned link carries %s; only the four utm keys" % ", ".join(extra))
    source = utm.get("utm_source", "")
    if person_slug and person_slug in source and source != blog_utm_source:
        out.append("utm_source %r names the person; the person belongs in utm_content" % source)
    content = utm.get("utm_content", "")
    if person_slug and content and not content.startswith(person_slug + "_"):
        out.append("utm_content %r should be %s_<placement>" % (content, person_slug))
    return out


def check_utms(text, opts):
    seen, out = set(), []
    for line, url in urls_in(text, prose_only=True):
        if url in seen:
            continue
        seen.add(url)
        for message in utm_findings(url, opts.domains, opts.person_slug, opts.blog_utm_source):
            out.append((line, "%s: %s" % (message, url)))
    return out


_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/129.0 Safari/537.36 last-looks/%s" % VERSION)
_FETCH_LIMIT = 2 * 1024 * 1024


def http_fetch(url, method="GET", timeout=20):
    """One request. Redirects are followed; a failure is a status of 0."""
    req = urllib.request.Request(url, method=method,
                                 headers={"User-Agent": _UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = b"" if method == "HEAD" else resp.read(_FETCH_LIMIT)
            return Response(resp.status, resp.headers.get("Content-Type", ""), data)
    except urllib.error.HTTPError as exc:
        ctype = exc.headers.get("Content-Type", "") if exc.headers else ""
        return Response(exc.code, ctype, b"")
    except Exception:  # URLError, socket, ssl, http.client, bad URL
        return Response(0, "", b"")


_URL_CACHE = {}


def url_ok(url, fetch):
    """HEAD, then GET, once per URL per run."""
    if url not in _URL_CACHE:
        resp = fetch(url, "HEAD")
        if not 200 <= resp.status < 400:
            resp = fetch(url, "GET")
        _URL_CACHE[url] = 200 <= resp.status < 400
    return _URL_CACHE[url]


def check_urls(text, fetch):
    seen, out = set(), []
    for line, url in urls_in(text):
        if url in seen or skip_host(url):
            continue
        seen.add(url)
        if not url_ok(url, fetch):
            out.append((line, "URL does not resolve: %s" % url))
    return out


# --------------------------------------------------------------------------
# Images. Dimensions come from the file header; no Pillow.
# --------------------------------------------------------------------------

def image_info(data):
    """(format, width, height) from the first bytes of an image, or None if
    it is not one of the five formats. SVG has no pixel width."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return ("png", int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"))
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return ("gif", int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little"))
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8 " and len(data) >= 30:
            w = int.from_bytes(data[26:28], "little") & 0x3FFF
            h = int.from_bytes(data[28:30], "little") & 0x3FFF
            return ("webp", w, h)
        if chunk == b"VP8L" and len(data) >= 25:
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return ("webp", w, h)
        if chunk == b"VP8X" and len(data) >= 30:
            return ("webp", 1 + int.from_bytes(data[24:27], "little"),
                    1 + int.from_bytes(data[27:30], "little"))
        return ("webp", None, None)
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                return ("jpeg", int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            i += 2 + length
        return ("jpeg", None, None)
    head = data[:2048].lstrip(b"\xef\xbb\xbf").lstrip()
    if head.startswith(b"<svg") or (head.startswith((b"<?xml", b"<!DOCTYPE svg")) and b"<svg" in head):
        return ("svg", None, None)
    return None


def image_findings(data, label, min_width):
    """Why these bytes fail as a content image, or []."""
    info = image_info(data)
    if info is None:
        return ["%s is not PNG, JPEG, GIF, WebP or SVG" % label]
    fmt, width, _ = info
    if fmt == "svg":
        return []
    if width is None:
        return ["%s: could not read the %s width from its header" % (label, fmt)]
    if width < min_width:
        return ["%s is %d px wide, wants at least %d" % (label, width, min_width)]
    return []


def image_refs(text):
    """(line, src) for every markdown image and <img src> in the text."""
    body, off = body_and_offset(text)
    out = []
    for n, line in enumerate(body.split("\n"), 1 + off):
        for pattern in (_MD_IMAGE, _HTML_IMG):
            for match in pattern.finditer(line):
                out.append((n, match.group(1)))
    return out


def _is_remote(src):
    return src.startswith(("http://", "https://"))


def check_local_image(path, label, min_width):
    path = pathlib.Path(path)
    if not path.is_file():
        return ["image %s does not exist" % label]
    try:
        data = path.open("rb").read(_FETCH_LIMIT)
    except OSError as exc:
        return ["image %s unreadable: %s" % (label, exc)]
    return image_findings(data, "image %s" % label, min_width)


def check_remote_image(url, fetch, min_width=None):
    resp = fetch(url, "GET")
    if resp.status != 200:
        return ["image %s returned %s" % (url, resp.status or "no response")]
    ctype = (resp.content_type or "").split(";")[0].strip().lower()
    if not (ctype.startswith("image/") or image_info(resp.data)):
        return ["image %s is %s, not an image content type" % (url, ctype or "untyped")]
    if min_width is None:
        return []
    return image_findings(resp.data, "image %s" % url, min_width)


def check_images_md(text, base_dir, opts):
    """Images a markdown file references: local files checked on disk, remote
    ones fetched, both held to the width floor."""
    out, seen = [], set()
    for line, src in image_refs(text):
        if src in seen or src.startswith("data:"):
            continue
        seen.add(src)
        if _is_remote(src):
            if skip_host(src) or not opts.net:
                continue
            messages = check_remote_image(src, opts.fetch or http_fetch, opts.min_width)
        else:
            target = pathlib.Path(os.path.expanduser(src.split("#")[0].split("?")[0]))
            if not target.is_absolute():
                target = pathlib.Path(base_dir) / target
            messages = check_local_image(target, src, opts.min_width)
        out.extend((line, m) for m in messages)
    return out


# --------------------------------------------------------------------------
# HTML pages, on disk or live
# --------------------------------------------------------------------------

class _Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images, self.links, self.meta = [], [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if tag == "img" and a.get("src"):
            self.images.append((line, a["src"].strip()))
        elif tag == "a" and a.get("href", "").startswith(("http://", "https://")):
            self.links.append((line, a["href"].strip()))
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").strip().lower()
            if key in ("og:image", "twitter:image", "twitter:image:src") and a.get("content"):
                self.meta.setdefault(key.replace(":src", ""), (line, a["content"].strip()))


def parse_page(text):
    page = _Page()
    page.feed(text)
    return page


def check_page(text, base, opts, local_dir=None):
    """Every <img> loads as an image, og:image and twitter:image exist and
    load, owned <a> links carry UTMs. `base` is the page URL or the file."""
    page = parse_page(text)
    fetch = opts.fetch or http_fetch
    out, seen = [], set()
    for line, src in page.images:
        if src.startswith("data:") or src in seen:
            continue
        seen.add(src)
        target = urllib.parse.urljoin(base, src) if _is_remote(base) else src
        if _is_remote(target):
            if opts.net and not skip_host(target):
                out.extend((line, m) for m in check_remote_image(target, fetch))
        elif local_dir is not None:
            path = pathlib.Path(local_dir) / target.split("#")[0].split("?")[0]
            if not path.is_file():
                out.append((line, "image %s does not exist" % src))
            elif image_info(path.open("rb").read(_FETCH_LIMIT)) is None:
                out.append((line, "image %s is not PNG, JPEG, GIF, WebP or SVG" % src))
    for key in ("og:image", "twitter:image"):
        if key not in page.meta:
            out.append((None, "no %s meta tag" % key))
            continue
        line, url = page.meta[key]
        if not _is_remote(url):
            out.append((line, "%s must be an absolute https URL, got %s" % (key, url)))
        elif opts.net:
            out.extend((line, "%s: %s" % (key, m)) for m in check_remote_image(url, fetch))
    for line, url in page.links:
        if url in seen:
            continue
        seen.add(url)
        for message in utm_findings(url, opts.domains, opts.person_slug, opts.blog_utm_source):
            out.append((line, "%s: %s" % (message, url)))
        if opts.net and not skip_host(url) and not url_ok(url, fetch):
            out.append((line, "URL does not resolve: %s" % url))
    return out


# --------------------------------------------------------------------------
# The video standard: two videos, four beats, a tagged console CTA
# --------------------------------------------------------------------------

BEATS = (
    ("what this is", (r"\bwhat (?:this|it) is\b", r"\bwhat is (?:this|it)\b",
                      r"\bwhat we built\b", r"\bthe demo\b")),
    ("how it works", (r"\bhow it works\b", r"\bunder the hood\b", r"\barchitecture\b")),
    ("why you'd use it", (r"\bwhy\b", r"\bwhen to use\b", r"\bthe problem\b")),
    ("examples for expansion", (r"\bexamples? for expansion\b", r"\bexpansion\b",
                                r"\bextend", r"\bnext steps?\b", r"\bwhat else\b",
                                r"\bideas?\b")),
)
_BEAT_NAME_KEYS = ("dir", "label", "title", "name", "heading", "beat", "scene", "section")
_SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "footage",
              "frames"}
_SCRIPT_NAME = re.compile(
    r"^([^/]*script[^/]*\.md|shots?\.md|shot-?list\.md|brag-plan\.md|share-copy\.txt|"
    r"storyboard[^/]*\.py|[^/]*beats[^/]*\.(py|json)|[^/]*narration[^/]*\.json|takes\.json|"
    r"[^/]*script[^/]*\.json)$", re.I)
_REMOTION_CONFIG = re.compile(r"^remotion\.config\.(ts|js|mjs|cjs)$")


def beat_names(text, suffix):
    """(position, name) for every heading, label or beat direction in a
    script file. Markdown gives headings, bold labels at the start of a line,
    `Beat n:` lines, HTML-comment beats and short table cells (a storyboard's
    Scene column); JSON gives dir/label/title strings and the direction of
    each [direction, line] beat; Python gives its string literals. Plain text
    gives nothing, because a caption has no beats."""
    out = []
    if suffix in (".md", ".markdown"):
        patterns = (r"^#{1,6}\s+(.+?)\s*$",
                    r"^\*\*([^*\n]+?):?\*\*",
                    r"^(?:Beat|Scene|Shot|Section)\s*\w*[.:)-]\s*(.+?)\s*$",
                    r"<!--+\s*([A-Z][A-Z0-9 ,.'/&()-]{2,}?)\s*[.\-=_]{3,}")
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.MULTILINE):
                out.append((match.start(), match.group(1).strip()))
        for match in re.finditer(r"^\|(.+)\|\s*$", text, re.MULTILINE):
            offset = match.start()
            for cell in match.group(1).split("|"):
                name = cell.strip()
                if 2 <= len(name) <= 40 and not re.fullmatch(r"[-: ]+", name):
                    out.append((offset, name))
                offset += len(cell) + 1
    elif suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError:
            return []
        counter = [0]

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in _BEAT_NAME_KEYS and isinstance(value, str):
                        counter[0] += 1
                        out.append((counter[0], value))
                    walk(value)
            elif isinstance(node, list):
                if len(node) >= 2 and isinstance(node[0], str) and isinstance(node[1], str):
                    counter[0] += 1
                    out.append((counter[0], node[0]))
                for item in node:
                    walk(item)
        walk(data)
    elif suffix == ".py":
        for match in re.finditer(r"\"([^\"\n]{3,120})\"|'([^'\n]{3,120})'", text):
            out.append((match.start(), match.group(1) or match.group(2)))
    return sorted(out)


def beat_coverage(names):
    """(found, missing, in_order). `found` maps each beat to the position of
    its first match; `in_order` is whether those positions run in the
    standard's order. A name matches by synonym, case-insensitive."""
    found = {}
    for beat, patterns in BEATS:
        for pos, name in names:
            low = name.lower().replace("’", "'")
            if any(re.search(p, low) for p in patterns):
                found[beat] = pos
                break
    missing = [beat for beat, _ in BEATS if beat not in found]
    order = [found[beat] for beat, _ in BEATS if beat in found]
    return found, missing, order == sorted(order)


def cta_findings(text, project, person_slug, console_url=DEFAULT_CONSOLE_URL):
    """Why the closing console CTA is missing or untagged, or []."""
    want = urllib.parse.urlsplit(console_url)
    want_path = want.path.rstrip("/") or "/"
    candidates = [u for _, u in urls_in(text) if host_of(u) == (want.hostname or "").lower()]
    if not candidates:
        return ["console CTA missing: no %s link" % want.hostname]
    slugs = {project, project.replace("-", "_"), project.replace("_", "-")}
    best, best_problems = None, None
    for url in candidates:
        parts = urllib.parse.urlsplit(url)
        query = {k: v[-1] for k, v in urllib.parse.parse_qs(parts.query).items()}
        problems = []
        if (parts.path.rstrip("/") or "/") != want_path:
            problems.append("points at %s, the signup is %s" % (parts.path or "/", want_path))
        if not query.get("utm_source"):
            problems.append("missing utm_source")
        if query.get("utm_medium") != "video":
            problems.append("utm_medium is %r, want video" % query.get("utm_medium", ""))
        if query.get("utm_campaign") not in slugs:
            problems.append("utm_campaign is %r, want %s" % (query.get("utm_campaign", ""), project))
        content = query.get("utm_content", "")
        want_content = "%s_video" % person_slug if person_slug else "<person_slug>_video"
        if (person_slug and content != want_content) or (not person_slug and not content.endswith("_video")):
            problems.append("utm_content is %r, want %s" % (content, want_content))
        if not problems:
            return []
        if best_problems is None or len(problems) < len(best_problems):
            best, best_problems = url, problems
    return ["console CTA %s: %s" % (best, "; ".join(best_problems))]


def _walk(root, maxdepth):
    root = pathlib.Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_depth = len(pathlib.Path(dirpath).relative_to(root).parts)
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("brag-output")]
        if rel_depth >= maxdepth:
            dirnames[:] = []
        for name in filenames:
            yield pathlib.Path(dirpath) / name


def find_videos(repo):
    """{'brag': [(mp4, dir)], 'remotion': [(mp4 or None, project dir)]}.

    A brag video is `brag-output*/brag*.mp4`. A Remotion video is a render
    under a Remotion project (a remotion.config.* or a package.json naming
    remotion), or failing that any mp4 under video/, renders/ or an edit
    output directory, which is where the renders land.
    """
    repo = pathlib.Path(repo)
    brag = [(mp4, d) for d in sorted(repo.glob("brag-output*")) if d.is_dir()
            for mp4 in sorted(d.glob("brag*.mp4"))]
    projects = []
    for path in _walk(repo, maxdepth=6):
        if _REMOTION_CONFIG.match(path.name):
            projects.append(path.parent)
        elif path.name == "package.json" and path.parent not in projects:
            try:
                if '"remotion"' in path.read_text(errors="replace"):
                    projects.append(path.parent)
            except OSError:
                pass
    projects = sorted(set(projects))
    remotion = []
    for proj in projects:
        mp4s = sorted(p for p in _walk(proj, maxdepth=3) if p.suffix.lower() == ".mp4")
        if not mp4s:
            mp4s = sorted(p for p in _walk(proj.parent, maxdepth=3) if p.suffix.lower() == ".mp4")
        remotion.append((mp4s[0] if mp4s else None, proj))
    if not remotion:
        for sub in ("video", "renders", "edit/out", "out"):
            d = repo / sub
            if d.is_dir():
                for mp4 in sorted(p for p in _walk(d, maxdepth=3) if p.suffix.lower() == ".mp4"):
                    remotion.append((mp4, d))
    return {"brag": brag, "remotion": remotion}


def script_files(video_dir, repo):
    """The script and beat files that belong to a video, nearest first.

    The video's own directory, then its parent when that parent is not the
    repo itself (a Remotion project's worktree, say), plus the storyboard
    skill's beats module at its conventional paths. Never the whole repo: a
    podcast episode's script.json is not a video's beat file.
    """
    repo = pathlib.Path(repo)
    video_dir = pathlib.Path(video_dir)
    roots = [video_dir]
    parent = video_dir.parent
    if parent != repo and (repo in parent.parents) and parent.name not in ("worktrees", ".claude"):
        roots.append(parent)
    out = []
    for d in roots:
        for path in _walk(d, maxdepth=3):
            if _SCRIPT_NAME.match(path.name) and path not in out:
                out.append(path)
    for rel in ("tools/storyboard_beats.py", "docs/storyboard_beats.py"):
        path = repo / rel
        if path.is_file() and path not in out:
            out.append(path)
    return sorted(out, key=lambda p: (len(p.parts), p.name != "brag-plan.md", str(p)))


def ffprobe_info(path):
    """(width, height, seconds) from ffprobe, or None when it cannot say."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        data = json.loads(proc.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        return (int(stream.get("width", 0)), int(stream.get("height", 0)),
                float((data.get("format") or {}).get("duration", 0) or 0))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def frame_ok(width, height):
    return (width >= 1920 and height >= 1080) or (width >= 1080 and height >= 1920)


def project_slug(repo):
    name = pathlib.Path(repo).resolve().name
    return name[:-4] if name.endswith("-lab") else name


def check_video(repo, opts):
    """The project's video standard. Returns (findings, notes): findings are
    what blocks a video, notes are durations and the ffprobe status."""
    repo = pathlib.Path(repo).resolve()
    project = project_slug(repo)
    found = find_videos(repo)
    findings, notes = [], []
    probe = shutil.which("ffprobe") if opts.ffprobe else None
    if opts.ffprobe and not probe:
        notes.append("ffprobe not installed; frame size and duration not checked")

    def rel(p):
        try:
            return str(pathlib.Path(p).relative_to(repo))
        except ValueError:
            return str(p)

    checked_dirs = set()

    def one(label, mp4, video_dir):
        if mp4 is not None and probe:
            info = ffprobe_info(mp4)
            if info is None:
                findings.append("%s: ffprobe could not read %s" % (label, rel(mp4)))
            else:
                w, h, secs = info
                notes.append("%s: %s is %dx%d, %.1f s" % (label, rel(mp4), w, h, secs))
                if not frame_ok(w, h):
                    findings.append("%s: %s is %dx%d, want at least 1920x1080 or 1080x1920"
                                    % (label, rel(mp4), w, h))
        if (label, video_dir) in checked_dirs:
            return                              # one script check per video directory
        checked_dirs.add((label, video_dir))
        scripts = script_files(video_dir, repo)
        if not scripts:
            findings.append("%s: no script or beat file next to %s" % (label, rel(video_dir)))
            return
        names, texts = [], []
        for i, path in enumerate(scripts):
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            texts.append(text)
            names.extend(((i, pos), name) for pos, name in beat_names(text, path.suffix.lower()))
        _, missing, in_order = beat_coverage(names)
        where = ", ".join(rel(p) for p in scripts[:3])
        if missing:
            findings.append("%s: beats missing in %s: %s" % (label, where, ", ".join(missing)))
        elif not in_order:
            findings.append("%s: beats out of order in %s; the standard is %s"
                            % (label, where, ", ".join(b for b, _ in BEATS)))
        for message in cta_findings("\n".join(texts), project, opts.person_slug, opts.console_url):
            findings.append("%s: %s" % (label, message))

    if not found["brag"]:
        findings.append("missing brag video (brag-output*/brag*.mp4)")
    for mp4, d in found["brag"]:
        one("brag", mp4, d)
    if not found["remotion"]:
        findings.append("missing Remotion video (no remotion.config.*, no render under video/ or renders/)")
    for mp4, d in found["remotion"]:
        if mp4 is None:
            findings.append("remotion: project at %s has no render" % rel(d))
        one("remotion", mp4, d)
    return findings, notes


# --------------------------------------------------------------------------
# Files. Everything below touches the filesystem or the network.
# --------------------------------------------------------------------------

KINDS = ("prose", "social", "drip", "notes", "html", "url", "video")


def kind_of(target):
    target = str(target)
    if target.startswith(("http://", "https://")):
        return "url"
    path = pathlib.Path(target)
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        return "html"
    if suffix in (".mp4", ".mov", ".json", ".py"):
        return "video"
    if path.name == "notes.md":
        return "notes"
    if path.parent.name == "drips":
        return "drip"
    if path.name == "social.md":
        return "social"
    return "prose"


def project_root(path):
    """The repo a file belongs to: the nearest ancestor holding advocacy/,
    .hub/ or .git. None when it is a loose file."""
    for parent in pathlib.Path(path).resolve().parents:
        if (parent / "advocacy").is_dir() or (parent / ".hub").is_dir() or (parent / ".git").exists():
            return parent
    return None


def find_notes(path, override=None):
    if override:
        return pathlib.Path(os.path.expanduser(override))
    for parent in pathlib.Path(path).resolve().parents:
        for candidate in (parent / "notes.md" if parent.name == "advocacy" else None,
                          parent / "advocacy" / "notes.md"):
            if candidate is not None and candidate.is_file():
                return candidate
    return None


def options_from_config(cfg, **overrides):
    cfg = machine_config.with_defaults(cfg or {})
    domains = tuple(d.strip().lower() for d in (cfg.get("utm_domains") or "").split(",") if d.strip())
    values = dict(
        voice=cfg.get("voice_personal") or "personal-style",
        domains=domains,
        person_slug=(cfg.get("person_slug") or "").strip(),
        blog_utm_source=(cfg.get("blog_utm_source") or "").strip(),
        console_url=(cfg.get("console_signup_url") or DEFAULT_CONSOLE_URL).strip(),
        config=cfg,
    )
    values.update({k: v for k, v in overrides.items() if v is not None})
    return Options(**values)


def _read(path):
    return pathlib.Path(path).read_text(errors="replace")


def check_file(path, kind, opts):
    """Every finding on one file, as Finding(path, line, message)."""
    path = pathlib.Path(path)
    if not path.is_file():
        return [Finding(str(path), None, "no such file")]
    text = _read(path)
    fetch = opts.fetch or http_fetch
    results = []
    if kind == "html":
        results += check_page(text, str(path), opts, local_dir=path.parent)
        return [Finding(str(path), line, msg) for line, msg in results]
    if kind == "video":
        return []
    if kind != "notes":
        results += check_frontmatter(text, opts.voice, need_status=(kind != "drip"))
    results += check_em_dashes(text)
    results += check_banned_words(text)
    if kind in ("prose", "social"):
        notes = find_notes(path, opts.notes)
        results += check_numbers(text, _read(notes) if notes and notes.is_file() else None)
    if kind == "social":
        results += check_social(text)
    if kind == "drip":
        try:
            repo = drip.repo_of(path)
            ctx = drip.project_context(repo, drip_path=path, config_values=opts.config)
        except ValueError:
            notes = find_notes(path, opts.notes)
            ctx = drip.Context(notes=_read(notes) if notes and notes.is_file() else "",
                               blackouts=set(), taken={}, hooks={})
        if opts.notes:
            ctx = ctx._replace(notes=_read(opts.notes))
        results += check_drip_text(text, ctx)
    if kind != "notes":
        results += check_utms(text, opts)
        results += check_images_md(text, path.parent, opts)
    if opts.net:
        results += check_urls(text, fetch)
    return [Finding(str(path), line, msg) for line, msg in results]


def check_url(url, opts):
    fetch = opts.fetch or http_fetch
    resp = fetch(url, "GET")
    if resp.status != 200:
        return [Finding(url, None, "page returned %s" % (resp.status or "no response"))]
    ctype = (resp.content_type or "").split(";")[0].lower()
    if ctype and "html" not in ctype:
        return [Finding(url, None, "page is %s, not HTML" % ctype)]
    text = resp.data.decode("utf-8", errors="replace")
    return [Finding(url, line, msg) for line, msg in check_page(text, url, opts)]


def format_finding(finding, base=None):
    path = finding.path
    if base and not path.startswith(("http://", "https://")):
        try:
            path = str(pathlib.Path(path).resolve().relative_to(pathlib.Path(base).resolve()))
        except ValueError:
            pass
    if finding.line is None:
        return "%s: %s" % (path, finding.message)
    return "%s:%d: %s" % (path, finding.line, finding.message)


def _display(target):
    if str(target).startswith(("http://", "https://")):
        return str(target)
    path = pathlib.Path(target).resolve()
    try:
        return str(path.relative_to(pathlib.Path.cwd()))
    except ValueError:
        return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The mechanical checks before a piece ships. One line per "
                    "finding, a verdict per file, exit 1 while anything is open.")
    parser.add_argument("targets", nargs="+",
                        help="Content files, HTML pages, live URLs, or a video or beat file.")
    parser.add_argument("--notes", help="Override the project's advocacy/notes.md.")
    parser.add_argument("--min-width", type=int, default=None,
                        help="Raster images must be at least this wide. Default %d." % DEFAULT_MIN_WIDTH)
    parser.add_argument("--config", help="Override ~/.claude/advocacy-workflow.yml.")
    parser.add_argument("--repo", help="The project repo, when it cannot be inferred from the path.")
    parser.add_argument("--voice", help="Override voice_personal, the pass every file must list.")
    parser.add_argument("--domains", help="Override utm_domains, comma separated.")
    parser.add_argument("--no-net", action="store_true", help="Skip every network check.")
    parser.add_argument("--no-video", action="store_true", help="Skip the project video standard.")
    args = parser.parse_args(argv)

    cfg = machine_config.load(args.config)
    opts = options_from_config(
        cfg, notes=args.notes, min_width=args.min_width, voice=args.voice,
        domains=tuple(d.strip().lower() for d in args.domains.split(",") if d.strip()) if args.domains else None,
        net=not args.no_net)

    blocking, verdicts, video_repos = 0, [], {}
    for target in args.targets:
        kind = kind_of(target)
        if kind == "url":
            findings = check_url(target, opts)
        else:
            findings = check_file(pathlib.Path(target).expanduser(), kind, opts)
        for finding in findings:
            print(format_finding(finding, base=pathlib.Path.cwd()))
        repo = pathlib.Path(args.repo).expanduser().resolve() if args.repo else (
            project_root(target) if kind != "url" else None)
        if repo is not None and not args.no_video:
            blocks = kind == "video"
            video_repos[repo] = video_repos.get(repo, False) or blocks
        n = len(findings)
        verdicts.append((target, n, kind))
        blocking += n

    for repo, blocks in video_repos.items():
        findings, notes = check_video(repo, opts)
        label = "video" if blocks else "video reminders"
        for note in notes:
            print("%s (%s): %s" % (label, project_slug(repo), note))
        for message in findings:
            print("%s (%s): %s" % (label, project_slug(repo), message))
        if blocks:
            blocking += len(findings)
            for i, (target, n, kind) in enumerate(verdicts):
                if kind == "video" and project_root(target) == repo:
                    verdicts[i] = (target, n + len(findings), kind)

    print()
    for target, n, _ in verdicts:
        print("%s: %s" % (_display(target), "ship-ready" if n == 0 else
                          "%d finding%s, not ship-ready" % (n, "" if n == 1 else "s")))
    print("%d finding%s in %d file%s" % (blocking, "" if blocking == 1 else "s",
                                         len(verdicts), "" if len(verdicts) == 1 else "s"))
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
