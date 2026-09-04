# The seven surfaces, across two branches

Not every campaign earns every one. Declining is a first-class outcome and the
proposal must say why, not silently omit.

The two branches are peers and run the same length. There is exactly one
asymmetry: video derives from the personal blog only, because those go to
the advocate's own channels.

## Personal

| Surface | Limit | Earn it when |
| --- | --- | --- |
| `personal_blog` | 1,200 words | There is a ledger. The story is what it was like, and it cannot be reconstructed later. |
| `personal_thread` | 280 chars | Nearly always. One canonical, rendered per platform. |
| `personal_linkedin` | 3,000 chars | The work reads to an audience that will not clone anything. Text plus images, and voiceless demos rather than narrated video. |
| `personal_video_script` | 15 min | Watching it beats reading about it. The only surface that produces renders. |

## Corporate

| Surface | Limit | Earn it when |
| --- | --- | --- |
| `corporate_blog` | 1,500 words | The technique generalizes past this project and the claim is proven, not simulated. |
| `corporate_thread` | 280 chars | The corporate blog is live and worth pointing at. |
| `corporate_linkedin` | 3,000 chars | Same as personal, in the company's voice. |

## A derivative cannot be kept without its blog

Every derivative projects from its branch's blog. Keeping `personal_thread`
without `personal_blog` is not a smaller campaign, it is a Gate B task waiting
on a Gate A task nobody files, so `build_tasks` refuses it outright.

## One canonical thread, rendered per platform

X, Bluesky and Threads carry the same content and differ only in limits, so
they are one surface and one write, not three.

| Platform | Limit | Quirk |
| --- | --- | --- |
| X | 280 | every URL billed at 23 chars regardless of length, max 2 links per post |
| Bluesky | 300 | no data yet, treat as X with more room |
| Threads | 500 | longest, fewest posts needed |

## Every derivative fans out to all four styles

`technical`, `build-it-too`, `fun`, `user-demo`. No picking a style per
surface. A blog has no variants because it is the source the variants come
from.

The style contracts live at
`claude-code/skills/core/script-to-video/styles/`, one file each, and govern
threads and video alike. **They are never copied into a project repo.** A
second copy is the copy that goes stale.

## Defer rather than decline when

The angle is real but the evidence is not in yet. Say which evidence, and what
would change the answer.

## Do not offer at all when

Something outside the work genuinely forecloses it: a partner NDA that
forbids naming the integration, a feature the repo does not build yet, an
event the footage was promised to first. Proposing what cannot be done
wastes the reader's judgment.

A missing LICENSE is not one of these. It is a gate task to be cleared, not
a reason to decline a surface: `build_tasks` already puts "Decide public,
and add a LICENSE" ahead of the Gate A blogs, and every other surface reaches
a blog through the chain, so the drop waits on it and the drafting does not.
Decline a surface for what it cannot do, not for a prerequisite that has its
own task.
