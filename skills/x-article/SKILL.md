---
name: x-article
description: Use when an approved blog draft has to ship as a long-form X Article from the advocate's own handle, with a mirror on their personal blog and a run of standalone posts that keep linking back to it for the next few weeks. Covers adapting the draft for X (no code blocks, no tables), UTM tagging per surface, the paste page for the composer, the 5:2 cover, the caption, the personal-blog variants, and the post schedule. Triggers include "make the X Article", "post this as an X Article", "turn this into an X Article and a tweet series", "schedule tweets for this post", "mirror this on my blog", and /x-article.
---

# X Article

One approved draft becomes three surfaces, published together:

| Surface | Job | Canonical? |
|---|---|---|
| **X Article** | Reach. Where the conversation is this week | No, a mirror |
| **Personal blog mirror** | Search. The page engines and AI answers can index and cite | **Yes** |
| **Post series** (10 to 15 posts) | Keep it alive for three to four weeks after launch | Links back to one of the two above |

A lighter **first-person post** is optional, a fourth surface for the advocate's own blog or LinkedIn
later. It is never the mirror.

## Before you start

- **Source is an approved draft**, gate A or later from `advocacy-cycle`, or a draft a reviewer has
  signed off. Never derive from an unreviewed draft. The mirror copies it, so its mistakes ship twice.
- **Settings** live in `~/.claude/advocacy-workflow.yml`. If any of these are missing, ask once and
  tell the user to add them (the file keeps keys it does not know):

  ```yaml
  x_handle: "@handle"                    # who posts
  person_slug: "first_last"              # utm_content prefix, the person credited
  blog_base_url: "https://example.com/blog"
  blog_utm_source: "firstlast_blog"
  utm_domains: "company.com,docs.company.com"   # only these get tagged
  launch_blackouts: "2026-10-14,2026-10-15"      # company launch days, no posts
  ```

## 1. Adapt the draft for X

X Articles support headings, subheadings, bold, italics, strikethrough, lists, links, images, video,
GIFs and embedded posts. **They have no code blocks, no tables, and no inline code.** Pasted
backticks show up as literal backticks.

Write `x-article.md` from the approved draft:

1. **Code becomes images.** Render each substantial block as a card in the project's visual style,
   trimmed for reading, and link the full runnable code from a public gist on the work account.
   One-liners become plain text in the sentence. Run the trimmed code you put in an image. If it
   doesn't run, don't publish it.
2. **Tables become lists**, one item per row, with the numbers in bold. If a table genuinely needs
   columns, render it as an image.
3. **Keep the text as approved.** Only change what X forces you to change, and fix any caption that
   referred to a table ("the table above" becomes "the list above").
4. **Hero video first.** Captions have to carry the story, because X autoplays video muted. A 20 to
   30 second cut beats a long screen capture. Replace any synthetic voices with the company's current
   product voices when there's a choice.

## 2. Tag the links, per surface

`utm_source` names the platform and `utm_content` names the person and placement. **Never put the
person in `utm_source`.** That breaks every source report marketing runs.

| Surface | source | medium | content |
|---|---|---|---|
| X Article | `x` | `social` | `<person_slug>_article` |
| Series post | `x` | `social` | `<person_slug>_post` |
| Reply | `x` | `social` | `<person_slug>_reply` |
| Blog mirror | `<blog_utm_source>` | `referral` | `<person_slug>_blog` |

`utm_campaign` is one snake_case slug per piece, shared by every surface. Tag only `utm_domains`.
Leave vendors, GitHub, gists and X links untagged.

```bash
S=${CLAUDE_PLUGIN_ROOT:-$(ls -d ~/.claude/plugins/cache/advocacy-workflow/advocacy-workflow/*/ | tail -1)}/skills/x-article/scripts
python3 "$S/utm.py" x-article.md x-article.md --domains "$DOMAINS" \
  --source x --medium social --campaign "$CAMPAIGN" --content "${PERSON}_article"
```

Companies often restrict who may mint UTM values. Post the scheme where marketing ops will see it as
an FYI. Don't block the launch waiting for a reply.

## 3. Build the paste page and the cover

```bash
python3 "$S/x_paste.py" x-article.md x-article-paste.html --assets "$(pwd)/assets" --title "$TITLE"
```

