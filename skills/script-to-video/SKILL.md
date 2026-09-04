---
name: script-to-video
description: Use when a written script has to become a watchable video and no footage exists yet. Covers base layers for an editor, timing references before a shoot, animatics, narrated walkthroughs, and scratch cuts for feeling out pacing. Triggers include "turn this script into a video", "make me a base layer", "narrate this script", "karaoke transcript video", "animatic", a script that needs timing before anyone records, and /script-to-video.
---

# Script to video

Turn a written script into a narrated 1920x1080 video: synthetic voice, a karaoke transcript that
lights the word being spoken, the shot direction for each beat held on screen, and a waveform with
a playhead.

The output is a **base layer**, not a deliverable. Drop it on a timeline and replace the picture
and audio with the real thing. Its job is to put every cut in the right place before anyone records.

## When to use

- A script exists and someone needs to see it as a video before shooting it.
- You want the real runtime of a script rather than a word-count guess.
- An editor needs a scratch track to build against.
- You want to compare several tonal takes on the same material.

**Not for:** anything shipping to an audience. The voice is synthetic and the point is timing.

## What a run produces

**One take per file in `styles/`.** That is the default output: four style files means four mp4s
off one source script. Render the whole set unless the user names a subset.

Orientation is separate from style. A vertical run still produces one take per style, so asking
for vertical means four vertical mp4s, not one.

Each take is the same material in a different voice, so they are worth comparing side by side
before committing an edit to one direction.

## Workflow

1. **Read the source script.** Pull out its beats: the shot direction and the spoken line for each.
2. **Split fat beats.** One beat per shot change. A beat whose direction lists several things
   should be several beats, or the direction stops matching the picture.
3. **Read every file in `styles/`.** Each one carries the writing rules for its take.
4. **Write one take per style** into a single beat JSON, keyed by style. Keep the facts identical
   across takes and change only the framing; a style is a way of saying the same true thing.
5. **Add holds** wherever the real edit sits in silence, so runtime is honest.
6. **Render them all** in one invocation.

## Styles

`styles/*.md`. One file per style, each a set of writing rules: stance, what it leads with, what to
emphasize, what to cut, register, length, and a calibration line.

| Style | Stance |
| --- | --- |
| `technical` | What it does and how it is built. Never what went wrong and what I learned |
| `build-it-too` | The viewer is going to clone this. Every beat answers "what would I change" |
| `fun` | Somebody made a thing they like and wants to show you |
| `user-demo` | A person who will never read the code is deciding whether to use it |

**Edit these files to tune a style; add a file to add one.** New styles are picked up
automatically, there is no list to update. `styles/README.md` covers the format.

Only `title`, `voice`, and `tempo` from a style's frontmatter reach the renderer. Everything else
is guidance for whoever writes the take.

## Vertical mode

`"orientation": "vertical"` renders 1080x1920 for social platforms, with bigger type and fewer
words per line. The text sits in the upper middle so platform UI along the bottom does not cover it.

Vertical output is **one long reel cut into standalone clips**, not a tall version of the
walkthrough. Use `chunks` instead of `beats`:

```json
{
  "vert-technical": {
    "title": "Technical demo - vertical",
    "orientation": "vertical", "tempo": 0.85, "chunk_gap": 5,
    "chunks": [
      {"label": "The whole pronunciation dictionary",
       "beats": [["normalize.py on screen", "This is the entire dictionary."]]}
    ]
  }
}
```

Between chunks the renderer holds a loud amber card reading `CLIP n / N`, the next clip's label,
and `— CUT HERE —`. That card is the whole point of the format: one render, obvious cut points,
chop it up afterwards. `chunk_gap` defaults to 5 seconds.

### Writing a chunk

**Every chunk is a hook, a quick payoff, and a call to action.** A chunk that only informs is a
chunk nobody finishes. Three beats is usually right:

| Beat | Job |
| --- | --- |
| Hook | One sentence that states the surprise or the problem. No setup, no context, no "in this video" |
| Payoff | Two or three sentences that deliver the thing the hook promised |
| CTA | One sentence pointing somewhere: the repo, the feed, the write-up, the next clip |

Each chunk stands alone. Someone seeing clip four first should need nothing from clips one to
three, which means a fact can repeat across chunks and that is correct, not sloppy.

**Holds belong in horizontal, not here.** A 12 second hold in a walkthrough is space for b-roll.
The same hold inside a 30 second social clip is dead air a viewer scrolls past, and it makes the
clip boundaries hard to find because a long hold looks exactly like a chunk gap. Keep vertical
holds to 3 seconds or drop them.

### Chunk length, by platform

Set `target_seconds` and the renderer warns on any chunk estimated to overrun it.

| Target | Platform | Shape |
| --- | --- | --- |
| **15s** | Instagram Stories, whose card *is* 15 seconds | Hook, one payoff line, three-word CTA. 8 to 10 chunks per reel |
| **30s** | Reels, TikTok | Hook, two or three payoff lines, a full CTA. 6 chunks per reel |

Stories is the one with a hard structural unit. Go over 15 seconds and the platform splits the
card wherever it likes, which throws away the cut points you built.

The 21 to 34 second band for Reels and TikTok is a completion-rate observation rather than a rule:
short enough to finish, long enough to land a hook and a payoff.

**Platform maxima change often. Verify current limits before committing a workflow to them.**

**Size chunks with the estimator, not with a word count.** Vertical copy is punchy by design and
punchy is the slow mode, so 75 words of hooks is nowhere near 75 words of prose. Pick chunk topics
already self-contained in the source: a single surprising number, one bug, one design decision. A
chapter needing a preamble is a bad chunk.

## The core trick

