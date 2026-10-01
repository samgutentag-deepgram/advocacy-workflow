"""Pure core for advocacy-intake.

Every function here takes data and returns data. No network, no environment,
no writes. That is what makes the interesting half testable without an Asana
token and without a real repository.

The model is deliberately small. Every promoted campaign gets one Asana
project with the same seven flat tasks, no sections, no subtasks. Ticking a
task is both the approval and the record. Status comes from files, and Asana
is updated from files in one direction (see advocacy-cycle's sync.py).
"""
from __future__ import annotations

from collections import namedtuple
import datetime as dt
import os
import pathlib
import re

Signals = namedtuple(
    "Signals",
    "ledger_entries has_deploy capture_plan legal_doc has_license has_content "
    "public_repo",
)

# Dockerfile and Procfile describe how to run a thing, not that a live,
# reader-reachable deploy exists; a Pi on a bench can have either. Only these
# four name an actual hosted target.
_DEPLOY_MARKERS = ("fly.toml", "vercel.json", "netlify.toml", "render.yaml")

# A doc whose whole job is "can we publish this yet".
_LEGAL_MARKERS = ("docs/legal.md", "LEGAL.md", "docs/compliance.md",
                  "docs/approval.md")

HUB_YML = pathlib.PurePosixPath(".hub", "hub.yml")

# A top-level `public_repo:` line in hub.yml. Anchored at column 0 so a
# commented-out or indented mention does not count: one real hub.yml carries
# a comment explaining why it deliberately has no public_repo key.
_PUBLIC_REPO = re.compile(r"^public_repo:[ \t]*(\S.*)$", re.MULTILINE)


def _has_content(root):
    """True if the repository holds at least one file outside .git.

    Stops at the first file found rather than walking the whole tree, so a
    large repository does not pay for this check. A `git init` with zero
    commits and zero files is the case this exists for: git-repo-shaped, but
    nothing has been built yet.
    """
    for _, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        if filenames:
            return True
    return False


def public_repo_in(hub_text):
    """The `public_repo:` value in a hub.yml, or None. Quotes stripped."""
    match = _PUBLIC_REPO.search(hub_text)
    if not match:
        return None
    value = match.group(1).split(" #", 1)[0].strip().strip('"').strip("'")
    return value or None


def read_public_repo(repo_path):
    """The public twin's URL from .hub/hub.yml, or None if the flip has not
    happened. Reads only."""
    hub = pathlib.Path(repo_path) / HUB_YML
    if not hub.is_file():
        return None
    return public_repo_in(hub.read_text(errors="replace"))


def read_signals(repo_path):
    """Inspect a repository and report what is there. Reads only; never writes.

    Raises FileNotFoundError if the path does not exist, rather than returning
    empty signals, because "I found nothing" and "there is nothing there" lead
    to very different conversations.
    """
    root = pathlib.Path(repo_path)
    if not root.is_dir():
        raise FileNotFoundError("no such repository: %s" % root)

    ledger = root / ".hub" / "ledger.md"
    entries = 0
    if ledger.is_file():
        for line in ledger.read_text(errors="replace").splitlines():
            if line.startswith("### ["):
                entries += 1

    capture = None
    for candidate in (".hub/capture-plan.md", "docs/capture-plan.md"):
        if (root / candidate).is_file():
            capture = candidate
            break

    legal = None
    for candidate in _LEGAL_MARKERS:
        if (root / candidate).is_file():
            legal = candidate
            break

    has_deploy = any((root / m).exists() for m in _DEPLOY_MARKERS)
    has_license = any((root / n).is_file()
                      for n in ("LICENSE", "LICENSE.md", "LICENSE.txt"))

    return Signals(
        ledger_entries=entries,
        has_deploy=has_deploy,
        capture_plan=capture,
        legal_doc=legal,
        has_license=has_license,
        has_content=_has_content(root),
        public_repo=read_public_repo(root),
    )


# One task on the board. `note` is the description written onto the Asana
# task at creation: one line saying when to tick it, except the review,
# which carries its five steps. `due_day` is days after day 0, or None: only
# the review carries a date, because everything else is done when it is done
# and a made-up deadline is worse than none.
Task = namedtuple("Task", "title note due_day")

REVIEW_DAY = 90

# THE SEVEN. Same titles, same order, every campaign. Titles are the
# reconcile key: reconcile() matches on title text, so a title changed here
# without being changed in Asana makes every re-run create a duplicate.
SEVEN_TASKS = (
    Task("Public repo",
         "Complete when the public twin exists with a LICENSE and "
         ".hub/hub.yml carries public_repo.", None),
    Task("Personal blog live",
         "Complete when the post is live on the personal blog and "
         "advocacy/content/blog-base.md carries its URL under published:.",
         None),
    Task("Corporate blog live",
         "Complete when the post is live on the company blog and "
         "advocacy/content/blog-base.md carries its URL under published:.",
         None),
    Task("X Article live",
         "Complete when the Article is published from the advocate's handle "
         "and advocacy/content/x-article.md carries its URL under published:.",
         None),
    Task("Drip written and scheduled",
         "Complete when one advocacy/content/drips/*.md has all six posts "
         "written and dated and passes drip.py check.", None),
    Task("Video live",
         "Complete when the video is public and a drip (piece_type: video) "
         "or advocacy/content/video-script.md carries its URL.", None),
    Task("90 day review",
         "90 day review. On or after the due date: (1) pull the Profound "
         "visibility report for this project's topic and compare it with the "
         "day 0 snapshot; (2) read advocacy/content/published.log and the "
         "post stats behind each permalink; (3) note repo traffic and stars; "
         "(4) write five lines in .hub/ledger.md: what moved, what did not, "
         "the one surprising number, keep or close, the next angle if any; "
         "(5) tick this task. Complete when a dated review entry exists in "
         "the ledger.", REVIEW_DAY),
)

