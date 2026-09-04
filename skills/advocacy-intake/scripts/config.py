"""Machine-level configuration for the advocacy workflow.

Everything in here is a fact about ONE person's Asana workspace and writing
setup, not about any one project. It is asked once per machine and reused by
every campaign, which is why it does not live in a repo.

Pure: parsing, validating and rendering are functions over strings. The
interview that fills it in is procedure and belongs in SKILL.md, because the
questions need a human.
"""
from __future__ import annotations

from collections import namedtuple
import os
import pathlib
import re

CONFIG_PATH = "~/.claude/advocacy-workflow.yml"

Field = namedtuple("Field", "key label how")

# Flat on purpose. A nested schema would need a real YAML parser, and this
# skill has no build step to install one into; the frontmatter parser made the
# same trade for the same reason.
FIELDS = (
    Field("asana_workspace", "Asana workspace gid",
          "Ask Claude to list your Asana workspaces. There is usually one."),
    Field("lab_root", "Where lab repos live",
          "The directory holding private working repos. ~/LABS by "
          "convention. Every repo under it is named <thing>-lab."),
    Field("voice_personal", "Personal voice skill",
          "The installed skill that writes in your own voice. "
          "`personal-style` ships with this plugin and is advocate-agnostic; "
          "name your own instead if you have one."),
    Field("voice_corporate", "Corporate voice skill",
          "The installed skill that writes in the company voice. "
          "`corporate-style` ships with this plugin."),
)

_BY_KEY = {f.key: f for f in FIELDS}

DEFAULTS = {
    "lab_root": "~/LABS",
    "voice_personal": "personal-style",
    "voice_corporate": "corporate-style",
}

_LINE = re.compile(r"^([a-z_]+):\s*(.*)$")


def parse(text):
    """Config text to a dict. Comments and blank lines ignored.

    Unknown keys are kept rather than dropped: a newer version of this plugin
    may have written something this one does not know about, and silently
    deleting it on the next save would be worse than carrying it.
    """
    out = {}
    for line in text.split("\n"):
        line = line.split("#", 1)[0].rstrip() if line.lstrip().startswith("#") else line
        m = _LINE.match(line.rstrip())
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def render(values):
    """A dict back to config text, with the guidance kept as comments.

    Known fields come first and in FIELDS order so the file reads the same
    way every time; anything else is appended rather than lost.
    """
    lines = ["# advocacy-workflow. One machine, one person, every campaign.",
             "# Written by the first-run interview. Safe to edit by hand.", ""]
    for f in FIELDS:
        lines.append("# %s" % f.label)
        lines.append('%s: "%s"' % (f.key, values.get(f.key, "")))
        lines.append("")
    extra = sorted(k for k in values if k not in _BY_KEY)
    if extra:
        lines.append("# Not written by this version.")
        for k in extra:
            lines.append('%s: "%s"' % (k, values[k]))
        lines.append("")
    return "\n".join(lines)


def missing(values):
    """The fields still needing an answer, in the order to ask them.

    A field present but empty counts as missing: the interview writes the
    whole file at once, so an empty value means it was skipped, not that
    somebody meant blank.
    """
    return [f for f in FIELDS if not (values or {}).get(f.key, "").strip()]


def with_defaults(values):
    """Fill what can be defaulted so the interview only asks what it must."""
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (values or {}).items() if str(v).strip()})
    return out


def config_path(override=None):
    return pathlib.Path(os.path.expanduser(override or CONFIG_PATH))


def load(override=None):
    """Read the config, or an empty dict if it has never been written."""
    p = config_path(override)
    return parse(p.read_text()) if p.exists() else {}


def lab_path(values, name):
    """Where a lab repo for `name` belongs.

    Appends the `-lab` suffix if it is not already there. A repo without it
    is one somebody publishes by accident, and that is the whole reason the
    convention exists.
    """
    root = pathlib.Path(os.path.expanduser(
        (values or {}).get("lab_root") or DEFAULTS["lab_root"]))
    slug = name if name.endswith("-lab") else "%s-lab" % name
    return root / slug


if __name__ == "__main__":
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        description="Read or check the machine-level advocacy config. All "
                    "logic is in the functions above; this only prints.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--show", action="store_true",
                      help="Print the config as JSON, defaults applied.")
    mode.add_argument("--missing", action="store_true",
                      help="Print the fields still needing an answer, with "
                           "where to find each. Exit 1 if any are missing, so "
                           "a caller can gate on it.")
    mode.add_argument("--path", action="store_true",
                      help="Print where the config file lives.")
    parser.add_argument("--config", help="Override the config path.")
    args = parser.parse_args()

    if args.path:
        print(config_path(args.config))
        raise SystemExit(0)

    values = with_defaults(load(args.config))
    if args.show:
        print(json.dumps(values, indent=2, sort_keys=True))
        raise SystemExit(0)

    gaps = missing(values)
    for f in gaps:
        print("%s\n    %s\n    %s" % (f.key, f.label, f.how))
    if not gaps:
        print("config complete: %s" % config_path(args.config))
    raise SystemExit(1 if gaps else 0)