It refuses a draft that still has a code fence or a table. Every red box on the page shows the file's
**absolute path**, so nobody has to go hunting for it. Open the page in the browser once. After
that, tell the user to refresh the tab.

**Cover:** X recommends 5:2. Render a dedicated 2000x800 card, because a crop of a 16:9 card cuts off
the header or the footer. Make the two brand names the largest text, a short hook second, and one
concrete number third. Leave out footers and working labels.

## 4. The personal blog mirror

- **Same text as the Article**, with real code blocks restored (the blog can hold them) and the blog
  UTMs swapped in.
- **The page must be crawlable and carry its metadata:** a self-referencing canonical tag, `og:image`
  and `twitter:image` set to the cover as absolute `https://` URLs, and the page listed in the
  sitemap. Check the live HTML after deploy, not the build output.
- **Publish it five minutes before the Article.** The mirror gets the earlier timestamp, and the
  Article gets a real URL to point to. Then edit the Article to add one line at the end: "Also on my
  blog, with copyable code: [link]".

## 5. The optional first-person variant

Follow `voice_personal` and `personal-style`. **It describes the final build only:** what it is, why
it was built, and how it works now. No mistakes, no dead ends, no lessons learned, no limitations,
and it ends on a concrete call to action. It is a different piece from the mirror. Use it on the
advocate's blog later or as the LinkedIn text, never as a duplicate of the mirror.

## 6. Publish

X Articles cannot be scheduled from the composer. They are published by hand.

1. **Pick a slot:** mid-week, around 9:00 AM Pacific (noon Eastern). Never a date in
   `launch_blackouts`, and never on the same day as another piece in the series.
2. **Caption, 256 characters maximum.** X adds the Article link itself. Lead with the person's own
   situation, then the one idea and one number. Tag the other products' handles in the caption, not
   in the first line of the body. Offer two options: one that leads with the idea and one that
   leads with the person.
3. **Save the caption somewhere outside the composer.** It may not survive closing the publish dialog.
4. **Stay online for the first hour.** Early replies drive the reach.

## 7. The post series

Write `x-series.md`: **10 to 15 standalone posts**, each built from **one** fact, number, image, or
code idea taken from the Article. None is a summary of the whole piece.

- **Each post stands alone.** A reader who never sees the Article still gets something.
- **One number per post**, taken from the Article, so every claim is already reviewed. No new claims.
- **Rotate the angle:** the problem, the pattern, a surprising number, a picture (a card from the
  Article), a how-to (a code image), and what someone asked in a reply. Posts from a personal handle
  describe what works, so no "where it falls short" post.
- **Links:** about half point to the X Article (it stays on-platform) and half to the blog mirror
  with `_post` UTMs on the owned links inside the post. On X, put an external link in the first reply
  rather than the post body, since posts with links in the body get less reach.
- **Schedule:** two to three a week, Tuesday to Thursday mornings, across three to four weeks.
  Nothing on a blackout date. Front-load the strongest three into the first week.
- **Format each entry as:** number, date and time, angle, the post text (280 characters, or the
  premium limit if the account has one), media file with its absolute path, the link, and where the
  link goes (body or reply).
- Run `de-slop` over the whole series before the user loads the scheduler.

## Done means

- [ ] Every code image's trimmed code was run
- [ ] Every owned link carries the right `utm_content` for its surface, and nothing else is tagged
- [ ] The paste page has no code fences or tables, and shows an absolute path for every file
- [ ] The cover is 5:2
- [ ] The mirror is live, canonical to itself, with `og:image` set, checked in the live HTML
- [ ] The Article is published, and edited afterward to link the mirror
- [ ] `x-series.md` is written, de-slopped, and every date is clear of the blackouts
- [ ] The UTM scheme was posted to marketing ops as an FYI

## Notes

- **The X API can create and publish Articles** (`POST /2/articles/draft`, then `/publish`, with the
  body in DraftJS `content_state`). It is pay-per-use with no free tier, and code blocks are still
  unsupported. For a handful of posts the paste page is cheaper. Revisit if a funded company
  developer app exists.
- **The first run of this skill** was a voice-agent demo post, shipped as a reviewed company-blog
  draft reposted as an X Article, with a mirror on the advocate's site.
