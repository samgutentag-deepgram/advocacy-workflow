---
name: advocacy-intake
description: Turn a repository you already have into an advocacy campaign. Reads the repo cold, proposes which of seven surfaces across two branches it has earned, writes advocacy/advocacy.md, and promotes the repo's existing Asana project with a gate-grouped task board. Files gates A and B; advocacy-cycle files C and D. Use when the user says "make a campaign out of this", "this should be content", "run intake on this repo", or runs /advocacy-intake. Does NOT create repositories, does NOT create Asana projects, and does NOT write build ledgers; project-hub owns those.
---

## First run: set up this machine

**Before any verb, check the config.** Read it with:

```bash
python3 <skill>/scripts/config.py --show     # or import config and call load()
```

It lives at `~/.claude/advocacy-workflow.yml`, holds one person's Asana and
writing setup, and is reused by every campaign on that machine. If
`config.missing()` returns anything, **run the interview before doing what was
asked, then continue with the original request.** Never ask about a field that
is already filled.

Ask only what is missing, one question at a time, in `FIELDS` order. Each
field carries a `how` string saying where to find its answer; say that rather
than assuming the person knows. Three fields default (`lab_root`,
`voice_personal`, `voice_corporate`) and should be confirmed, not
interrogated.

The one Asana fact is the workspace gid. Read it back with the Asana tools,
write the file with `config.render()`, confirm what was written, and carry on.
Nothing has to be created in Asana by hand first.

**Also check `project-hub` is installed**, since this skill cannot run without
it. If `/project-hub` is not available, say so and point at
`/plugin install project-workflow@project-workflow`.

## Related skills

- **project-hub** owns `.hub/`, the ledger, the capture plan, and the Asana
  project itself. `project-hub init` creates the project, scaffolds four exploration tasks,
  and writes the project gid and URL into `hub.yml` under an `asana:` key.
  All of that must exist BEFORE the promotion decision, so this skill reads
  it and never creates a project of its own.
- **Two capture-shaped tasks, not a duplicate.** One of hub init's four
  exploration tasks is `Capture the first time it works`: the unrepeatable
  moment you cannot schedule, maybe weeks away. This skill's own prep
  spine creates `Record the campaign footage`: the deliberate recording
  session, scheduled now, that produces the campaign's video. Both are
  real and both get created. See step 7.
- **The configured voice skills** govern every piece of prose this generates.
  Read `voice_personal` and `voice_corporate` from the config rather than
  naming a skill here; different people write in different voices, and one of
  them may be ghostwriting for another.

## What this is not

It does not initialize a repository. The repo already exists, because the
workflow is: make a directory, `git init`, run Claude, `/init`, tinker. If the
repo never earns a campaign, nothing needs undoing, because nothing was added.

## Invocation

**No argument, run from inside the repo, is the default.** That is where the
work already is.

```
/advocacy-intake            # cwd, resolved to the git root
/advocacy-intake <path>     # from anywhere
```

Resolve with `git rev-parse --show-toplevel`, so a subdirectory works. If cwd
is not a git repo and no path was given, refuse and say so. Never guess.

**Before touching anything, echo what you resolved:**

```
repo:     <absolute path>
branch:   <branch>, <clean|N changes>
will:     promote 1 existing Asana project, write 1 advocacy/ directory
nothing happens until you confirm the surfaces below.
```

Promoting a project is outward facing and awkward to unwind (a dated gate
board lands in front of anyone watching the project), and a no-argument
invocation is how the wrong repo gets promoted. This confirmation is the
guard that makes the convenient form safe, not a courtesy.

## Steps

**The scripts below live in the plugin, not in the repo being read.** cwd
is the target repo (`~/LABS/dog-whisper-lab`, say), which has no `scripts/`
of its own. Every invocation uses the plugin's installed path,
`${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/...`, which Claude Code
resolves to wherever this version of the plugin is installed. Do not shorten
these to a repo-relative `scripts/...`; that only happens to work if you are
standing inside this skill's own directory, which you never are when running
intake.

