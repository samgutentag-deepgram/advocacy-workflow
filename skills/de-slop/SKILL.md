---
name: de-slop
description: Use when a draft is factually settled and about to go to a reviewer, and it needs the machine fingerprints taken out. Triggers include "de-slop this", "run a de-slop pass", "does this read like AI wrote it", "this sounds machine-written", "find the AI tells", "hunt the AI-isms", a reviewer saying a piece reads as AI, and /de-slop. A rhythm edit, not a rewrite: structure, claims, and length stay put.
---

# De-slop

How to get the machine fingerprints out of a draft before anyone else reads it.

The one thing to carry into every pass: **the surface tells are individually worthless, and the
real giveaway is conceptual incoherence.** Word lists are the least useful part of this skill.

---

## When to use

**Whichever voice a draft is in, it gets the de-slop pass before anyone else reads it.** Every
draft, every voice, no exceptions.

- A draft is written, the facts are settled, and it has not gone to a reviewer yet.
- A reviewer already said a piece reads as AI-written, and you need to find out where.
- You want a second pass on your own prose before publishing.

**A corporate draft needs this pass more than a personal one.** That is backwards from what you
would guess. Corporate voice runs at a flatter register, and the flatness hides the tics that a
first-person draft would make obvious. In a personal draft the machine sentences stick out against
the voice around them. In a corporate draft they blend in.

**Do not use it** to restructure, to re-argue claims, or to cut length. Those are different jobs.
This pass changes rhythm and word choice only.

### How this sits next to the other writing skills

| Skill | Job |
| --- | --- |
| the configured voice skill | Voice. How the piece was written in the first place. |
| `corporate-style` | The company voice, including one term per concept, every time. |
| `de-slop` | A separate, later pass that removes machine fingerprints from a finished draft. |

De-slop runs after the others, on a finished draft. It can conflict with `corporate-style` in
exactly one way: a naive pass flags repeated domain terms, and `corporate-style` requires them.
**`corporate-style` wins. De-slop never overrides one term per concept.**

---

## The rule that matters

> "The number one giveaway of LLM writing is not the punchy ad copy sentences, the overuse of
> honestly and delve, the use of it's not X, it's Y comparisons, and rhetorical groupings of three.
> It's the absolute conceptual incoherence behind common word choices."

LLMs put words together that co-occur in a corpus without checking that the concepts behind them
cohere. The result reads fine at a glance and falls apart the moment you picture it.

These four examples are the shape to hunt for. Memorize them.

| Phrase | Why it is incoherent |
| --- | --- |
| "nestled amid a year of war" | A military offensive does not nestle. |
| "two overarching pillars that undergird" | Pillars do not overarch, and nothing overarches and undergirds at once. |
| "words aren't just empty containers, a blank slate to be filled" | You fill a container and you fill a slate, but those are two unrelated senses of fill. |
| "two related toolkits and see what they buy you when you point them at a problem" | Toolkits do not buy you anything, and you do not point one at a problem. Named in the video as a Claude output. |

**Read for this. You cannot grep for it.** Every mixed metaphor in that list uses ordinary words in
ordinary collocations. The failure is at the concept level, which means a human has to picture the
sentence and notice it does not resolve.

The corollary the video is honest about: incoherent writing is bad writing whether a machine or a
person produced it. Do not spend the review deciding which. Fix it either way.

Fixing it means repairing the phrase until it resolves. It does not mean deleting the passage or
reshaping the paragraphs around it. The claim stays, the length stays, the metaphor changes.

---

## The cluster tells

None of these is evidence on its own. All of them are ordinary rhetoric, and the video is explicit
that LLMs trip them because LLMs follow writing best practices. A cluster is the signal.

**Constructions**

- **The DiGiorno construct**, "it's not X, it's Y." The video's name for it, and it is the single
  most reliable member of the cluster. Measured at **17 instances in 2,662 words** in our own
  corporate draft before the pass.
- **Explicit self-validation.** "And that matters." "Here's the thing." The sentence that tells the
  reader the previous sentence was important.
- **Groupings of three**, parentheticals, and thoughts set off with dashes. Classical rhetoric, and
  the video flags that academic writing is full of them. Low signal alone, real signal in a cluster.
- **Punchy ad-copy fragments.** "Honestly." "The catch." A sentence fragment doing a paragraph's job.
- **Aphoristic section-closers.** A portable maxim at the end of every section. One per piece is
  writing. One per section is a pattern.
- **Identically-shaped headers.** Our five step headers were all "Step N: <colon> <wry subclause>."

**Pet words**, per the video, by model

| Source | Words |
| --- | --- |
| General | delve, honestly, actually, "and that matters", gap, blueprint |
| Gemini | buckets, gaps |
| **Claude** | **toolkit, move** |
| ChatGPT voice | "Sure thing", "That's a really great question" |
| The presenter's own peeve | the expanding use of **quietly** and **amid** |

**Ours, added from the HN Radio pass**

- **"worth ~ing"** as an insight hedge. "Worth saying out loud", "worth knowing about", "worth
  sitting with." The reviewer's note is the fix: if it were not worth it you would not have written it. Six in
  2,662 words.
