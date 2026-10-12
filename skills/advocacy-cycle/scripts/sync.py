"""What the files say has started and what they say is done, as stage titles.

A campaign is one parent task on the home board. Its stage subtasks are
created only when a stage starts, so the board never carries a placeholder.
Status comes from files. Asana is updated from files, in one direction, and
never by hand except ticking. This script is the file half of that: it reads
the repo and prints which stages the files show started (create the subtask)
and which they prove complete (tick it), with the evidence. The Asana half
(fetch the parent's subtasks, create the started ones that are missing, tick
the complete ones still open, never untick or delete anything) is the
model's, through the Asana MCP tools, because no script here holds a token.

    sync.py --repo <path> [--day0 YYYY-MM-DD] [--today YYYY-MM-DD]
            [--existing-titles-file <file>] [--config <yml>]

Stdlib only. Reads hub.yml through intake_core, frontmatter through
cycle_core, and drips through drip.py, so none of those formats exist twice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from collections import namedtuple
from urllib.parse import urlparse

HERE = pathlib.Path(__file__).resolve().parent
_INTAKE = HERE.parent.parent / "advocacy-intake" / "scripts"
for _path in (HERE, _INTAKE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import config as machine_config  # noqa: E402  advocacy-intake's yml reader
from intake_core import (  # noqa: E402
    REVIEW_TITLE, SEVEN_TASKS, TITLES, campaign_dates, due_on, migration_message,
    read_public_repo, read_signals, read_tracking, reconcile, task_by_title,
)
from cycle_core import (  # noqa: E402
    COMPANION, CONTENT_FILES, DRIPS_DIR, NOTES, PUBLISHED_LOG, VIDEO_SCRIPT,
    X_ARTICLE, open_beats, parse_frontmatter, piece_status, published_urls,
    review_date,
)
import drip  # noqa: E402

LEDGER = pathlib.PurePosixPath(".hub", "ledger.md")

PUBLIC_REPO, PERSONAL_BLOG, CORPORATE_BLOG, X_ARTICLE_LIVE, DRIP, VIDEO = TITLES[:6]

Evidence = namedtuple("Evidence", "task because")


# --------------------------------------------------------------------------
# Pure
# --------------------------------------------------------------------------

def host_of(url):
    """The host of a URL, lowercased, without a leading www."""
    value = (url or "").strip()
    if not value:
        return ""
    parsed = urlparse(value if "//" in value else "//" + value)
    host = parsed.netloc.lower()
    return host[4:] if host.startswith("www.") else host


def classify_blog(url, config_values):
    """Which blog task a live URL belongs to, or None when the config cannot
    say.

    The personal blog is the host of `blog_base_url`; the company's blogs are
    the hosts in `utm_domains`, the same two settings x-article already
    reads. Anything else is reported rather than guessed, because ticking
    the wrong one is a lie on the board.
    """
    cfg = config_values or {}
    host = host_of(url)
    if not host:
        return None
    personal = host_of(cfg.get("blog_base_url") or "")
    if personal and host == personal:
        return PERSONAL_BLOG
    corporate = {host_of(d) for d in (cfg.get("utm_domains") or "").split(",")
                 if d.strip()}
    if host in corporate:
        return CORPORATE_BLOG
    return None


def drip_written(text):
    """True when every one of the six posts has text in its fence."""
    sections = drip.parse_sections(text)
    return (len(sections) == len(drip.ARCHETYPES)
            and all(section.text for section in sections))


def ordered(evidence):
    """One Evidence per task, in the order of the seven, first reason kept."""
    first = {}
    for item in evidence:
        first.setdefault(item.task, item)
    return [first[title] for title in TITLES if title in first]


# --------------------------------------------------------------------------
# The repo. Everything below touches the filesystem, read-only.
# --------------------------------------------------------------------------

def _read(path):
    return pathlib.Path(path).read_text(errors="replace")


def _status(path):
    return piece_status(_read(path)) if path.is_file() else "missing"


def file_states(repo):
    """Where every content file is, by its path under advocacy/."""
    advocacy = pathlib.Path(repo) / "advocacy"
    out = {}
    for rel in [NOTES, COMPANION] + [f.path for f in CONTENT_FILES] + [X_ARTICLE, VIDEO_SCRIPT]:
        path = advocacy / rel
        state = _status(path)
        row = {"status": state}
        if path.is_file():
            beats = open_beats(_read(path))
            if beats:
                row["open_beats"] = beats
            urls = published_urls(_read(path))
            if urls:
                row["published"] = urls
        out[str(rel)] = row
    return out


def drip_states(repo):
    """Per drip file: how many posts are written, and the piece it drips."""
    drips = pathlib.Path(repo) / "advocacy" / DRIPS_DIR
    out = {}
    if not drips.is_dir():
        return out
    for path in sorted(drips.glob("*.md")):
        text = _read(path)
        fm = parse_frontmatter(text)
        written, unwritten = drip.progress(drip.parse_sections(text))
        out[path.name] = {
            "piece": fm.get("piece") if isinstance(fm.get("piece"), str) else None,
            "piece_type": fm.get("piece_type") if isinstance(fm.get("piece_type"), str) else None,
            "written": len(written),
            "unwritten": len(unwritten),
            "live": len([s for s in written if s.meta.get("published")]),
        }
    return out


def evidence_from(repo, config_values, day0=None):
    """(complete, unmatched): the tasks the files prove done, with the file
    that says so, and the live URLs no rule could place."""
    repo = pathlib.Path(repo)
    advocacy = repo / "advocacy"
    found, unmatched = [], []

    public = read_public_repo(repo)
    if public:
        found.append(Evidence(PUBLIC_REPO, ".hub/hub.yml public_repo: %s" % public))

    blog = advocacy / CONTENT_FILES[0].path
    if blog.is_file():
        for url in published_urls(_read(blog)):
            task = classify_blog(url, config_values)
            if task:
                found.append(Evidence(task, "%s published: %s" % (CONTENT_FILES[0].path, url)))
            else:
                unmatched.append("%s published: %s (host matches neither blog_base_url "
                                 "nor utm_domains)" % (CONTENT_FILES[0].path, url))

    article = advocacy / X_ARTICLE
    if article.is_file():
        for url in published_urls(_read(article)):
            found.append(Evidence(X_ARTICLE_LIVE, "%s published: %s" % (X_ARTICLE, url)))

    for name, state in drip_states(repo).items():
        rel = "%s/%s" % (DRIPS_DIR, name)
        if state["unwritten"] == 0 and state["written"] == len(drip.ARCHETYPES):
            found.append(Evidence(DRIP, "%s has all %d posts written and dated"
                                  % (rel, len(drip.ARCHETYPES))))
        if state["piece_type"] == "video" and state["piece"]:
            found.append(Evidence(VIDEO, "%s drips a video: %s" % (rel, state["piece"])))
        if state["piece_type"] == "blog" and state["piece"]:
            task = classify_blog(state["piece"], config_values)
            if task:
                found.append(Evidence(task, "%s drips a blog: %s" % (rel, state["piece"])))

    log = advocacy / PUBLISHED_LOG
    if log.is_file():
        lines = [l for l in _read(log).splitlines() if l.strip()]
        if lines:
            found.append(Evidence(DRIP, "%s has %d live post(s)" % (PUBLISHED_LOG, len(lines))))

    video = advocacy / VIDEO_SCRIPT
    if video.is_file():
        for url in published_urls(_read(video)):
            found.append(Evidence(VIDEO, "%s published: %s" % (VIDEO_SCRIPT, url)))

    ledger = repo / LEDGER
    if ledger.is_file():
        reviewed = review_date(_read(ledger))
        if reviewed and day0 is not None:
            _, due = campaign_dates(day0)
            if reviewed >= due:
                found.append(Evidence(REVIEW_TITLE, "%s has a review entry dated %s, due %s"
                                      % (LEDGER, reviewed, due)))
            else:
                unmatched.append("%s review entry dated %s is before the due date %s"
                                 % (LEDGER, reviewed, due))
        elif reviewed:
            unmatched.append("%s review entry dated %s; pass --day0 to compare "
                             "with the due date" % (LEDGER, reviewed))

    return ordered(found), unmatched


# What counts as a stage having started. Completion always counts too, so a
# stage finished before anyone made its subtask still gets one, ticked.
# Corporate blog has no start signal of its own: the corporate post is an
# edit of the same blog-base.md the personal post comes from, so starting
# one says nothing about whether the other will happen. It gets its subtask
# when a company-blog URL proves it, or by hand the day that edit begins.
_STARTED_STATES = {"drafting", "written", "published"}


def started_from(repo, config_values, day0=None, today=None):
    """Evidence, in stage order, for every stage the files show has begun."""
    repo = pathlib.Path(repo)
    advocacy = repo / "advocacy"
    complete, _ = evidence_from(repo, config_values, day0)
    found = list(complete)

    legal = read_signals(repo).legal_doc
    if legal:
        found.append(Evidence(PUBLIC_REPO, "%s exists: the publish check has begun" % legal))

    blog_state = _status(advocacy / CONTENT_FILES[0].path)
    if blog_state in _STARTED_STATES:
        found.append(Evidence(PERSONAL_BLOG, "%s is %s" % (CONTENT_FILES[0].path, blog_state)))

    article_state = _status(advocacy / X_ARTICLE)
    if article_state in _STARTED_STATES:
        found.append(Evidence(X_ARTICLE_LIVE, "%s is %s" % (X_ARTICLE, article_state)))

    drips = drip_states(repo)
    if drips:
        found.append(Evidence(DRIP, "%s/%s exists" % (DRIPS_DIR, sorted(drips)[0])))

    video_state = _status(advocacy / VIDEO_SCRIPT)
    if video_state in _STARTED_STATES:
        found.append(Evidence(VIDEO, "%s is %s" % (VIDEO_SCRIPT, video_state)))

    if day0 is not None and today is not None:
        _, due = campaign_dates(day0)
        if today >= due:
            found.append(Evidence(REVIEW_TITLE, "day 90 (%s) has arrived" % due))

    return ordered(found)


def to_create(started, existing_titles, day0=None):
    """The started stages with no subtask yet, as rows to create in order.
    Never a stage that has not started, and never a delete."""
    plan = reconcile([task_by_title(e.task) for e in started], existing_titles)
    rows = []
    for task in plan.create:
        due = due_on(task, day0) if day0 else None
        rows.append({"title": task.title, "note": task.note,
                     "due_on": due.isoformat() if due else None})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Print which stages the files show started and which "
                    "they prove complete. Reads only; creating and ticking "
                    "subtasks under the parent task is the caller's.")
    parser.add_argument("--repo", required=True, help="The project's working repo.")
    parser.add_argument("--day0", help="Day 0, YYYY-MM-DD, from the parent task's start_on. "
                                       "Needed only to judge the 90 day review.")
    parser.add_argument("--today", help="YYYY-MM-DD. Defaults to the real date; "
                                        "the review starts on day 90.")
    parser.add_argument("--existing-titles-file", dest="existing_titles_file",
                        help="The parent task's current subtask titles, one per "
                             "line. Adds `create`: started stages with no subtask.")
    parser.add_argument("--config", help="Override ~/.claude/advocacy-workflow.yml.")
    args = parser.parse_args(argv)

    repo = pathlib.Path(args.repo).expanduser().resolve()
    if not (repo / "advocacy").is_dir():
        print("%s has no advocacy/ directory; run intake first" % repo, file=sys.stderr)
        return 2
    day0 = dt.date.fromisoformat(args.day0) if args.day0 else None
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    cfg = machine_config.with_defaults(machine_config.load(args.config))
    tracking = read_tracking(repo)
    migrate = migration_message(tracking)
    if migrate:
        print("sync: %s" % migrate, file=sys.stderr)
    complete, unmatched = evidence_from(repo, cfg, day0)
    started = started_from(repo, cfg, day0, today)
    out = {
        "tracking": dict(tracking._asdict(), migrate=migrate),
        "started": [item._asdict() for item in started],
        "complete": [item._asdict() for item in complete],
        "unmatched": unmatched,
        "tasks": list(TITLES),
        "files": file_states(repo),
        "drips": drip_states(repo),
    }
    if args.existing_titles_file:
        titles_path = pathlib.Path(args.existing_titles_file)
        if not titles_path.is_file():
            raise ValueError("no such existing-titles file: %s" % titles_path)
        existing = [line.strip() for line in titles_path.read_text().splitlines()
                    if line.strip()]
        out["create"] = to_create(started, existing, day0)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
