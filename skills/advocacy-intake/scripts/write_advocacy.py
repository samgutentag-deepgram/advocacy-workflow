"""The only module in this skill that creates a file."""
from __future__ import annotations

import pathlib
import re

# Imported, not duplicated. This list used to be a hand-maintained copy of
# intake_core.SURFACES with a comment asking the next person to keep the two
# in sync. That is the arrangement where one copy goes stale and nothing
# catches it: the surface set changed and this file kept validating against
# five keys that no longer existed. One definition, one place.
from intake_core import SURFACES

_VALID_SURFACE_KEYS = tuple(s.key for s in SURFACES)

_TEMPLATE = """# {project} advocacy

**Publish or remove this directory before this repo goes public.** It holds
unpublished drafts, and it is one directory so that removing it is one command.

## The claim

{claim}

## The reader

{reader}

## Surfaces

{surface_lines}

## Where the work is tracked

{asana_url}

Asana holds phase, schedule, progress and every task's brief. This file holds
the claim, and the claim is frozen: it does not change again even if the work
does. If the claim turns out to be wrong, that is a finding worth writing up,
not an edit to make here.
"""

# Written when advocacy.md is created before the Asana project exists. Repo
# first, Asana second: this file records what was decided even if the Asana
# call never happens, and intake fills this line in once the project is real.
_TRACKING_PENDING = (
    "Pending. The Asana project does not exist yet. Intake fills this in "
    "with `write_advocacy.py --set-asana-url` right after it creates the "
    "project."
)

# Matches the tracking value between its header and the fixed paragraph that
# follows it, so --set-asana-url can replace only that line and nothing else
# in the file: not the claim, not the reader, not the surfaces.
_TRACKING_PATTERN = re.compile(
    r"(## Where the work is tracked\n\n)(.*?)(\n\nAsana holds phase)",
    re.DOTALL,
)


def render_advocacy_md(project, claim, reader, surfaces, asana_url=None):
    """Render the file. Pure: takes strings, returns a string.

    asana_url is optional because the file is written before the Asana
    project exists (repo first, Asana second, so a failed run still leaves
    a repo that knows what it decided). Omit it to render the pending
    tracking line; fill it in later with set_asana_url.
    """
    surface_lines = "\n".join("- `%s`" % s for s in surfaces)
    tracking = asana_url if asana_url else _TRACKING_PENDING
    return _TEMPLATE.format(
        project=project,
        claim=claim,
        reader=reader,
        surface_lines=surface_lines,
        asana_url=tracking,
    )


def set_asana_url(text, url):
    """Rewrite only the tracking section of an already-rendered file.

    Pure: takes the file's text and the new URL, returns new text. Never
    touches the claim, the reader, or the surfaces; the claim is frozen and
    that does not bend for this update either. Raises ValueError if there is
    no tracking section to update, rather than appending one blindly.
    """
    match = _TRACKING_PATTERN.search(text)
    if not match:
        raise ValueError(
            "no tracking section found in this file; refusing to append one"
        )
    return text[:match.start(2)] + url + text[match.end(2):]


def write_advocacy(repo_path, text):
    """Create advocacy/advocacy.md under repo_path.

    Refuses to overwrite. The claim is frozen once written, so clobbering it
    on a re-run would silently destroy the one thing this file exists to hold.
    """
    root = pathlib.Path(repo_path)
    target = root / "advocacy" / "advocacy.md"
    if target.exists():
        raise FileExistsError(
            "%s already exists. The claim is frozen; edit it by hand if it "
            "genuinely must change." % target
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def update_asana_url(repo_path, url):
    """Rewrite only the tracking section of an existing advocacy/advocacy.md.

    Never creates the file: this is an update to a claim already frozen by
    write_advocacy, not a second way to create one. Raises FileNotFoundError
    if the file does not exist, and propagates set_asana_url's ValueError if
    the file exists but has no tracking section to update.
    """
    root = pathlib.Path(repo_path)
    target = root / "advocacy" / "advocacy.md"
    if not target.is_file():
        raise FileNotFoundError(
            "%s does not exist. --set-asana-url only updates a file that "
            "write_advocacy.py already created; it does not create one." % target
        )
    text = target.read_text()
    updated = set_asana_url(text, url)
    target.write_text(updated)
    return target


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Thin CLI over write_advocacy's pure functions. All "
                     "logic lives in render_advocacy_md, set_asana_url, "
                     "write_advocacy, and update_asana_url; this block only "
                     "parses arguments, calls them, and prints the result.",
    )
    parser.add_argument("--repo", required=True, help="Repo root to write into.")
    parser.add_argument("--project", help="Project name. Create mode only.")
    parser.add_argument("--claim", help="The frozen, falsifiable claim. Create mode only.")
    parser.add_argument("--reader", help="Who this is for. Create mode only.")
    parser.add_argument(
        "--surfaces", metavar="a,b,c",
        help="Comma-separated surface keys that were kept. Create mode only.",
    )
    parser.add_argument(
        "--asana-url", dest="asana_url",
        help="URL of the Asana project, if it already exists. Create mode "
             "only; optional there, because the project usually does not "
             "exist yet when this file is written.",
    )
    parser.add_argument(
        "--set-asana-url", dest="set_asana_url", metavar="URL",
        help="Update mode: rewrite only the tracking section of an existing "
             "advocacy/advocacy.md. Mutually exclusive with every create-mode "
             "flag above.",
    )
    args = parser.parse_args()

    create_flags_used = [
        name for name, value in (
            ("--project", args.project),
            ("--claim", args.claim),
            ("--reader", args.reader),
            ("--surfaces", args.surfaces),
            ("--asana-url", args.asana_url),
        ) if value is not None
    ]

    if args.set_asana_url is not None and create_flags_used:
        parser.error(
            "--set-asana-url cannot be combined with %s"
            % ", ".join(create_flags_used)
        )

    try:
        if args.set_asana_url is not None:
            target = update_asana_url(args.repo, args.set_asana_url)
            print(str(target.resolve()))
        else:
            missing = [name for name, value in (
                ("--project", args.project),
                ("--claim", args.claim),
                ("--reader", args.reader),
                ("--surfaces", args.surfaces),
            ) if value is None]
            if missing:
                parser.error(
                    "the following arguments are required: %s"
                    % ", ".join(missing)
                )
            surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
            unknown = [s for s in surfaces if s not in _VALID_SURFACE_KEYS]
            if unknown:
                raise ValueError(
                    "unknown surface key(s): %s" % ", ".join(unknown)
                )
            text = render_advocacy_md(
                project=args.project,
                claim=args.claim,
                reader=args.reader,
                surfaces=surfaces,
                asana_url=args.asana_url,
            )
            target = write_advocacy(args.repo, text)
            print(str(target.resolve()))
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print("write_advocacy: %s" % exc, file=sys.stderr)
        sys.exit(1)