- **Flat register.** That draft had **one contraction in 2,662 words**. Every sentence was correct
  and the whole thing read like a machine.
- **A piece narrating its own budget.** "The reason it is worth 400 words."

---

## What not to do

**Do not build a word blacklist.** The HN Radio corporate post uses **gap 21 times**, which would
light up any list that includes Gemini's tic. In that post a gap is the silence between two audio
segments. It is the domain term, it is the subject of an entire section, and every use is correct.
A blacklist would have made the piece worse.

The same is true of `quietly` in "it quietly produces MPEG-2 Layer III." That failure genuinely is
silent, and naming it is the point of the paragraph.

One term per concept, every time, is already the rule in `corporate-style`. A de-slop pass must not
fight it.

If the output of this skill reads as a list of banned words, the pass failed.

---

## The pass

Run it after the draft is factually settled and before it goes to anyone else. It is a rhythm edit,
not a rewrite: structure, claims, and length stay put.

1. **Count, then cut.** From the cycle's publish directory:

   ```bash
   f=publish/corporate-blog.md
   grep -cE "is not [a-z]|are not [a-z]|, not [a-z]" $f    # DiGiorno construct
   grep -cE "worth [a-z]+ing|is worth "                $f  # insight hedge
   grep -coE "rather than"                             $f
   grep -cE '(^|\. )(That is|It is|This is)\b'         $f  # flat openers
   grep -coE "[A-Za-z]+'(t|re|ve|ll|s)\b"              $f  # contractions, want MORE
   ```

   Every count on that list should go **down** except the last one. The contraction count is the
   one you want to go **up**.

   The patterns are case-sensitive, so a sentence-initial "Worth sitting with" slips past the hedge
   count. Treat the numbers as a floor, not a census.

2. **Cap the DiGiorno construct at three**, and keep only the ones where the negation preempts a
   specific wrong assumption the reader actually holds. "`-ar 44100` is a compatibility flag, not a
   quality setting" survives because readers do assume it is a quality setting.
3. **Zero "worth ~ing."** Assert the thing instead.
4. **One aphorism per piece**, at most.
5. **Vary the headers.** Use plain imperatives for procedures, per `corporate-style`.
6. **Let contractions in.** Corporate voice is flatter than personal voice, not airless.
7. **Read every metaphor out loud and picture it.** This is the step that catches the real tell, and
   it is the only step a script cannot do for you. Skipping this is how the HN Radio corporate post
   reached a reviewer sounding machine-written on 2026-08-25.

### What the pass reports

A finished run reports three things, in this order. A run that gives only the after numbers, or
that leaves out the metaphor read, does not satisfy the cycle's exit checklist.

1. **A before and after count table** for the grep-able tells, one row per count in step 1. Run the
   greps before you edit, keep the numbers, run them again after.

   | Tell | Before | After |
   | --- | --- | --- |
   | DiGiorno construct | | |
   | "worth ~ing" hedges | | |
   | Flat openers | | |
   | Contractions (want this one up) | | |

2. **An explicit statement that step 7 happened**, and what it found. Name the metaphors you read
   out loud and how each one resolved, or say plainly that none of them broke. "Read the metaphors"
   with nothing after it is not a report.
3. **Anything you deliberately left alone**, and why. Domain terms held under `corporate-style` go
   here, so the next reader knows the repetition was a decision.

### What done looks like

Calibration numbers from the HN Radio corporate post, so a later session knows when to stop:

| Tell | Before | After |
| --- | --- | --- |
| DiGiorno construct | 17 | 6 |
| "worth ~ing" hedges | 6 | 0 |
| Contractions | 1 | 16 |
| Aphorisms | 5 | 1 |

All in 2,662 words. The piece finished at 2,655 words against a 2,800 cap, seven fewer than before,
with a new intro, a new pipeline section and a new API lead-in added in the same pass. The de-tell
paid for the additions.

---

## What the video says LLMs are good for

Recorded because the cycle uses them and the honest version of this has to say so.

- Boilerplate, and first drafts of easily verifiable information.
- "Read this draft. Are there any glaring omissions?" Finding what is missing and what can be cut.
- Trimming fat.

The failure case it names is the one to avoid: using a model for material you do not already know,
which produces "a dramatic reading of my own Google results."

---

## Provenance

Two sources, both from 2026-08-25:

- **A reviewer's comments** on the HN Radio corporate blog: *"this is a glaring tell that
  something was written by AI. I would comb through the article and find instances of this type of
  thing"* and *"Be more assertive, if it wasn't 'worth knowing' you wouldn't have written it."*
- **["How to Detect AI Slop"](https://www.youtube.com/watch?v=ORgKY9AlybA)**, Dr. Taylor Jones
  (Language Jones), PhD linguistics, UPenn. Transcript pulled and read in full.

The two agree on the surface tells. The video adds the part a review comment did not have room for:
the surface tells are individually worthless, and the real giveaway is something else entirely.

This skill was ported from `docs/de-slop.md` in the retired `advocacy-plan` repo.