### 1. Read the repo

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/intake_core.py --signals <repo>
```

**If `has_content` is false, stop.** The repo is git-initialized but holds
no files outside `.git`: no commits, nothing built. Say plainly that the
repo is empty, that there is nothing to advocate for yet, and that intake is
a promotion step that runs after something has been built, not before. Do
not propose surfaces, do not write `advocacy/`, do not touch Asana. This is
a guard, not a suggestion: an all-empty signals block is not a small
campaign, it is the wrong moment to run this skill.

Then read for yourself what a script cannot judge: the README's claim, the
ledger's best entries, which numbers are already measured and sourced. The
script reports structure, not specifics: it does not look inside
`.hub/assets/` and it does not extract numbers from prose. If footage exists
under `.hub/assets/`, that is your signal to treat video as the lead
surface, not the script's. If the README or ledger states a measured number
(a latency figure, a false-positive rate, a size), read it yourself and
carry the specific number into the relevant task's kickoff prompt and the
verify task's description in step 4. The model supplies specifics; the
script only supplies structure.

### 2. Propose surfaces, with a reason each

Read `reference/surfaces.md`. Propose using `AskUserQuestion`, one option set,
`multiSelect: true`, and **say what you are declining and why** in the message
around it. Three specific honesty rules:

- **No ledger means say so.** "The build-log angle is weak here and the
  first-time-it-worked footage is gone" is the correct output, not a proposal
  for a personal post that will be painful to write.
- **Defer with evidence.** Name what would change the answer.
- **Do not offer what is blocked.** A gated surface is not a choice.

### 3. Freeze the claim and write the file

**If `advocacy/advocacy.md` already exists, this is a re-run.** Skip this
step entirely and go straight to step 4; do not call `write_advocacy.py` in
create mode. `write_advocacy.py` itself still refuses to overwrite an
existing file; that refusal is correct and stays exactly as it is. This step
only runs the first time.

The claim must be falsifiable. If you cannot name two ways it could turn out
false, it is a description and not a claim, and the intake stops there.

Read the Asana project URL out of `hub.yml`'s `asana` key. If that key is
missing, stop here instead of writing a file with a broken tracking line;
see the same guard at the top of step 4. Otherwise pass the URL straight in:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/write_advocacy.py --repo <repo> \
  --project <slug> --claim "<the frozen, falsifiable claim>" \
  --reader "<who this is for>" --surfaces <the,keys,kept,in,step,2> \
  --asana-url <the URL from hub.yml>
```

One write, not two. The old flow wrote the file without `--asana-url` and
came back later with a separate `--set-asana-url` call, because the Asana
project used to not exist yet when this file was first written. `project-hub
init` now creates the project before `advocacy/` exists at all, so the URL
is already sitting in `hub.yml` before intake starts. `--set-asana-url`
still works in `write_advocacy.py` and stays tested; this flow just never
needs it.

### 4. Promote the existing Asana project

The project always already exists by the time intake runs. `project-hub
init` creates it and scaffolds four exploration tasks, all before `advocacy/`
exists. This step
never creates a project; it promotes the one that is there.

Promoting is also the only point where this skill puts dates on anything.
An exploration has no schedule, and inventing one would be fiction; a
made-up bar on a Timeline is worse than no bar. A campaign has a schedule
by definition, day 0 to day 90, so promotion is where day 0 gets asked for
and the schedule gets written. The consequence: an undated project is an
exploration and a dated one is a campaign, and that is the whole signal.
There is no status field to flip, on purpose.

1. **Read `hub.yml` for `asana.project`.** That gid is the project to
   promote.

2. **If `hub.yml` has no `asana` key, stop.** Do not create a project, do
   not guess, do not proceed. Say plainly that this repo has no Asana
   project yet, that `/project-hub init` creates one, and to run that first.
   This is a refusal, not a warning.

