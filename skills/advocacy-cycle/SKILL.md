---
name: advocacy-cycle
description: Produce the content for a campaign that advocacy-intake already promoted. Extracts notes.md from the build ledger, writes the base blog post, the per-archetype takes and the social pool, records what ships, schedules the drips, renders base-layer video, and keeps the campaign's Asana parent task current from the files: a stage subtask appears when that stage starts and is ticked when it ships. Use when the user says "start the cycle", "write the blog post", "write the takes", "draft the social posts", "check the draft", "the post is live", "drip the posts", "sync asana", or runs /advocacy-cycle. Requires advocacy/advocacy.md, which advocacy-intake writes.
---

# Advocacy cycle

One build becomes a base post, six archetype takes, twelve social posts, a
drip per shipped piece, and a video. One Asana parent task on the shared
home board holds the campaign, and a stage subtask (seven possible titles)
appears under it only once that stage starts, then records when it went
live. The six developer archetypes are the fan-out for everything written
for a reader: Curious dev, Explorer, Builder, Scaler, Champion, Partner dev,
always in that order.

## Related skills

- **project-hub** owns `.hub/` and the ledger. This skill reads the ledger
  and never writes to it.
- **advocacy-intake** owns `advocacy/advocacy.md`, the frozen claim, day 0,
  and the parent task. **It runs first.** If `advocacy/advocacy.md`
  is missing, stop and say so.
- **last-looks** is the check. This skill does not carry its own.
- **x-article** writes `content/x-article.md`, its paste page and
  `x-series.md` from an approved `blog-base.md`.
- **script-to-video** renders the base-layer video.
- **The configured voice skills** govern voice: `voice_personal` and
  `voice_corporate` in `~/.claude/advocacy-workflow.yml`. **de-slop** runs
  on every draft before it is handed over.

## Where things live

Inside the lab repo, `<thing>-lab`, under `lab_root`:

```
advocacy/
  advocacy.md                 the frozen claim. intake's. never edited here
  notes.md                    every fact, cited. the only source content may project from
  notes.companion.md          what each fact means and where it came from
  content/blog-base.md        the base post
  content/archetype-takes.md  six pickup briefs, one per archetype
  content/social.md           six X posts and six LinkedIn posts, one pair per archetype
  content/x-article.md        x-article's, with x-series.md and the paste page
  content/video-script.md     the script render reads, when there is a video
  content/drips/<date>-<slug>.md   six dated posts for one shipped piece
  content/published.log       one line per drip post that went live
  renders/                    gitignored
  assets/                     authored figures
```

`scripts/cycle_core.py` computes every path. Do not construct one by hand.

## Files drive Asana, one direction

The files are the record. `published:` in a file's frontmatter is where a
piece went live, `hub.yml`'s `public_repo` is the flip, a drip with six
written posts is the drip. `sync` reads those and ticks the matching stage
subtask. Nothing flows the other way, and nothing in a file caches what the
board said. A subtask is ticked by `sync` or by hand, and never unticked or
deleted by a script.

**No placeholders.** A stage subtask is created the first time the files
show its stage begun, never earlier:

| Stage | Starts when |
| --- | --- |
| Public repo | a legal or approval doc exists, or `public_repo` is set |
| Personal blog live | `blog-base.md` is drafting, written or published |
| Corporate blog live | a company-blog URL proves it, or the user adds it by hand when the corporate edit begins |
| X Article live | `x-article.md` is drafting, written or published |
| Drip written and scheduled | any file exists under `content/drips/` |
| Video live | `video-script.md` is drafting, written or published, or a video drip exists |
| 90 day review | day 90 arrives, created with its due date |

Anything complete has started, so a stage that shipped before its subtask
existed gets one, ticked, in the same sync.

**The campaign must point at a parent task.** `sync` prints `tracking`. If
its `kind` is not `task`, show `migrate` and stop before any Asana write: an
`advocacy.md` still pointing at an old per-repo project is migrated with
advocacy-intake's "Migrating" steps, never synced in place.

## Beats are inline, in the file, not metadata

A beat is an HTML comment that scaffolds one section: its name, a word
budget, the job that section has to do, and the facts it may use with their
citations. You write into it and delete it when the section lands.

```
<!-- COLD OPEN ......................................... 60-100 w
     Job: the honest reaction to a wall of text, before the project exists.
     Facts: 3 stories from a pool of 30 (config.py:24-26).
-->
```

The beats still in a file are the sections still unwritten, which is the
honest progress signal for a draft. `open_beats()` lists them and
`piece_status()` turns them into one word: `empty`, `drafting`, `written`,
`published`.

## Verbs

Parse the argument. No argument means status.

### (no argument): status

Run `scripts/sync.py --repo <repo>` for the file states and the drips, and
fetch the parent task's subtasks from Asana. Print each existing stage with
a tick or not, then the files with their status and open beats, then each
drip's written and live counts. Name what the files show started that has
no subtask yet, and what they prove complete that the board has not ticked,
and say `sync` would create or tick it.

### `init`: notes and scaffolds

