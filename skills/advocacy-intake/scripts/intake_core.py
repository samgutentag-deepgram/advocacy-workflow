"""Pure core for advocacy-intake.

Every function here takes data and returns data. No network, no environment,
no writes. That is what makes the interesting half testable without an Asana
token and without a real repository.
"""
from __future__ import annotations

from collections import namedtuple
import os
import pathlib

Surface = namedtuple(
    "Surface", "key label branch kind limit_kind limit needs_capture")

# The surfaces a campaign can earn, across two branches. Not every campaign
# earns every one, and declining is a first-class outcome rather than an
# omission.
#
# `branch` is "personal" or "corporate". They are peers and run the same
# length, with exactly one asymmetry: video derives from the personal blog
# only, because those go to the advocate's own channels.
#
# `kind` is "blog" or "derivative". A blog is a source and has no style
# variants, because the variants ultimately come from it. Every derivative
# fans out to all four styles.
SURFACES = (
    Surface("personal_blog",         "Personal blog",         "personal",  "blog",       "words",   1200, False),
    Surface("personal_thread",       "Personal thread",       "personal",  "derivative", "chars",    280, False),
    Surface("personal_linkedin",     "Personal LinkedIn",     "personal",  "derivative", "chars",   3000, False),
    Surface("personal_video_script", "Personal video script", "personal",  "derivative", "minutes",   15, True),
    Surface("corporate_blog",        "Corporate blog",        "corporate", "blog",       "words",   1500, False),
    Surface("corporate_thread",      "Corporate thread",      "corporate", "derivative", "chars",    280, False),
    Surface("corporate_linkedin",    "Corporate LinkedIn",    "corporate", "derivative", "chars",   3000, False),
)

# All four, on every derivative, every time. There is no picking a style per
# surface.
#
# These strings are the `key` field in the frontmatter of each file under
# claude-code/skills/core/script-to-video/styles/, verbatim, and they are
# also the filename suffix a variant carries on disk. One name per style
# everywhere: a second naming system would be the one that drifts, and a
# fifth style needs no mapping updated here or anywhere else.
STYLES = ("technical", "build-it-too", "fun", "user-demo")

_BY_KEY = {s.key: s for s in SURFACES}


def surface_by_key(key):
    """Look up a Surface. Raises KeyError on an unknown key, deliberately:
    a typo in a surface name should stop the run, not silently drop a
    deliverable."""
    return _BY_KEY[key]


def blog_of(branch):
    """The blog surface key for a branch.

    Every derivative on a branch projects from that branch's blog, so this
    is how a derivative finds the parent it is not allowed to run ahead of.
    """
    return "%s_blog" % branch


Signals = namedtuple(
    "Signals",
    "ledger_entries has_deploy capture_plan gate_doc has_license has_content",
)

# A deploy target means the "make the live thing solid" prep task applies.
# A Pi on a bench has none of these and should not get that task.
# Dockerfile and Procfile describe how to run a thing, not that a live,
# reader-reachable deploy exists; a Pi on a bench can have either. Only these
# four name an actual hosted target.
_DEPLOY_MARKERS = ("fly.toml", "vercel.json", "netlify.toml", "render.yaml")

# A doc whose whole job is "can we publish this yet".
_GATE_MARKERS = ("docs/legal.md", "LEGAL.md", "docs/compliance.md",
                 "docs/approval.md")


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


