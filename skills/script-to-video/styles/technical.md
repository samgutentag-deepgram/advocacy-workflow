---
key: technical
title: Technical demo
voice: flux-alexis-en
tempo: 1.0
---

# Technical demo

## Stance
Describe what the thing does and how it is built. **Not** what went wrong and what you learned.

That distinction is the whole style and it was a correction, so it is written down: a
lessons-learned narrative borrows credibility the author may not have earned, and it reads as
false when a model wrote most of the code. Describe the system, not the journey.

## Leads with
What it is and what it produces, in two sentences, then straight into mechanism.

## Emphasize
- The design decision and the constraint behind it.
- Real measured numbers with their sample size.
- Behavior of the underlying platform that a reader would want to know.

## Cut
- "Three things broke and each taught me something."
- "One thing I got wrong."
- "The bug is what shaped the design."
- Any sentence whose subject is the author's growth.

Bugs still belong in the script. Frame them as properties of the stack, not as confessions.
"The encode step targets 44.1, and that number is load bearing" carries the same fact as
"I shipped it broken" and claims nothing about the author.

## Register
Declarative. Present tense. The code is the subject of most sentences.

## Length
Match the source script's chapter count. This is the take that tracks the real edit most closely.

## Calibration line
> The encode step targets forty four point one kilohertz, and that number is load bearing. Flux
> returns twenty four, and encoding at twenty four gives you MPEG two Layer Three.