3. **First: is day 0 already set? If so, do not ask again.** Read the
   project's `start_on`. If it has a value, that IS day 0 and this campaign
   has already been promoted at least once. Say what it is, say you are
   keeping it, and go straight to the next step without touching the dates.

   **Day 0 is frozen once set, for the same reason the claim is.** Every drop
   date is computed from it, so changing it silently re-dates the whole
   campaign. Worse on a partial re-run: tasks created the first time keep
   their original dates while anything created now is computed from the new
   day 0, and you end up with one project whose drops come from two different
   day 0s with nothing flagging it. If day 0 genuinely has to move, that is a
   deliberate edit you make in Asana, not something a re-run does quietly
   underneath them.

   Only when `start_on` is empty is this a first promotion, and only then do
   the rest of this step.

   **Determine day 0. Look at the repo before proposing one; never default
   to today without looking.** Check the git history (first commit date and
   most recent commit date), `.hub/ledger.md`, and the README for signs the
   work is already built and shipped, not just starting now. This guards
   against exactly the case of a repo like `atc-to-text`: a built and
   deployed demo already holding a September slot, where defaulting day 0
   to today would put its bar in the wrong quarter and silently misdate all
   five drops.

   Propose day 0 with `AskUserQuestion`, a small number of concrete
   options, never an open prompt. Always include today as one of them.

   - If nothing in the repo suggests history worth accounting for, say so,
     propose today, and move on. Do not force a question the evidence
     already answered.
   - If the git history, the ledger, or the README show the work has
     already been built and shipped, say what you found and offer that
     evidence as the other options: the first commit's date, the ledger's
     most recent entry, a date or slot named in the README. Do not default
     to today when the evidence points elsewhere; ask.

4. **Set the project's `start_on` and `due_on`.** `start_on` is day 0.
   `due_on` is day 0 plus 90 days. Set both in the same `update_project`
   call, not two sequential ones: Asana rejects a `start_on` later than the
   project's current `due_on`, and setting `start_on` alone against a
   project that already carries an earlier `due_on` (a re-run, say) hits
   that rejection. Sending both fields together avoids the ordering trap.

5. **Nothing else marks the promotion.** The dates from step 4 and the gate
   board below are what make this a campaign. There is no custom field to
   flip and no portfolio to move it into; an earlier version had both, and
   they were dropped because each one needed hand setup in every workspace.

6. **Fetch the project's existing task titles** and write them, one per
   line, to a temp file. The four exploration tasks from hub init will be
   among them.