def read_signals(repo_path):
    """Inspect a repository and report what is there. Reads only; never writes.

    Raises FileNotFoundError if the path does not exist, rather than returning
    empty signals, because "I found nothing" and "there is nothing there" lead
    to very different task lists.
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

    gate = None
    for candidate in _GATE_MARKERS:
        if (root / candidate).is_file():
            gate = candidate
            break

    has_deploy = any((root / m).exists() for m in _DEPLOY_MARKERS)
    has_license = any((root / n).is_file()
                      for n in ("LICENSE", "LICENSE.md", "LICENSE.txt"))

    return Signals(
        ledger_entries=entries,
        has_deploy=has_deploy,
        capture_plan=capture,
        gate_doc=gate,
        has_license=has_license,
        has_content=_has_content(root),
    )


PrepTask = namedtuple("PrepTask", "key title why")


def derive_spine(signals):
    """Turn signals into the preparation tasks this specific repo needs.

    Deliberately not a fixed list. A Pi on a bench has nothing to "make
    solid", and a repo that already has a capture plan should have it linked
    rather than be asked to write a second one.
    """
    spine = []

    # 1. The publishing gate(s), whatever they turn out to be here. A repo
    # can carry both an internal legal-review gate and a missing LICENSE at
    # the same time; each is checked independently so neither silently
    # crowds out the other.
    if signals.gate_doc:
        spine.append(PrepTask(
            "gate_doc",
            "Clear the publishing gate",
            "%s gates anything public. Settle it before a drop is scheduled."
            % signals.gate_doc,
        ))
    if not signals.has_license:
        spine.append(PrepTask(
            "gate",
            "Decide public, and add a LICENSE",
            "No LICENSE file, so the repo reads as private. Every drop that "
            "links the code is blocked until this is decided.",
        ))

    # 2. Make the live thing solid, only if there is a live thing.
    if signals.has_deploy:
        spine.append(PrepTask(
            "solidify",
            "Make the live thing solid",
            "A deploy target exists, so a reader will hit it. Fix what is "
            "broken before pointing anyone at it.",
        ))

    # 3. Numbers, always. Every campaign quotes something.
    spine.append(PrepTask(
        "verify",
        "Verify every number you will quote",
        "Anything without a source cannot go in a draft. Check them once, "
        "here, rather than during the write.",
    ))

    # 4. Capture, always, but link an existing plan rather than duplicating it.
    if signals.capture_plan:
        why = ("Follow %s, which already exists. Do not rewrite it."
               % signals.capture_plan)
    else:
        why = ("No capture plan exists. Write one before the first "
               "irreversible run, because that run happens once.")
    # Title must match SKILL.md exactly. It is the reconcile key: reconcile()
    # matches on title, so a title here that differs from the one actually
    # created in Asana makes every re-run produce a duplicate. This one is
    # deliberately NOT "capture the first time it works", which is a different
    # job owned by project-hub init: that one is the unrepeatable moment you
    # cannot schedule, this one is the planned session that makes the video.
    spine.append(PrepTask("capture", "Record the campaign footage", why))

    return spine


# One task on the board.
#
# `gate` is the gate this task belongs to ("A".."D"), or None on a prep task.
# It is what groups the board into Asana sections, and it decides which skill
# files the task.
#
# `parent` is the key of the task this one is a subtask of, or None for a
# top-level task. Subtasks exist because Asana subtasks cannot belong to a
# section: twenty loose variant tasks could not be grouped under Gate C, so
# each canonical carries its four as children instead. Depth stops at two.
Task = namedtuple("Task", "key title why depends_on gate parent")
Task.__new__.__defaults__ = ((), None, None)

Gate = namedtuple("Gate", "key label filer drop_day")

# THE SINGLE PLACE GATES ARE DEFINED, and the reason both filers can share
# one table instead of each carrying a copy.
#
# `filer` splits the board by when the work becomes real. advocacy-intake
# files A and B at promotion, because the two blogs and five canonicals are
# knowable the moment a campaign is scoped. advocacy-cycle files C and D on
# its first run, because a style variant of a canonical that does not exist
# yet is not a task, it is a guess.
#
# `drop_day` is counted from day 0, same as the old day map.
GATES = (
    Gate("A", "Gate A: blogs",      "intake",  1),
    Gate("B", "Gate B: canonicals", "intake", 10),
    Gate("C", "Gate C: variants",   "cycle",  30),
    Gate("D", "Gate D: renders",    "cycle",  45),
)

_GATE_BY_KEY = {g.key: g for g in GATES}

# Gate D has no surface of its own: the render batch is one task about four
# variants of one script, not a surface a campaign can decline.
RENDER_KEY = "renders"


def gate_by_key(key):
    """Look up a Gate. Raises KeyError on an unknown key, deliberately."""
    return _GATE_BY_KEY[key]


def gate_task_key(gate_key, surface_key, style=None):
    """The task key for one item. Unique and stable: reconcile maps keys to
    titles, so a key that moves breaks dependency wiring on the next re-run."""
    if style is None:
        return "gate:%s:%s" % (gate_key, surface_key)
    return "gate:%s:%s:%s" % (gate_key, surface_key, style)


def filer_for(task):
    """Which skill files this task.

    Prep tasks carry no gate and belong to intake: the spine is scoped with
    the campaign, not produced by the content cycle.
    """
    gate = _GATE_BY_KEY.get(task.gate)
    return gate.filer if gate else "intake"


def _build_schedule():
    """Every possible task key mapped to (drop_day, offset).

    Built across all surfaces rather than the kept ones, so the table does
    not change shape with the campaign. Offsets are 0 throughout: in the gate
    model each gate IS a drop, so there is nothing to count backwards from.
    """
    out = {}
    for gate in GATES:
        if gate.key == "D":
            out[gate_task_key("D", RENDER_KEY)] = (gate.drop_day, 0)
            for style in STYLES:
                out[gate_task_key("D", RENDER_KEY, style)] = (gate.drop_day, 0)
            continue
        wanted = "blog" if gate.key == "A" else "derivative"
        for surface in SURFACES:
            if surface.kind != wanted:
                continue
            out[gate_task_key(gate.key, surface.key)] = (gate.drop_day, 0)
            if gate.key == "C":
                for style in STYLES:
                    out[gate_task_key("C", surface.key, style)] = (gate.drop_day, 0)
    return out


_SCHEDULE_BY_TASK_KEY = _build_schedule()


def schedule_for(task_key):
    """(drop_day, offset) for a gate task, or None for a prep task.

    The core stays clockless on purpose: it hands out two integers and the
    caller, which knows day 0, does the arithmetic.
    """
    return _SCHEDULE_BY_TASK_KEY.get(task_key)


def build_tasks(signals, kept_surface_keys):
    """The prep spine, then every gate item for the surfaces that were kept.

    The whole graph, both filers' share of it. Slicing by filer is
    reconcile's job, because a dependency has to be resolvable even when the
    task it points at was filed by the other skill.

    Where the spine attaches, and why it is not wired five more times:

    - `gate` and `gate_doc` land on the GATE A blogs only. Everything else
      reaches a blog through the chain, so a legal block on the blog stops
      the branch transitively. Wiring it to every item would say the same
      thing four more times and be four more places to get it wrong.
    - `verify` lands on the Gate A blogs for the same reason, and because the
      blog is where a number appears first. Catching it there is the last
      point before four surfaces repeat it.
    - `capture` lands on the Gate D render batch. Footage exists before the
      camera step, not before the surface.

    Every caller that wants a task graph comes through here, so the
    empty-repo guard lives at this choke point rather than in any one caller.
    """
    if not signals.has_content:
        raise ValueError(
            "repo is empty: no files found outside .git. There is nothing "
            "to build a campaign around yet."
        )
    if not kept_surface_keys:
        raise ValueError(
            "no surfaces kept. A campaign with nothing to ship is not a campaign."
        )

    kept = list(kept_surface_keys)
    for key in kept:
        surface_by_key(key)          # raises on a typo, deliberately

    blogs = [k for k in kept if surface_by_key(k).kind == "blog"]
    derivatives = [k for k in kept if surface_by_key(k).kind == "derivative"]

    # Nothing derives from a parent that is not there. Keeping a thread
    # without its blog is not a smaller campaign, it is a broken one, and it
    # would produce a Gate B task depending on a Gate A task nobody files.
    for key in derivatives:
        branch_blog = blog_of(surface_by_key(key).branch)
        if branch_blog not in blogs:
            raise ValueError(
                "%s was kept but %s was not. A derivative projects from its "
                "branch's blog." % (key, branch_blog)
            )

    spine = derive_spine(signals)
    spine_keys = [t.key for t in spine]
    tasks = [Task(t.key, t.title, t.why, ()) for t in spine]

    gates = [k for k in ("gate", "gate_doc") if k in spine_keys]

    # GATE A. The blogs, and the only place the publishing gates attach.
    for key in blogs:
        surface = surface_by_key(key)
        deps = list(gates)
        if "verify" in spine_keys:
            deps.append("verify")
        tasks.append(Task(
            gate_task_key("A", key),
            "Gate A: %s, edit to publish ready" % surface.label,
            "The source every surface on this branch projects from. Limit is "
            "%s %s, and this is the last point a wrong number comes out "
            "before four other surfaces repeat it."
            % (surface.limit, surface.limit_kind),
            tuple(deps), "A", None,
        ))

    # GATE B. One canonical per derivative, waiting on its branch's blog.
    for key in derivatives:
        surface = surface_by_key(key)
        parent_blog = surface_by_key(blog_of(surface.branch))
        tasks.append(Task(
            gate_task_key("B", key),
            "Gate B: %s, edit to publish ready" % surface.label,
            "Derived from the approved %s. Limit is %s %s, and this is the "
            "last point it can be cut to." % (parent_blog.label,
                                              surface.limit,
                                              surface.limit_kind),
            (gate_task_key("A", blog_of(surface.branch)),), "B", None,
        ))

    # GATE C. The style fan-out, one parent per canonical carrying four
    # children. Parents exist so the gate can be an Asana section at all.
    for key in derivatives:
        surface = surface_by_key(key)
        parent_key = gate_task_key("C", key)
        tasks.append(Task(
            parent_key,
            "Gate C: %s, review %d style variants" % (surface.label,
                                                      len(STYLES)),
            "Staggered long tail reposts of already approved material, so "
            "the edits are light. A style changes framing and never a claim: "
            "a wrong number is wrong in all four and is fixed in the "
            "canonical first.",
            (gate_task_key("B", key),), "C", None,
        ))
        for style in STYLES:
            tasks.append(Task(
                gate_task_key("C", key, style),
                "Gate C: %s, %s variant" % (surface.label, style),
                "The %s take on the approved canonical. Same facts, "
                "different framing." % style,
                (parent_key,), "C", parent_key,
            ))

    # GATE D. Renders, and only if the branch that has video kept it.
    if "personal_video_script" in derivatives:
        parent_key = gate_task_key("D", RENDER_KEY)
        deps = [gate_task_key("C", "personal_video_script")]
        if "capture" in spine_keys:
            deps.append("capture")
        tasks.append(Task(
            parent_key,
            "Gate D: render %d horizontal base layers" % len(STYLES),
            "One per video script variant, horizontal only. Placeholder "
            "timing and a synthetic voice: this is the structure to "
            "re-record against, not a deliverable.",
            tuple(deps), "D", None,
        ))
        for style in STYLES:
            tasks.append(Task(
                gate_task_key("D", RENDER_KEY, style),
                "Gate D: %s base layer" % style,
                "Watch it. Keep the framing or drop it.",
                (parent_key,), "D", parent_key,
            ))

    return tasks


Plan = namedtuple("Plan", "create keep untouched title_by_key")


def reconcile(desired_tasks, existing_titles, filers=None):
    """Work out what to create, given what the project already holds.

    There is deliberately no delete list and there never will be. People add
    tasks to Asana as they occur to them during the build, and a task they typed
    is the same kind of thing as a task this generated. Anything unrecognized
    is reported as untouched, not as drift.

    `filers` restricts what may be CREATED, not what is known. Pass
    ("intake",) at promotion and ("cycle",) from the content cycle. Both
    still receive the full `title_by_key`, because a Gate C task depends on
    a Gate B task the other skill filed, and a dependency that cannot be
    resolved is worse than one that was never wanted: an unwired dependency
    looks exactly like a task that is ready to start.
    """
    existing = set(existing_titles)
    eligible = [t for t in desired_tasks
                if filers is None or filer_for(t) in filers]
    create = [t for t in eligible if t.title not in existing]
    keep = [t.title for t in eligible if t.title in existing]
    desired_titles = {t.title for t in desired_tasks}
    untouched = [title for title in existing_titles
                 if title not in desired_titles]
    # A created task's depends_on holds KEYS, but Asana is addressed by title.
    # Without this map the caller cannot resolve "gate" to the task actually
    # sitting in the project, so it either guesses or silently drops the wire,
    # and an unwired dependency looks exactly like a task that is ready.
    title_by_key = {t.key: t.title for t in desired_tasks}
    return Plan(create=create, keep=keep, untouched=untouched,
                title_by_key=title_by_key)


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
        help="Print build_tasks(...) as a JSON array. Each object carries "
             "drop_day and offset (null on prep tasks) so the caller can "
             "date it. Requires --surfaces.",
    )
    mode.add_argument(
        "--reconcile", metavar="REPO",
        help="Print reconcile(...) as one JSON object with create/keep/"
             "untouched. Requires --surfaces and --existing-titles-file.",
    )
    parser.add_argument(
        "--surfaces", metavar="a,b,c",
        help="Comma-separated surface keys to keep. Required with --tasks "
             "or --reconcile, rejected without either.",
    )
    parser.add_argument(
        "--filer", metavar="intake|cycle",
        help="Restrict --reconcile's create list to one filer's gates. "
             "intake files gates A and B plus the prep spine; cycle files C "
             "and D. Omit to plan the whole board.",
    )
    parser.add_argument(
        "--existing-titles-file", dest="existing_titles_file", metavar="FILE",
        help="Path to a file holding one existing Asana task title per "
             "line. Required with --reconcile, rejected without it.",
    )
    def _task_json(task):
        """One task as JSON, with its schedule attached.

        gate and parent come straight off the task: the caller needs the
        first to pick an Asana section and the second to create a subtask
        under the right parent.

        drop_day and offset ride along rather than living on Task itself.
        Both are null on a prep task: the day map has nothing to say about
        the spine, so those stay undated.
        """
        row = dict(task._asdict())
        schedule = schedule_for(task.key)
        row["drop_day"] = schedule[0] if schedule else None
        row["offset"] = schedule[1] if schedule else None
        return row

    args = parser.parse_args()

    if args.surfaces is not None and args.tasks is None and args.reconcile is None:
        parser.error("--surfaces is only valid together with --tasks or --reconcile")
    if args.tasks is not None and args.surfaces is None:
        parser.error("--tasks requires --surfaces")
    if args.reconcile is not None and args.surfaces is None:
        parser.error("--reconcile requires --surfaces")
    if args.existing_titles_file is not None and args.reconcile is None:
        parser.error("--existing-titles-file is only valid together with --reconcile")
    if args.reconcile is not None and args.existing_titles_file is None:
        parser.error("--reconcile requires --existing-titles-file")

    try:
        if args.signals is not None:
            signals = read_signals(args.signals)
            print(json.dumps(signals._asdict()))
        elif args.tasks is not None:
            surface_keys = [s.strip() for s in args.surfaces.split(",")]
            surface_keys = [s for s in surface_keys if s]
            if not surface_keys:
                raise ValueError(
                    "no surfaces kept. A campaign with nothing to ship is "
                    "not a campaign."
                )
            for key in surface_keys:
                surface_by_key(key)  # raises KeyError on an unknown surface
            signals = read_signals(args.tasks)
            # The empty-repo guard lives in build_tasks itself, not here,
            # so --reconcile (which also calls build_tasks) inherits it too.
            tasks = build_tasks(signals, surface_keys)
            print(json.dumps([_task_json(t) for t in tasks]))
        else:
            surface_keys = [s.strip() for s in args.surfaces.split(",")]
            surface_keys = [s for s in surface_keys if s]
            if not surface_keys:
                raise ValueError(
                    "no surfaces kept. A campaign with nothing to ship is "
                    "not a campaign."
                )
            for key in surface_keys:
                surface_by_key(key)  # raises KeyError on an unknown surface
            signals = read_signals(args.reconcile)
            desired = build_tasks(signals, surface_keys)
            titles_path = pathlib.Path(args.existing_titles_file)
            if not titles_path.is_file():
                raise FileNotFoundError(
                    "no such existing-titles file: %s" % titles_path
                )
            existing_titles = [
                line.strip() for line in titles_path.read_text().splitlines()
                if line.strip()
            ]
            filers = (args.filer,) if args.filer else None
            plan = reconcile(desired, existing_titles, filers=filers)
            # title_by_key is the whole board, not just this filer's share.
            # SKILL.md tells the caller to resolve every depends_on key
            # through it, and a Gate C task depends on a Gate B task the
            # other filer created, so a map scoped to the create list would
            # strand exactly the dependencies that cross the split.
            print(json.dumps({
                "create": [_task_json(t) for t in plan.create],
                "keep": plan.keep,
                "untouched": plan.untouched,
                "title_by_key": plan.title_by_key,
            }))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print("intake_core: %s" % exc, file=sys.stderr)
        sys.exit(1)