REVIEW_TITLE = "90 day review"

TITLES = tuple(t.title for t in SEVEN_TASKS)

# hub init scaffolds this on every exploration. Promoting IS that decision,
# so intake ticks it if it is there and says nothing if it is not.
DECISION_TASK = "Decide: promote or drop"


def task_by_title(title):
    """Look up one of the seven. Raises KeyError on anything else,
    deliberately: a typo must stop the run, not create an eighth task."""
    for task in SEVEN_TASKS:
        if task.title == title:
            return task
    raise KeyError(title)


def build_tasks(signals):
    """The seven, for a repo that has something in it.

    Every caller that wants a task list comes through here, so the
    empty-repo guard lives at this choke point rather than in any one caller.
    """
    if not signals.has_content:
        raise ValueError(
            "repo is empty: no files found outside .git. There is nothing "
            "to build a campaign around yet."
        )
    return list(SEVEN_TASKS)


def due_on(task, day0):
    """The task's due date given day 0, or None for the six undated ones."""
    if task.due_day is None:
        return None
    return day0 + dt.timedelta(days=task.due_day)


def campaign_dates(day0):
    """(start_on, due_on) for the project itself: day 0 to day 90."""
    return day0, day0 + dt.timedelta(days=REVIEW_DAY)


Plan = namedtuple("Plan", "create keep untouched")


def reconcile(desired_tasks, existing_titles):
    """Work out what to create, given what the project already holds.

    There is deliberately no delete list and there never will be. People add
    tasks to Asana as they occur to them during the build, and a task they
    typed is the same kind of thing as a task this generated. Anything
    unrecognized is reported as untouched, not as drift.
    """
    existing = set(existing_titles)
    create = [t for t in desired_tasks if t.title not in existing]
    keep = [t.title for t in desired_tasks if t.title in existing]
    desired_titles = {t.title for t in desired_tasks}
    untouched = [title for title in existing_titles
                 if title not in desired_titles]
    return Plan(create=create, keep=keep, untouched=untouched)


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Thin CLI over intake_core's pure functions. All logic "
                    "lives in the functions above; this block only parses "
                    "arguments, calls them, and prints JSON.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--signals", metavar="REPO",
        help="Print read_signals(REPO) as one JSON object.",
    )
    mode.add_argument(
        "--tasks", metavar="REPO",
        help="Print the seven tasks as a JSON array. With --day0, each "
             "carries its due_on (null on all but the review).",
    )
    mode.add_argument(
        "--reconcile", metavar="REPO",
        help="Print reconcile(...) as one JSON object with create/keep/"
             "untouched. Requires --existing-titles-file.",
    )
    parser.add_argument(
        "--day0", metavar="YYYY-MM-DD",
        help="Day 0. Adds due_on to each task and start_on/due_on for the "
             "project. Valid with --tasks or --reconcile.",
    )
    parser.add_argument(
        "--existing-titles-file", dest="existing_titles_file", metavar="FILE",
        help="Path to a file holding one existing Asana task title per "
             "line. Required with --reconcile, rejected without it.",
    )

    def _task_json(task, day0):
        row = dict(task._asdict())
        due = due_on(task, day0) if day0 else None
        row["due_on"] = due.isoformat() if due else None
        return row

    args = parser.parse_args()

    if args.existing_titles_file is not None and args.reconcile is None:
        parser.error("--existing-titles-file is only valid together with --reconcile")
    if args.reconcile is not None and args.existing_titles_file is None:
        parser.error("--reconcile requires --existing-titles-file")
    if args.day0 is not None and args.signals is not None:
        parser.error("--day0 is only valid together with --tasks or --reconcile")

    try:
        day0 = dt.date.fromisoformat(args.day0) if args.day0 else None
        if args.signals is not None:
            signals = read_signals(args.signals)
            print(json.dumps(signals._asdict()))
        elif args.tasks is not None:
            tasks = build_tasks(read_signals(args.tasks))
            print(json.dumps([_task_json(t, day0) for t in tasks]))
        else:
            desired = build_tasks(read_signals(args.reconcile))
            titles_path = pathlib.Path(args.existing_titles_file)
            if not titles_path.is_file():
                raise FileNotFoundError(
                    "no such existing-titles file: %s" % titles_path
                )
            existing_titles = [
                line.strip() for line in titles_path.read_text().splitlines()
                if line.strip()
            ]
            plan = reconcile(desired, existing_titles)
            out = {
                "create": [_task_json(t, day0) for t in plan.create],
                "keep": plan.keep,
                "untouched": plan.untouched,
                "decision_task": (DECISION_TASK
                                  if DECISION_TASK in existing_titles else None),
            }
            if day0:
                start, due = campaign_dates(day0)
                out["project"] = {"start_on": start.isoformat(),
                                  "due_on": due.isoformat()}
            print(json.dumps(out))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print("intake_core: %s" % exc, file=sys.stderr)
        sys.exit(1)
