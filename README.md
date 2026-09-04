# advocacy-workflow

A Claude Code plugin. Turns a project you have finished into a content campaign, and tracks the
whole thing in Asana.

One build becomes two blog posts, five canonical derivatives, twenty style variants and four
videos, through four review gates that are all yours.

Employer-agnostic on purpose. No skill names a company. The one product dependency is the video
renderer, which calls Deepgram for speech synthesis and word timings.

## Requires project-workflow

This plugin does not create repositories, Asana projects, or build ledgers.
[project-workflow](https://github.com/samgutentag-deepgram/project-workflow) owns those, along with
the `.hub/ledger.md` build record that every draft here is sourced from, and every skill here refuses
to run without it.

```
/plugin marketplace add samgutentag-deepgram/project-workflow
/plugin install project-workflow@project-workflow
```

## Install

This repo is both the plugin and its own marketplace.

```
/plugin marketplace add samgutentag-deepgram/advocacy-workflow
/plugin install advocacy-workflow@advocacy-workflow
```

Start a new Claude Code session afterwards. Skills load at session start.

## First run

The first advocacy command you run checks `~/.claude/advocacy-workflow.yml`, and interviews you if
anything is missing. Four settings, one of which is your Asana workspace gid. Nothing has to be
created in Asana by hand before you start.

```bash
PLUGIN=$(ls -d ~/.claude/plugins/cache/advocacy-workflow/advocacy-workflow/*/ | tail -1)
python3 "$PLUGIN/skills/advocacy-intake/scripts/config.py" --missing
```

Exits non-zero while anything is unanswered.

## The skills

| Skill | Runs | Produces |
|---|---|---|
| `advocacy-intake` | Once, when you decide a project is content | `advocacy/advocacy.md`, and gates A and B on the board |
| `advocacy-cycle` | Repeatedly, after the build is done | the `advocacy/content/` tree, gates C and D, and the drafts |
| `script-to-video` | From an approved video script | narrated placeholder videos to re-record against |
| `personal-style` | Drafting in an advocate's own voice | prose |
| `corporate-style` | Drafting in the company voice | prose |
| `de-slop` | Before every gate | the machine fingerprints taken out |

## The gates

```
notes.md          every fact, cited, out of the build ledger
  two blogs                                     GATE A
    five canonicals                             GATE B
      twenty style variants                     GATE C
        four horizontal base layers             GATE D
```

**Nothing derives from an unapproved parent, at any level.** You pass a gate by completing its task
in Asana. Asana is the source of truth for gate state; the files carry a dated cache of it and
never the reverse.

## Your own voice

`personal-style` and `corporate-style` ship here and are written to work for anyone. If you have
your own voice skill, name it in `voice_personal` and it is used instead. That field is also how you
ghostwrite for somebody else: point it at their voice skill.

## Full guide

[`docs/user-guide.html`](docs/user-guide.html) is the read-cold version: every command, every Asana
action, and every file that lands where, from an empty folder through the public flip. Open it in a
browser.

## Tests

```bash
cd skills/advocacy-intake && python3 -m pytest -q     # 109
cd skills/advocacy-cycle  && python3 -m pytest -q     #  71
```

The interesting half is pure functions over data, so it tests without an Asana token and without a
repo full of drafts.
