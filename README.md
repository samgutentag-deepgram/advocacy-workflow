# advocacy-workflow

A Claude Code plugin. Turns a project you have finished into a content campaign, and tracks the
whole thing as one parent task on a shared Asana board, with a subtask per stage once that stage
starts.

One build becomes a base post, six archetype takes, twelve social posts, a drip per shipped piece,
and a video. The board records what went live, and the files are what tick it.

Employer-agnostic on purpose. No skill names a company. The one product dependency is the video
renderer, which calls Deepgram for speech synthesis and word timings.

## Requires project-workflow

This plugin does not create repositories, Asana projects, or build ledgers. In Asana it creates one
parent task per campaign on a board you name, and subtasks under it as work starts.
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
anything is missing. Six settings: your Asana workspace gid, the home board every campaign lives on
(usually your team's advocacy board) and optionally a section on it, plus three that default. The
board has to exist already; nothing else has to be created in Asana by hand.

```bash
PLUGIN=$(ls -d ~/.claude/plugins/cache/advocacy-workflow/advocacy-workflow/*/ | tail -1)
python3 "$PLUGIN/skills/advocacy-intake/scripts/config.py" --missing
```

Exits non-zero while anything is unanswered.

## The skills

| Skill | Runs | Produces |
|---|---|---|
| `advocacy-intake` | Once, when you decide a project is content | `advocacy/advocacy.md`, day 0, and the campaign's parent task |
| `advocacy-cycle` | Repeatedly, after the build is done | `advocacy/notes.md`, the `advocacy/content/` files, the drips, and the stage subtasks and their ticks |
| `script-to-video` | From a video script | narrated placeholder videos to re-record against |
| `personal-style` | Drafting in an advocate's own voice | prose |
| `corporate-style` | Drafting in the company voice | prose |
| `de-slop` | Before every handover | the machine fingerprints taken out |
| `x-article` | When an approved draft ships as an X Article | the X-ready draft, its paste page and 5:2 cover, the blog mirror, and a 10 to 15 post series with a schedule |
| `last-looks` | Right before anything ships or posts | de-slop and the voice pass, then every mechanical check (numbers, links, UTMs, images, limits, the video standard), one finding per line and a verdict per file |

## One parent task, seven possible stages

Every promoted campaign is one task on the shared home board, never a project of its own. Under it
go at most seven stage subtasks, with these titles, in this order:

```
Public repo
Personal blog live
Corporate blog live
X Article live
Drip written and scheduled
Video live
90 day review          the only one with a due date: day 0 plus 90
```

A stage subtask is created only when the files show that stage started: a blog in draft, a drip
file, a legal doc, day 90 arriving. No placeholders, no dates on work nobody has begun. Ticking a
subtask is both the approval and the record. Explorations have no parent task. Status comes from
the files, and `advocacy-cycle sync` updates the board from them in one direction: `public_repo` in
`hub.yml`, a `published:` URL in a content file, a drip with six written posts, a dated review entry
in the ledger. Nothing is ever unticked or deleted by a script.

Campaigns promoted before 0.5.0 point at a per-repo Asana project. `sync` refuses to write to those
and prints the migration steps: make the parent task, move started work under it, archive the old
project, and repoint `advocacy.md` with `write_advocacy.py --set-asana-url`.

## Your own voice

`personal-style` and `corporate-style` ship here and are written to work for anyone. If you have
your own voice skill, name it in `voice_personal` and it is used instead. That field is also how you
ghostwrite for somebody else: point it at their voice skill.

## Full guide

[`docs/user-guide.html`](docs/user-guide.html) is the read-cold version: the parent task and its stages, the happy
path with one command per step, the archetypes, the file layout, the settings, and the rules.

## Tests

```bash
python3 -m pytest -q     # every skill, from the repo root
```

The interesting half is pure functions over data, so it tests without an Asana token and without a
repo full of drafts.