1. Refuse if `advocacy/advocacy.md` is missing.
2. **Write `notes.md` from `.hub/ledger.md`.** Every fact gets a citation to
   the ledger entry, the file and line, or an external source. **If it is
   not in `notes.md` or in a cited source, it does not ship.** Put the
   reasoning in `notes.companion.md` so a fact that is true but baffling can
   be understood six weeks later. Resolve code citations with
   `check_citation` before moving on.
3. Scaffold `content/blog-base.md`, `content/archetype-takes.md` and
   `content/social.md` with `scaffold()`: frontmatter only. Never overwrite
   a file that exists.
4. Add `advocacy/renders/` to `.gitignore` if it is not there.

### `draft <blog-base|takes|social>`: write one file

Write from `notes.md` only. A claim with no entry there does not go in.
Open beats first, then write into them, then delete them.

- `blog-base`: the post, in `voice_personal`, describing the final build:
  what it is, why, how it works now. When it ships to the company blog, the
  edit for that is `voice_corporate` applied to this text, not a second
  draft.
- `takes`: six sections in archetype order. Each is a pickup brief for one
  reader, not prose for publication: what they want from the piece, the
  fact to lead with, the angle, the call to action.
- `social`: six sections in archetype order, each holding one X post in an
  ```` ```x ```` fence and one LinkedIn post in a ```` ```li ```` fence, in
  `voice_personal`. X: 280 characters with every URL billed at 23. LinkedIn:
  600 to 1,500 characters, at most three hashtags, first line is the hook.
  No two posts share their first six words.

Run `de-slop` before handing a draft over, then stop. Whether it is ready to
publish is the user's call, and nothing here infers it from the fact that a
draft exists.

### `check [<file>]`: hand off to last-looks

Run `/last-looks` on the file, or on every file under `advocacy/content/`
when none is named, and report its actual output. Do not reimplement any
check here. Drips also have their own strict format check in
`scripts/drip.py check`.

### `ship <file> <url>`: record the landing

`set_published()` writes the URL under `published:` in the file's
frontmatter, appending when the piece already lives somewhere else (a
company post and a personal mirror are two homes, not a correction).

**Then sync the file from the live page, never the reverse.** Once a piece
is up, the site is the source of truth for its own copy and the repo file is
a record of it. Refuse to ship while `check` is failing or `check_beats`
finds a beat still open. Then run `sync`.

### `drip <piece-url> --type blog|video [--title] [--start] [--lead]`

Run from the project repo once the piece is live. `scripts/drip.py scaffold`
writes `content/drips/<date>-<slug>.md`: six posts, one per archetype in the
fixed order, each on one platform, dated two a week on Tuesdays and
Thursdays from the first Tuesday at least five days out, skipping
`launch_blackouts` and any date another post holds. It refuses to overwrite.
**Every post arrives as a beat** carrying the archetype's job and every hook
already used in the project. Write from `notes.md`, through the voice skill
and `de-slop`, then `drip.py check`, then delete the beat. `check` traces
every number back to `notes.md` as a literal token and refuses a hook whose
first six words match `social.md`, `x-series.md`, or another drip.

### `post <drip-file> <n> <permalink>`: record one post going live

`scripts/drip.py post` writes `published: <permalink>` on post `n` and
appends `YYYY-MM-DD <platform> <permalink> <file>#<n>` to
`content/published.log`. It refuses a post already published, one still
unwritten, and any file failing `check`.

### `render`: base-layer video

Read `content/video-script.md`, build one `script-to-video` beat JSON, and
render horizontal to `advocacy/renders/`. Isolate per item so one failed
take does not kill the batch. Never estimate runtime from word count. The
output is a placeholder with a synthetic voice to re-record against, never
the deliverable. When the real video is public, `ship` its URL onto
`video-script.md`.

### `sync`: create started stages, tick finished ones

Fetch the parent task's subtask titles into a temp file, one per line, then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/advocacy-cycle/scripts/sync.py --repo <repo> \
  --day0 <parent start_on> --existing-titles-file <temp file>
```

It reads `advocacy.md`'s tracking line, `.hub/hub.yml` (`public_repo`), every
`published:` under `advocacy/content/`, `drips/*.md`, `published.log`, and
the ledger's `90 day review` entry. It prints `started` (stages begun),
`complete` (stages the files prove done) and `create` (started stages with
no subtask yet), each with evidence. `--day0` is the parent task's
`start_on`, needed to date and judge the 90 day review.

If `tracking.migrate` is not null, stop there. Otherwise create every row
under `create` as a subtask of the parent with exactly that title, its
`note` as the description and `due_on` where set, then complete every
subtask named under `complete` that is still open. **Never un-complete or
delete anything, and never create a stage `sync` did not name.** Print what
changed, one line per subtask with its evidence, and print `unmatched` as
is: a live URL on a host that is neither `blog_base_url` nor in
`utm_domains` is reported, not guessed, and the user ticks that one by
hand.

## Rules

- **Never edit `advocacy/advocacy.md`.** The claim is frozen and it is
  intake's file. If a draft contradicts it, the draft is wrong or the
  campaign is over.
- **Never write to `.hub/`.** That is project-hub's.
- **Every fact comes from `notes.md`**, cited. No entry, no claim.
- **Every rejection becomes a written rule with its reason.** Video ones go
  in that style's file under `script-to-video/styles/`; everything else
  goes here.
- All prose follows the configured voice skill. No em dashes.