7. **Reconcile**, using the surfaces the user actually kept in step 2:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-intake/scripts/intake_core.py --reconcile <repo> \
     --surfaces <the,keys,kept,in,step,2> \
     --existing-titles-file <temp file path>
   ```

   Create only the tasks listed under `create`, in order, then wire
   dependencies for those tasks against the full task list, not only
   against other tasks you just created. Leave `keep` alone. **Leave
   `untouched` alone completely.**

   **Pass `--filer intake`.** This skill files gates A and B and the prep
   spine, and nothing else. `advocacy-cycle` files gates C and D on its
   first run, because a style variant of a canonical that does not exist yet
   is a guess, not a task. Without the flag you will file the whole board,
   including twenty-four subtasks for content nobody has written.

   The `create` list is scoped by the flag. `title_by_key` is not: it always
   covers the whole board, because a Gate C task depends on a Gate B task
   this skill created, and that dependency has to stay resolvable from the
   other side.

   **A kept surface is not one task.** A blog is one Gate A item. A
   derivative is a Gate B canonical, a Gate C parent, and four Gate C
   variants under it. "Personal thread" is a label; "Gate B: Personal
   thread, edit to publish ready" is an action, and the board has to answer
   "what do I do next".

   Gates and items are defined in one place, `GATES` and `build_tasks` in
   `intake_core.py`. `advocacy-cycle` imports that same table rather than
   carrying its own, so there is one definition for two filers.

   | Gate | Items | Subtasks | Drop day | Filed by |
   | --- | --- | --- | --- | --- |
   | A | one per kept blog | none | 1 | intake |
   | B | one per kept derivative | none | 10 | intake |
   | C | one per kept derivative | 4, one per style | 30 | cycle |
   | D | one, the render batch | 4, one per style | 45 | cycle |

   Gate D exists only when `personal_video_script` was kept. Video derives
   from the personal blog only.

   **Create the Asana sections first, one per gate**, then create each task
   into its gate's section. A task with no section lands in the project's
   default bucket and the board stops answering the question it exists for.

   **Subtasks are created under their parent, not into a section.** Asana
   subtasks cannot belong to one, which is why Gate C is five parent tasks
   carrying four children each rather than twenty loose tasks. A task's
   `parent` field in the JSON is the key of the task to create it under,
   and it is null on a top-level task. Depth stops at two; nothing in this
   model is a subtask of a subtask.

   **How the prep spine attaches, which is the part that is easy to get
   wrong.** The script already computes all of this; the rules are here so
   the output reads as intended rather than as noise:

   - Each gate item depends on the one it derives from. Gate B waits on its
     branch's Gate A blog, Gate C's parent waits on its Gate B canonical,
     each variant waits on its parent, and the Gate D batch waits on the
     video script's Gate C parent. Nothing derives from an unapproved
     parent, at any level.
   - **Branches never cross.** A personal surface never waits on a corporate
     one. They are peers, not a pipeline.
   - `gate` and `gate_doc` attach to the **Gate A blogs only**. Everything
     else reaches a blog through the chain, so a legal block on the blog
     stops the whole branch transitively. Wiring it to every item would say
     the same thing four more times and be four more places to get it wrong.
   - `verify` attaches to the **Gate A blogs only**, for the same reason and
     because the blog is where a number appears first. That is the last
     point before four other surfaces repeat it.
   - `capture` attaches to the **Gate D render batch**, and to nothing else.
     Footage exists before the camera step, not before the surface.
   - Each surface's limit is quoted on the item that can still cut to it:
     the Gate A blog, or the Gate B canonical.

   **Resolving a dependency: use `title_by_key` from the reconcile
   output.** A created task's `depends_on` holds task KEYS, like `gate`
   and `verify`. Asana is addressed by title. `title_by_key` maps every
   key to the title that task actually carries, whether it was just
   created or was already sitting in the project under `keep`. Look the
   key up there, find that title in the project, and wire to its gid.

   Do not skip a dependency you cannot resolve, and do not guess a title.
   Every key in `depends_on` is guaranteed to be present in
   `title_by_key`, so a lookup that misses means something upstream is
   wrong and is worth reporting rather than working around. An unwired
   dependency is the worst failure available here: it looks exactly like
   a task that is ready to start. It includes the four exploration tasks
   from hub init and anything the user typed in themselves, and this skill never
   deletes or flags either.

   **Create every task with exactly the title the script returned.** No
   overrides, for any task. `derive_spine` labels the capture task
   `Record the campaign footage` and that is the title to use. An earlier
   version of this file told you to override it, because the script and
   the doc had drifted apart. They no longer have, and re-introducing an
   override would break `reconcile`, which matches on title: a title
   created in Asana that differs from the one the script computes makes
   every re-run produce a duplicate.

   **Why this is not the same task as hub init's `Capture the first time
   it works`, even though both mention capture.** Hub init's task is the
   unrepeatable moment you cannot schedule: the first time something
   works, which may be weeks away, and a recording started after the fact
   is a reenactment. This skill's `Record the campaign footage` is the
   deliberate, planned recording session, scheduled now, that produces
   the campaign's video, and it carries real project-specific work (a
   licensing blocker, a legal source with required attribution, a
   segmentation fix, what has to be legible on screen) plus real
   dependents, such as a video surface's record step wired to it. A prior version
   of this skill treated the two as duplicates and skipped creating this
   one on the theory that hub init's task made it redundant by
   construction. A real run proved that wrong: skipping it deleted
   project-specific content and left the dependent record step pointing
   at a task that no longer got created. Both tasks are real. Create
   both.

   **The lesson: titles are the reconcile key, not intent.** `reconcile`
   matches on title text, not on what a task is for. Two tasks doing
   different jobs must not have titles that read as the same job, or a
   future edit will collapse one of them again, the way this one did. Two
   tasks doing the same job must share an identical title, or `reconcile`
   will create a second one under the new title instead of recognizing
   the first. Treat a task title as an identifier, not a description.

   **Give each newly created step task a `due_on`**, passed to
   `asana_create_task` at creation time, computed as **day 0 + `drop_day` +
   `offset`**. The script emits both numbers on every task it returns, so
   there is no table to read off and no mapping to do by hand. `drop_day`
   is the surface's day from the day map in `reference/day-map.md`;
   `offset` is that step's distance from the drop and is never positive, so
   the last step lands exactly on the drop day and the earlier steps stack
   backwards from it. The core has no clock on purpose: it hands over two
   integers and this step, which knows day 0, does the arithmetic.

   Worked example with day 0 = 2026-09-01. `Video tech demo: record` comes
   back with `drop_day` 30 and `offset` -5, so it is due 2026-09-26, five
   days before the day 30 drop on 2026-10-01.

   **A date before day 0 is correct. Do not clamp it.** `personal_blog`
   drops on day 1 and its outline step carries `offset` -3, which is day -2.
   That is not an arithmetic accident: the personal post has to go out while
   the launch attention is still there, and writing it takes longer than the
   day between day 0 and day 1. So the outlining and drafting happen DURING
   the build, not after it.

   That is the same argument the ledger and the capture plan rest on. The
   material for the post is produced while the work is happening, and a
   campaign that starts writing on day 0 has already lost the part that
   cannot be recovered. A negative day is the system saying so out loud.

   Set the project's `start_on` to the earliest step date rather than to day
   0, so the Timeline shows the prep that actually has to happen.

   `gate`, `gate_doc`, `solidify`, `verify`, and `capture` are prep tasks,
   not steps. The script returns `drop_day` and `offset` as `null` for
   them, and their `due_on` stays unset. The day map is a default, not a
   rule proven for every campaign: if a kept surface does not fit what a
   given repo is actually doing, leave that surface's steps undated rather
   than forcing a guess, and say so in the report. Never touch the `due_on`
   of a `keep` or `untouched` task; only tasks this step creates get dated.

8. **Mark the task named `Decide: promote or drop` complete, if one
   exists.** Promoting is that decision; leaving the task open would show a
   decision still pending on the board when it is not. If no task by that
   name exists, skip this silently. Not every project came through hub init
   with that task scaffolded, and a missing task here is not a problem to
   report.

**Every task description carries a generated kickoff prompt** to paste into a
fresh session, in this shape:

```
KICKOFF PROMPT, paste this into a fresh session from <repo>:

