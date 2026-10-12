---
name: advocacy-intake
description: Promote a repository you already have into an advocacy campaign. Reads the repo cold, writes advocacy/advocacy.md with one falsifiable claim and the reader, and finds or creates the campaign's one parent task on the shared home board, dated day 0 to day 90. Stage subtasks come later, one per stage as it starts. Use when the user says "make a campaign out of this", "this should be content", "run intake on this repo", or runs /advocacy-intake. Does NOT create repositories, does NOT create Asana projects, does NOT create placeholder tasks, and does NOT write build ledgers.
---

# Advocacy intake

Every promoted campaign is **one parent task on a shared home board**
(`asana_home_project` in the config, usually the team's advocacy pillar
board), never an Asana project of its own. Boards hold work, not people:
one board per campaign is how a team ends up with forty boards nobody opens.

Under the parent go at most seven stage subtasks, with these exact titles,
in this order:

1. Public repo
2. Personal blog live
3. Corporate blog live
4. X Article live
5. Drip written and scheduled
6. Video live
7. 90 day review (the only task with a due date: day 0 plus 90)

**A stage subtask is created only when its stage starts.** Intake creates
none. `advocacy-cycle`'s `sync` creates each one the first time the files
show that stage begun (a blog in draft, a drip file, a legal doc, day 90
arriving), so the board never holds a placeholder for work nobody has
started. Ticking a subtask is both the approval and the record. Explorations
have no parent task at all. Status comes from files; Asana is updated from
files, one direction, and never by hand except ticking. The table is
`SEVEN_TASKS` in `scripts/intake_core.py`, and `advocacy-cycle` imports it
rather than carrying its own.

## First run: set up this machine

Before any verb, run `config.py --missing` (the scripts live at
`${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/`). The config is
`~/.claude/advocacy-workflow.yml`, one person's Asana and writing setup. If
anything is missing, interview before doing what was asked, then continue:
one question at a time, in `FIELDS` order, saying each field's `how`. The
one Asana fact is the workspace gid; read it back with the Asana tools and
write the file with `config.render()`. The Asana facts are the workspace
gid and the home board (`asana_home_project`, plus an optional
`asana_home_section`); search the projects by name and read the gids back.
`lab_root`, `voice_personal` and `voice_corporate` default and are
confirmed, not asked.

Also check `project-hub` is installed. If `/project-hub` is not available,
say so and point at `/plugin install project-workflow@project-workflow`.

## Related skills

- **project-hub** owns `.hub/` and the ledger. If an older `project-hub init`
  left a per-repo Asana project in `.hub/hub.yml`, intake does not track the
  campaign there; see "Migrating" below.
- **advocacy-cycle** produces the content and owns `scripts/sync.py`, which
  creates started stages and ticks finished ones from the files. Step 5 runs
  it, so those rules exist in one place.

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
will:     find or create 1 parent task on the home board, write 1 advocacy/ directory
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

Write it before the parent task exists; step 3 fills the URL in. Repo
first, Asana second, so the decision is recorded even if Asana is down.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/write_advocacy.py --repo <repo> \
  --project <slug> --claim "<the frozen, falsifiable claim>" \
  --reader "<who this is for>"
```

### 3. Find or create the parent task

Check where the file says the campaign is tracked:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/intake_core.py --tracking <repo>
```

- `kind: task`: the parent exists. Use that gid and go to step 4.
- `kind: project`: an old per-repo campaign. Show `migrate` and stop; see
  "Migrating" below.
- `kind: missing`: list the home board's top-level task titles and match
  them with `find_parent(slug, titles)`: a title that is the slug, or the
  slug followed by a colon. If one matches, that is the parent. If none
  does, create one task on `asana_home_project` (in `asana_home_section`
  when set), assigned to the user, titled `<slug>: <one line saying what
  was built>`, with the claim and the lab repo path as its description and
  **no subtasks**. Then record it:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/write_advocacy.py --repo <repo> \
  --set-asana-url <the parent task URL>
```

### 4. Set day 0

Read the parent task's `start_on` with the Asana tools. **If it has a value,
that is day 0, it is frozen, and you keep it.** Say what it is and move on.
Moving day 0 re-dates the review underneath whoever is watching the board;
if it genuinely must move, that is a deliberate edit in Asana, not a re-run.

Only when `start_on` is empty: **day 0 defaults to today, and you say so.**
Look at the git history and the ledger first. Ask, with `AskUserQuestion`
and concrete dated options, only when the repo makes today obviously wrong:
a demo built and shipped weeks ago, a README naming a launch slot, a ledger
whose last entry is months old. Otherwise do not force a question the
evidence already answered.

Then set the parent task's `start_on` (day 0) and `due_on` (day 0 plus 90)
in one `update_tasks` call. Asana rejects a `start_on` later than the current
`due_on`, so sending both together avoids the ordering trap.

### 5. Sync from files

Fetch the parent's subtask titles, write them one per line to a temp file,
then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-cycle/scripts/sync.py --repo <repo> \
  --day0 <YYYY-MM-DD> --existing-titles-file <temp file>
```

Create every row under `create` as a subtask of the parent, in order, with
exactly that `title`, `note` as the description, and `due_on` where it is
not null. These are only stages the files show already begun; on a repo
where nothing has started, `create` is empty and that is correct. Then
complete every subtask named under `complete` that is still open. Never
un-complete or delete anything, and leave subtasks this skill did not name
alone. Report `unmatched` rather than guessing which blog a URL belongs to.

### 6. Report

Say what was promoted, whether the parent task was found or created and its
URL, which stage subtasks were created and from what evidence, which were
ticked, and what day 0 is and how it was chosen.

## Migrating a campaign from a per-repo project

`--tracking` and `sync` both say so when `advocacy.md` still points at an
Asana project. Nothing syncs until it is migrated, because ticking tasks on
a board the team no longer reads is a record nobody will find:

1. Find or create the parent task on the home board, as in step 3.
2. Move only the old tasks that have real work in them under the parent as
   subtasks with the stage titles. Close the placeholders instead.
3. Archive the old project. Archive, not delete: it is the record of what
   happened.
4. `write_advocacy.py --repo <repo> --set-asana-url <parent task URL>`, then
   run step 5.

## Rules

- **Never write to `.hub/`.** That is project-hub's.
- **Never remove or flag a task you did not create.**
- **Never create an eighth stage.** A new kind of work is a tick on one of
  the seven or it is not tracked here.
- **Never create a stage before it starts.** No placeholders, no dates on
  work nobody has begun.
- **Never create an Asana project.** A campaign is one task on the home
  board.
- **The claim is frozen** once `advocacy.md` is written. **Day 0 is frozen**
  once the parent's `start_on` is set.
- **Dates are set at promotion, never at exploration.** An exploration has
  no parent task; a dated parent is a campaign. That is the whole signal.
- No em dashes. American English. Prose follows the configured voice skill.
