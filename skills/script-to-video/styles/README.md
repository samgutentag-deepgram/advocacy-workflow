# Styles

One file per style. Each is a set of writing rules for adapting a source script into one take.
Everything here is prose for the author to follow, not config the renderer reads. The only fields
the renderer consumes are `title`, `voice`, and `tempo` from the frontmatter.

## Adding a style

Copy an existing file. Give it a `key` that is safe in a filename, and write the sections:
**Stance**, **Leads with**, **Emphasize**, **Cut**, **Register**, **Length**, **Calibration line**.

New styles are picked up automatically. There is no list to update.

## Tuning a style

Edit the file. Record *why* when a rule came from a correction, the way `technical.md` records why
the lessons-learned framing is banned. A style file with reasons in it survives being edited by
someone who was not there.

## Styles apply to both orientations

A style is a way of talking, not a layout. The same four styles are used for horizontal
walkthroughs and for vertical reels; vertical additionally requires the hook / payoff / CTA shape
per chunk, which is in SKILL.md rather than repeated in every style file.

## Per-run overrides

A style's `voice` and `tempo` are defaults. Override either in the generated beat JSON for a
single run without touching the style file.
