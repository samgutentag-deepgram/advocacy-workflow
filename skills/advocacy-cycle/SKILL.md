---
name: advocacy-cycle
description: Produce the content for a campaign that advocacy-intake already promoted. Scaffolds advocacy/content/, extracts notes.md from the build ledger, writes the two blogs, derives five canonicals and twenty style variants through four review gates, files gates C and D in Asana, and renders base-layer videos. Use when the user says "start the cycle", "write the blog posts", "fan out the variants", "check the drafts", "the post is live", or runs /advocacy-cycle. Requires advocacy/advocacy.md, which advocacy-intake writes.
---

# Advocacy cycle

One build becomes two blogs, five canonicals, twenty variants and four
videos, through four gates that are all yours.

```
notes.md          every fact, cited, out of .hub/ledger.md
  two blogs                                     GATE A
    five canonicals                             GATE B
      twenty style variants                     GATE C
        four horizontal base layers             GATE D
```

**Nothing derives from an unapproved parent, at any level.** This is the rule
the whole skill exists to enforce. Writing variants before the canonical is
signed off means rewriting all of them when it changes, which is how a fan-out
turns into four times the work instead of four times the output.

## Related skills

- **project-hub** owns `.hub/` and the ledger. This skill reads the ledger and
  never writes to it.
- **advocacy-intake** owns `advocacy/advocacy.md`, the frozen claim, and files
  gates A and B in Asana. **It runs first.** If `advocacy/advocacy.md` is
  missing, stop and say so: this skill produces a campaign's content, it does
  not decide there is one.
- **script-to-video** renders gate D and owns the style contracts.
- **The configured voice skills** govern voice. Read `voice_personal` and
  `voice_corporate` from `~/.claude/advocacy-workflow.yml` rather than naming
  a skill here. `personal-style` and `corporate-style` ship with this plugin
  and are advocate-agnostic; a person writing in their own established voice
  names their own skill instead, and the same field is how you ghostwrite for
  somebody else.
- **de-slop** runs before every gate.

## Where things live

Campaigns run inside a **lab repo**: a private working repo named
`<thing>-lab`, kept under the directory in `lab_root` (`~/LABS` by
convention). The `-lab` suffix is the convention that keeps a working repo
from being published by accident; the clean public repo is created separately
at the end and the lab repo never goes public.

```
advocacy/
  advocacy.md                 the frozen claim. intake's. never edited here
  notes.md                    every fact, cited. the only source content may project from
  notes.companion.md          what each fact means and where it came from
  content/<branch>/blog.md
  content/<branch>/<surface>/<surface>.md
  content/<branch>/<surface>/variants/<surface>-<style>.md
  renders/                    gitignored
  assets/                     authored figures
  review/                     critique output, input to revision
```

`scripts/cycle_core.py` computes every path. Do not construct one by hand.

**Directory depth is the gate.** Gate B is everything at the top level of a
surface's directory, Gate C is everything one level down in `variants/`.

### Asana is the source of truth for gate state

**A gate task marked complete IS that piece being approved.** The board
already says so. Do not ask the user to flip a field in a file to say it a second
time, and never infer approval from anything else.

The join is by title, and the titles match by construction because both
skills build them from the same `SURFACES` table. `gate_task_title()` gives
the task for any piece.

| Piece | Its task |
| --- | --- |
| a blog | `Gate A: <label>, edit to publish ready` |
| a canonical | `Gate B: <label>, edit to publish ready` |
| a variant | `Gate C: <label>, <style> variant` |

Read the board with `status_from_board()`, then **write the answer back into
each file's frontmatter as a cache**, stamped with the date:

```yaml
---
surface: personal-blog
status: approved          # cache. written from the board, never read into it
status_synced: 2026-08-28
published: https://...    # a fact about the world, not a gate state
---
```

**One direction only.** Nothing ever flows file to board, so the two cannot
drift into disagreeing about which is right. Same rule as syncing a published
piece from its live page.

**Why this way round.** If the board is right and a file is stale, nothing
breaks, because nothing reads the file for this. If a file were right and the
board stale, this skill would refuse to write variants for work the user considers
approved and they would go hunting for why a tool is arguing with them. One
direction fails quietly; the other fails loudly at the worst moment.

**If Asana cannot be reached**, fall back to the cached `status`, and say out
loud that you are reading a cache and how old `status_synced` is. Never let
that pass silently.

`published` is the exception and stays file-owned: a live URL is a fact no
checkbox can tell you.

### Beats are inline, in the file, not metadata

A beat is an HTML comment that scaffolds one section, holding its name, a word
budget, the job that section has to do, and the facts it may use with their
citations. You write into it and delete it when the section lands.

```
<!-- COLD OPEN ......................................... 60-100 w
     Job: the honest reaction to a wall of text, before the project exists.
     Facts: 3 stories from a pool of 30, 2 comments from ONE thread
     (config.py:24-26). Not two threads.
-->
```

So **the beats still in a file are the sections still unwritten**, which makes
them the honest progress signal for a draft: not how long it is, but how much
of its outline is still a comment. `open_beats()` lists them.

There is no `beats/` directory and no `beats:` frontmatter key. A beat belongs
where the writing happens, because that is the only place it gets read.

## Styles

`technical`, `build-it-too`, `fun`, `user-demo`. All four, on every canonical,
every time. No picking a style per surface.