"<what to do, which files to read first, which numbers are safe to quote,
which are not, and what the exit condition is.>"
```

That is what makes a task actionable rather than a label. Write it from what
you read in step 1, never from a template.

**One kickoff prompt per step, and keep them narrow.** A step is already a
single action, so its prompt is short: the files that step touches, the exit
condition for that step alone, and nothing about the steps around it. The
script's `why` for the step is the spine of it; add the repo's specifics on
top. Do not write one campaign-sized prompt and paste it onto every step of a
surface.

### 5. Report

Say what was promoted, what tasks were created versus already there, and
what is blocked. If any Asana call failed, say which tasks exist and that
re-running completes the rest. Say what day 0 was and how it was chosen,
the project's `start_on` and `due_on`, and which tasks were left without a
`due_on` and why. Report by gate, naming how many items each one created,
rather than listing every task title back.

Say plainly that gates C and D were not filed and that `advocacy-cycle`
files them when it runs. A board that stops at Gate B is the expected
outcome here, not an incomplete run, and it should be reported as such so
nobody re-runs intake looking for the rest.

## Rules

- **Never write to `.hub/`.** That is project-hub's, and this skill is
  read-only over build history.
- **Never propose a surface the repo cannot support.** Say what is missing.
- **Never remove or flag a task you did not create.** The user adds tasks to Asana
  as they occur to them during a build. A task they typed and a task this
  generated are the same kind of thing. `reconcile` has no delete list on
  purpose.
- **Re-running is safe** and creates only what is missing. It is never how a
  task gets added; typing it into Asana is.
- **The claim is frozen** once `advocacy.md` is written.
- **Dates are set at promotion, never at exploration.** Only step 4 writes
  `start_on`, `due_on`, or a task `due_on`. An exploration's project and
  tasks stay undated, which is why the Timeline draws bars for promoted
  campaigns only.
- **Renaming a task in Asana does not stick.** Reconciliation matches on
  title, so re-running intake after a task was renamed in Asana recreates it
  under its original title. If a title must change, rename it in the repo's
  brief and re-run, rather than renaming it in Asana directly.
- No em dashes. American English. Prose follows the configured voice skill.

## Resolved

Filing into a shared board used to need someone else's agreement, so this
skill never did it. That objection is gone: the project is the user's own, created by
`project-hub init`, and this skill only ever promotes that project, never
files into anything shared.
