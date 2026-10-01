---
name: last-looks
description: The last step before anything ships or posts. Runs de-slop and the configured personal voice pass on each prose file, then one script runs every mechanical check: frontmatter and passes, em dashes, banned words, every number traced to notes.md, X and LinkedIn limits, every URL resolving, UTM attribution on owned links, images present and wide enough, live pages loading their images and social cards, and the project's video standard. Refuses to call anything ship-ready while a finding is open. Use when the user says "last looks", "final check before I post", "is this ready to ship", or runs /last-looks.
---

# Last looks

The checks a tired reader misses and a script does not: a number that is not in
`notes.md`, a link that 404s, an owned link with no UTM, a 700 px hero image, an
em dash. Run it on everything that is about to leave the repo.

## What it takes

One or more targets, in any mix: a blog draft, `social.md`, a drip file,
`x-article.md`, an HTML page on disk, a live URL, or a video (`brag.mp4`, a
beat JSON, a `SCRIPT.md`). The script tells the kinds apart by name, so pass
the real paths rather than copies.

## The order

1. **Model passes, prose files only.** Run `advocacy-workflow:de-slop`, then the
   skill named in `voice_personal` in `~/.claude/advocacy-workflow.yml`, on each
   prose target. Record both in the file's frontmatter as
   `passes: [<voice_personal>, de-slop]`. The script checks that line is there
   and will not take your word for it.
2. **The script runs every mechanical check.**

   ```bash
   S=${CLAUDE_PLUGIN_ROOT:-$(ls -d ~/.claude/plugins/cache/advocacy-workflow/advocacy-workflow/*/ | tail -1)}
   python3 "$S/skills/last-looks/scripts/last_looks.py" advocacy/content/blog-base.md advocacy/content/social.md
   python3 "$S/skills/last-looks/scripts/last_looks.py" https://example.com/blog/post --min-width 1600
   ```

   One line per finding as `file:line: message`, then a one-line verdict per
   file, exit 1 while anything is open. Paste the output; never summarize a
   check you did not run.
3. **The verdict.** Nothing is ship-ready while a finding is open. Not with a
   caveat, not "except the links". Fix the file or the notes, run it again,
   and only then say so.

## What the script checks

| On | Check |
| --- | --- |
| every content file | frontmatter with `status` and both passes, no em dashes, no banned words (leverage, delve, nuanced, robust, seamlessly, elevate, streamline, supercharge, empower, unlock, comprehensive) |
| every content file | every number of two or more digits, decimals and thousands included, is a literal token in the project's `advocacy/notes.md`, ignoring word budgets, character counts, years, `path:line` citations, code and URLs. Superseded sections of the notes are not live |
| `social.md`, drips | X posts within 280 with every URL billed at 23; LinkedIn 600 to 1,500 characters and at most three hashtags; six posts per platform in `social.md`. A drip also gets `drip.py check`'s own rules |
| every URL | resolves (HEAD, then GET). `x.com`, `linkedin.com`, `api.deepgram.com` and localhost are skipped and checked by hand |
| every owned link | carries `utm_source`, `utm_medium`, `utm_campaign` and `utm_content`, nothing more. The person is in `utm_content`, never `utm_source`. Nothing off the owned domains is tagged. Links inside code are not links |
| `archetype-takes.md`, `notes.md` | skip the UTM and length checks. A pickup brief and the fact sheet are read in the repo, never posted. Em dashes, banned words and numbers still apply |
| every image a file references | exists, is PNG, JPEG, GIF, WebP or SVG, and a raster is at least 1200 px wide (`--min-width`), read from the file header |
| an HTML page or live URL | every `<img>` fetches with 200 and an image content type; `og:image` and `twitter:image` exist, are absolute URLs, and fetch |

`--notes <path>` overrides where the numbers are traced to. `--no-net` skips the
network checks and says nothing is ship-ready on that basis alone.

## The video standard

Every campaign ships two videos: a brag-style launch video (`brag-output*/brag.mp4`)
and a Remotion sample video (a Remotion project or render under the repo, often in a
`.claude/worktrees/*remotion*` worktree, `video/` or `renders/`).
Each video's script or beat file covers four beats in this order: what this is,
how it works, why you'd use it, examples for expansion. Synonyms count, by heading
or beat name, case-insensitive.
The closing call to action is the Deepgram console signup with attribution: a link on
`console_signup_url` carrying `utm_source`, `utm_medium=video`,
`utm_campaign=<project slug>` and `utm_content=<person_slug>_video`.
With `ffprobe` installed, every mp4 is at least 1920x1080 or 1080x1920 and its
duration is reported; without it, the script says so once.
Where the project earns it, one version per developer archetype, same four beats.

Video findings block shipping a video and block ticking **Video live** in Asana.
When the target is prose they print as reminders and do not change its verdict.

## Settings

Read from `~/.claude/advocacy-workflow.yml`: `voice_personal` (the pass every file
lists), `utm_domains` (the owned domains, comma separated), `person_slug`,
`blog_utm_source` (the one `utm_source` allowed to carry the person), and
`console_signup_url`, which defaults to `https://console.deepgram.com/signup`.

## Rules

- **Never call anything ship-ready with an open finding.** The script's exit code is
  the answer, and a finding you disagree with is fixed in the rule, not talked past.
- **A wrong number is fixed in `notes.md` first**, with the old value moved under a
  dated Superseded heading, then in the file. Editing the file alone puts the two in
  disagreement, and the next run finds it again.
- **Do not skip the network checks to get a green run.** `--no-net` is for a train.
- **This is the one implementation.** The command center's `lint.py` imports this
  script; `drip.py check` is imported here. Add a rule in one place.
- A clean run is what completes **Personal blog live**, **Corporate blog live**,
  **X Article live**, **Drip written and scheduled** and **Video live**. It does not
  tick them for you.

## Tests

```bash
python3 -m pytest skills/last-looks -q
```
