---
name: personal-style
description: Use when drafting or editing the advocate's personal voice for developer content (the first-person "what I built and how it works" post, the personal social thread, the personal half of an advocacy cycle's two drafts). Honest, human, advocate-authored, distinct from the company's corporate voice. Triggers include "personal voice", "the personal post", "the personal blog". An advocate with their own documented voice skill names it in `voice_personal` and that governs their exact tone.
---

# Personal Style

## Overview

The advocate's own voice, written as a person, not the company. Honesty is the constraint that dominates: you are explaining something you built to a smart peer, and every claim holds up. This guide is the shared frame any advocate uses. It does not impose one person's idiosyncrasies. An advocate with their own documented voice skill, named in `voice_personal`, uses that for their exact tone; this guide governs the shape.

Pairs with `corporate-style`. The cycle produces one draft in each voice from the same notes.

## Core posture

"I had a problem, here is what I did about it, maybe this saves you some time." Do not perform expertise. Have it.

## Core rules

- Start with the problem or the real context, not a preamble. No "In this post I will..."
- First person, specific, concrete.
- **Describe the final build, not the journey.** Lead with what it is and why you built it, then how it works now. No "here is what I got wrong, here is what I discovered" narrative, no dead-ends section, no lessons-learned framing. A past step earns one sentence only when it explains a current design choice, and it is stated as the reason ("the settled turn is the only one that acts, because early commits guessed wrong half the time"), not as a story.
- **State the current state, not the discovery.** "The gate reads P(none)", not "it turned out the gate should read P(none)."
- End on a concrete call to action the reader can do.
- Do not repeat the corporate post in a different order. If a reader reads both and feels they read the same thing twice, this piece has not found its angle.
- Every number and every quote still carries a source.

## Clarity (light STE)

Borrow the clarity half of [Simplified Technical English](https://skybrary.aero/articles/simplified-technical-english-ste) even in narrative: short sentences, active voice, one idea per sentence, consistent terms. Personal voice is human, not sloppy.

## Banned words and AI-isms

Never: leverage, delve, nuanced, robust, comprehensive, seamlessly, elevate, streamline, supercharge, empower, unlock. No "It's worth noting that," no "In conclusion," no hedging opener ("That's a great question"), no filler caveats ("of course," "naturally").

## Formatting

- No em dashes, ever. Use periods, commas, or parentheticals.
- Adjectives sparse and earned. One well-placed "seriously" beats three adjectives.
- Active voice over passive.
- Leave limitations out of the personal post. They belong in the repo README and the corporate post.

## Why this rule exists

Sam, 2026-09-29, after a personal draft came back structured around dead ends for the third time: "completely abandon the narrative of here's what I did wrong and here's what I discovered. I just want to talk about the final build and what I built." The ledger's `[friction]` and `[deadend]` entries are research for the reasons behind the design, not an outline for the post.

## Common mistakes

- Preamble before the point.
- A personal post that is just the corporate post reworded.
- Turning the post into a build log of mistakes. The ledger keeps the friction; the post describes the thing.
- AI-ism creep.
