---
name: advocacy-intake
description: Promote a repository you already have into an advocacy campaign. Reads the repo cold, writes advocacy/advocacy.md with one falsifiable claim and the reader, sets day 0 on the repo's existing Asana project, and creates the same seven flat tasks every campaign gets. Use when the user says "make a campaign out of this", "this should be content", "run intake on this repo", or runs /advocacy-intake. Does NOT create repositories, does NOT create Asana projects, and does NOT write build ledgers; project-hub owns those.
---

# Advocacy intake

Every promoted campaign has one Asana project with exactly seven flat tasks,
no sections, no subtasks, created in this order with these exact titles:

1. Public repo
2. Personal blog live
3. Corporate blog live
4. X Article live
5. Drip written and scheduled
6. Video live
7. 90 day review (the only task with a due date: day 0 plus 90)

Ticking a task is both the approval and the record. Explorations have zero
tasks. Status comes from files; Asana is updated from files, one direction,
and never by hand except ticking. The table is `SEVEN_TASKS` in
`scripts/intake_core.py`, and `advocacy-cycle` imports it rather than
carrying its own.

## First run: set up this machine

Before any verb, run `config.py --missing` (the scripts live at
`${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/`). The config is
`~/.claude/advocacy-workflow.yml`, one person's Asana and writing setup. If
anything is missing, interview before doing what was asked, then continue:
one question at a time, in `FIELDS` order, saying each field's `how`. The
one Asana fact is the workspace gid; read it back with the Asana tools and
write the file with `config.render()`. `lab_root`, `voice_personal` and
`voice_corporate` default and are confirmed, not asked.

Also check `project-hub` is installed. If `/project-hub` is not available,
say so and point at `/plugin install project-workflow@project-workflow`.

## Related skills

- **project-hub** owns `.hub/`, the ledger, and the Asana project itself.
  `project-hub init` creates the project and writes its gid and URL into
  `.hub/hub.yml` under `asana:`. This skill reads that and never creates a
  project of its own.
- **advocacy-cycle** produces the content and owns `scripts/sync.py`, which
  ticks the seven from the files. Step 5 runs it, so the pre-completion
  rules exist in one place.

## Invocation

```
/advocacy-intake            # cwd, resolved to the git root
/advocacy-intake <path>     # from anywhere
```

Resolve with `git rev-parse --show-toplevel`. If cwd is not a git repo and
no path was given, refuse and say so. Never guess.

**Before touching anything, echo what you resolved and wait for a yes:**

```
repo:     <absolute path>
branch:   <branch>, <clean|N changes>
will:     promote 1 existing Asana project, write 1 advocacy/ directory
nothing happens until you confirm.
```

A no-argument invocation is how the wrong repo gets promoted. This
confirmation is the guard that makes the convenient form safe.

## Steps

### 1. Read the repo

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/intake_core.py --signals <repo>
```

**If `has_content` is false, stop.** The repo is git-initialized but holds
no files outside `.git`. Say plainly that there is nothing to advocate for
yet and that intake runs after something has been built. Do not write
`advocacy/`, do not touch Asana.

Then read what a script cannot judge: the README's claim, the ledger's best
entries, which numbers are measured and sourced. `legal_doc` and
`has_license` tell you what stands between the repo and "Public repo";
`public_repo` tells you the flip already happened.

### 2. Freeze the claim and write the file

**If `advocacy/advocacy.md` exists, this is a re-run. Skip to step 3.**
`write_advocacy.py` refuses to overwrite, and that refusal is correct.

The claim must be falsifiable. If you cannot name two ways it could turn out
false, it is a description, not a claim, and intake stops here. Name the
reader in one sentence.

Read the Asana URL from `.hub/hub.yml`'s `asana.url`. If `hub.yml` has no
`asana` key, stop: this repo has no Asana project yet, `/project-hub init`
creates one, run that first.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/write_advocacy.py --repo <repo> \
  --project <slug> --claim "<the frozen, falsifiable claim>" \
  --reader "<who this is for>" --asana-url <the URL from hub.yml>
```

### 3. Set day 0

Read the project's `start_on` with the Asana tools. **If it has a value,
that is day 0, it is frozen, and you keep it.** Say what it is and move on.
Moving day 0 re-dates the review underneath whoever is watching the board;
if it genuinely must move, that is a deliberate edit in Asana, not a re-run.

Only when `start_on` is empty: **day 0 defaults to today, and you say so.**
Look at the git history and the ledger first. Ask, with `AskUserQuestion`
and concrete dated options, only when the repo makes today obviously wrong:
a demo built and shipped weeks ago, a README naming a launch slot, a ledger
whose last entry is months old. Otherwise do not force a question the
evidence already answered.

Then set the project's `start_on` (day 0) and `due_on` (day 0 plus 90) in
one `update_project` call. Asana rejects a `start_on` later than the current
`due_on`, so sending both together avoids the ordering trap.

### 4. Create the seven tasks

Fetch the project's existing task titles, write them one per line to a temp
file, and reconcile:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/intake_core.py --reconcile <repo> \
  --existing-titles-file <temp file> --day0 <YYYY-MM-DD>
```

Create every task under `create`, in order, with exactly the `title` the
script returned, `note` as the description, and `due_on` where it is not
null (only the review). No sections, no subtasks, no dependencies. Leave
`keep` alone. Leave `untouched` alone completely: hub init's tasks and
anything the user typed are the same kind of thing as these, and
`reconcile` has no delete list on purpose.

Re-running is safe and creates only what is missing, matched on title. A
task renamed in Asana does not stick: the original title is recreated.

If `decision_task` is not null, mark that task (`Decide: promote or drop`)
complete. Promoting is that decision. If it is null, say nothing.

### 5. Sync from files

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-cycle/scripts/sync.py --repo <repo> --day0 <YYYY-MM-DD>
```

Complete every task named under `complete` that is still open: `Public
repo` when `hub.yml` carries `public_repo`, `Personal blog live` or
`Corporate blog live` when `advocacy/content/blog-base.md` already has a
`published:` URL, and so on. Never un-complete anything. Report `unmatched`
rather than guessing which blog a URL belongs to.

### 6. Report

Say what was promoted, which of the seven were created versus already
there, which were pre-completed and from what evidence, what day 0 is and
how it was chosen, and the project's `start_on` and `due_on`. **Then tell
the user to add the project to the `Sam :: Advocacy` portfolio by hand.** No
MCP tool does it.

## Rules

- **Never write to `.hub/`.** That is project-hub's.
- **Never remove or flag a task you did not create.**
- **Never create an eighth task.** A new kind of work is a tick on one of
  the seven or it is not tracked here.
- **The claim is frozen** once `advocacy.md` is written. **Day 0 is frozen**
  once `start_on` is set.
- **Dates are set at promotion, never at exploration.** An undated project
  is an exploration and a dated one is a campaign. That is the whole signal.
- No em dashes. American English. Prose follows the configured voice skill.