The contracts live at `${CLAUDE_PLUGIN_ROOT}/skills/script-to-video/styles/`, one file
each, and govern threads as well as video. **Never copy them into a project
repo.** A second copy is the copy that goes stale. Read the Stance, Leads
with, Emphasize, Cut and Register sections; the frontmatter and Length section
are written for video.

Variants are staggered long tail reposts of the same material, filling gaps
between cycles. They are not four competing angles for one slot, so they may
share the canonical's rhythm and the edits should be light.

## Verbs

Parse the argument. No argument means status.

### (no argument) — status

Report, briefly: which gate the campaign is on, the count at each status per
gate, and the next unblocked piece. Name anything blocked and say what it is
waiting on. Use `gate_status` and `blocked_reason`; do not eyeball the tree.

### `init` — scaffold and file

1. Refuse if `advocacy/advocacy.md` is missing. Say that `/advocacy-intake`
   writes it and to run that first. This is a refusal, not a warning.
2. Read the kept surfaces out of `advocacy.md`.
3. **Write `notes.md` from `.hub/ledger.md`.** Every fact gets a citation to
   the ledger entry, the file, or an external source. **If it is not in
   `notes.md` or in a cited source, it does not ship.** Put the reasoning in
   `notes.companion.md` so a fact that is true but baffling can be understood
   six weeks later.
4. Create the content tree from `content_tree()`, each file frontmatter only,
   `status: drafted` absent until something is written. Never overwrite a file
   that exists.
5. **File gates C and D in Asana.** Run intake's reconciler with
   `--filer cycle`, create the sections, then the parents, then the subtasks
   under them. Gates A and B are already there; leave them alone.
6. Add `advocacy/renders/` to `.gitignore` if it is not there.

### `draft <surface>` — write a blog or a canonical

1. **Check the parent against the board.** Fetch the project's completed task
   titles, build the status map with `status_from_board()`, then let
   `blocked_reason` decide. Not judgment, and not the file's cached status.
2. Project only from `notes.md`. A claim with no entry there does not go in.
3. Blogs: the personal one uses the skill named in `voice_personal`, the
   corporate one uses `voice_corporate`. Canonicals inherit their blog's
   voice.
4. Run `de-slop` before handing it over.
5. Sync the cache with `apply_status()` and stop. **Approval is the user's, happens
   in Asana, and is never inferred** from the fact that a draft exists. Tell
   them which task to complete when they are happy with it.

### `variants <surface>` — fan out to four styles

1. Refuse unless the board says the canonical's Gate B task is complete, or
   the file carries a `published:` URL.
2. Write all four. Same facts, different framing.
3. **A style changes framing and never a claim.** A wrong number is wrong in
   all four, is fixed in the canonical first, and is carried down.

### `render` — gate D

Only for `personal_video_script`, and only once its variants are approved.
Build one `script-to-video` beat JSON per approved variant and render
horizontal. Output to `advocacy/renders/` beside its input JSON.

- **Isolate per item.** One failed take must not kill the batch or strand the
  queue behind it.
- **Never estimate runtime from word count.** Duration tracks sentence count
  too, and guessing from words has been wrong every time it was tried.
- These are placeholders with a synthetic voice. They exist so the advocate can
  re-record against a structure, and are never the deliverable.

### `check` — the five checks

Run all five and report actual output. Never report a check as passing without
having run it.

| Check | What it does |
| --- | --- |
| `citations` | Resolves every `path.py:120-140` against the repo. `find_citations` then `check_citation` |
| `facts` | Every number traced to `notes.md`, plus every file still holding a superseded value |
| `limits` | `check_limits`, which bills every URL at 23 characters the way X does |
| `links` | Every URL resolves |
| `beats` | `check_beats`: nothing approved or published still carries an open beat |

**`facts` is the one that matters most and the only one that is not pure.**
When a number in `notes.md` changes, every file already carrying the old value
has to be found and fixed. A corrected measurement once survived in fourteen
files, `notes.md` among them.

### `ship <surface>` — record the landing

Set `published:` to the live URL. `status` follows from that on the next
sync; do not hand-write it.

**Then sync the file from the live page, never the reverse.** Once a piece is
up, the site is the source of truth for its own copy and the repo file is a
record of it. A repo copy has been the last pre-publication draft before, and
differed from the published page in five blocks.

Refuse to mark anything published while a check is failing.

## Rules

- **Never write ahead of an unapproved parent.** Not even a first pass, not
  even to save a round trip.
- **Never edit `advocacy/advocacy.md`.** The claim is frozen and it is
  intake's file. If a draft contradicts it, the draft is wrong or the campaign
  is over.
- **Never write to `.hub/`.** That is project-hub's.
- **Never copy the style contracts into a project repo.**
- **Every rejection becomes a written rule with its reason.** Style-specific
  ones go in that style's file, the way `technical.md` records why
  lessons-learned framing is banned. Surface-neutral ones go here.
- All prose follows the configured voice skill. No em dashes.

## Notes

- The cycle exits at published, but publishing is not distribution. Getting a
  post read is a separate job and is deliberately outside this skill.
- Vertical video is out of scope. Horizontal only; extract vertical by
  hand if a clip earns it.
- LinkedIn wants text plus images and voiceless demos rather than narrated
  video. Its assets come from `advocacy/assets/`.