Batch TTS returns audio and no timing metadata, so there is nothing to drive word highlighting
off. **Send the synthesis back through speech to text.** Deepgram STT returns word-level start and
end times measured against the audio that actually exists, and those timings get aligned onto the
source text with `difflib`, so the words on screen are the script's own spelling and the timing is
real. Round trip is a couple of seconds per clip.

## Input format

One JSON file. Each take is a key; each beat is `[direction, spoken line]`, with an optional third
element for seconds of held silence after the line.

```json
{
  "my-take": {
    "title": "Technical demo",
    "voice": "flux-alexis-en",
    "tempo": 0.85,
    "beats": [
      ["Docs page for the API", "This endpoint takes plain text and returns audio."],
      ["Press play, let it run", "Here is what it made this morning.", 15]
    ]
  }
}
```

| Key | Does |
| --- | --- |
| `title` | Bottom-left label on every frame |
| `voice` | Any Deepgram Flux voice id. Default `flux-alexis-en` |
| `tempo` | `atempo` multiplier applied **before** the timing pass, so karaoke stays in sync. Below 1.0 is slower |
| `orientation` | `horizontal` (1920x1080, default) or `vertical` (1080x1920). See Vertical mode |
| `chunks` | Vertical reels: a list of `{label, beats}`, rendered with a cut card between each. Use instead of `beats` |
| `chunk_gap` | Seconds of silence and cut card between chunks. Default 5 |
| `target_seconds` | Per-chunk length target. Chunks estimated over it are flagged at render time |
| third beat element | Seconds of silence held after the line, direction still on screen |

## Running it

```bash
uv venv --python 3.12 .venv
uv pip install --python ./.venv/bin/python pillow
./.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/skills/script-to-video/scripts/build.py script.json --outdir ./out
./.venv/bin/python ${CLAUDE_PLUGIN_ROOT}/skills/script-to-video/scripts/build.py script.json my-take   # one take
```

A take that fails does not stop the batch: the rest still render, the failures are listed at the
end with a retry command, and the exit code is non-zero. TTS and STT calls do drop occasionally,
so check the summary rather than assuming a clean run.

Needs `ffmpeg` on PATH. The key comes from `$DEEPGRAM_API_KEY`, else `$DEEPGRAM_ENV_FILE`, else the
nearest `.env` at or above the working directory. Fonts override with `S2V_FONT_SANS` and
`S2V_FONT_MONO`.

The intermediate `.wav` is deleted once the mp4 exists, because the mp4 carries the audio. Pass
`--keep-wav` when you want the narration on its own track.

## Calibration

**Duration tracks words *and* sentence count, not words per minute.** Flux pauses at every
sentence boundary and lengthens the final word, so punchy fragment copy runs at roughly half the
words-per-minute of flowing prose. Measured on identical content:

| Copy | Words | Sentences | Result |
| --- | --- | --- | --- |
| Punchy | 26 | 10 | 15.0s = 104 wpm, 17% silence |
| Flowing | 38 | 1 | 11.5s = 198 wpm, 4% silence |

Estimate with:

```
duration ≈ (words × 0.30s) + (sentences × 0.70s)
```

Within about 10% across every sample measured. **Never size a chunk by word count alone**, because
hook-driven vertical copy is the punchy mode and will overrun a word-count budget badly.

`build.py script.json --estimate` prints predicted durations per chunk with no API calls. Use it
before spending a render.

### Tempo

**Leave `tempo` at 1.0.** `atempo` below 1.0 stretches phonemes, not just pauses: at 0.85 the
measured phoneme time grew 14%. People slow down by pausing more and holding the same phoneme
rate, so stretching vowels reads as sluggish rather than measured. If a take needs to fill more
wall clock, widen the gaps between beats instead of slowing the voice.

A base layer at natural tempo runs **shorter** than the real take, because presenting to camera is
slower than synthesis. That is fine. Treat the duration as a floor.

### Render cost

About 1 second of wall clock per second of video, plus the TTS and STT calls.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Applying `atempo` after the timing pass | Karaoke drifts. Set `tempo` in the JSON so the pipeline slows the audio *before* it transcribes |
| Narration-only timing on a demo script | Wherever the real edit sits in silence, add a hold. Otherwise the base layer lies about its runtime |
| One beat per chapter | Directions stop matching the picture. Split any beat whose direction lists several things |
| Rendering one style because it seems like the obvious fit | The set is the point. Comparing four framings of the same material is what picks the edit |
| Facts drifting between takes | A style changes framing, never claims. If a number is wrong in one take it is wrong in all of them |
| Trusting the duration as the shoot length | See Calibration. It is a floor |
| Sizing chunks by word count | Punctuation drives duration as much as words do. Run `--estimate` |
| Reaching for `tempo` to fix pacing | It stretches phonemes and sounds sluggish. Widen gaps instead |
| Piping a batch render through `grep` | You lose the traceback when a take fails. Read the whole log, or check the exit code |
| Vertical chunks that just continue each other | Each clip gets seen alone. Repeat whatever context it needs and give every one its own hook and CTA |
| A vertical chunk that runs long | Past ~40 seconds it stops being a social clip. Split it, or cut the setup |
| Carrying horizontal holds into a vertical cut | Long silences read as dead air on social, and they mask the real cut points. Trim to 3 seconds or remove |
| Assuming ffmpeg can draw the text | Many builds ship without `libass` and `drawtext`. This renders frames in Pillow and pipes raw RGB, so it does not care |

## Files

- `styles/*.md` — one file per style. Edit to tune, add to extend.
- `styles/README.md` — the style file format, and how to add one.
- `scripts/build.py` — the renderer. Run with no arguments for usage.
- `scripts/dg.py` — Deepgram TTS and STT helpers, key lookup, no printing of secrets.
