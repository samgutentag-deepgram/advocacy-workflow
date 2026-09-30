"""Build a paste page for the X Articles composer from an X-ready markdown draft.

X Articles keep headings, bold, italics, lists and links when you paste rich
text, but have no code blocks, tables, or inline code. This page is the copy
source: open it in a browser, select from the first red box down, paste into
the composer, then upload each red box's file where it sits.

The draft must already be X-ready: code and tables turned into images, links
tagged. This script refuses a draft that still has a code fence or a table,
because pasting one produces a broken Article.

    python3 x_paste.py x-article.md x-article-paste.html --assets /abs/path/to/assets --title "Title"

Media lines:
    ![alt](path/file.png)                    an image, uploaded in place
    >> VIDEO: `path/file.mp4`. Caption: "..." the hero video

Run the examples with: python3 -m doctest x_paste.py -v
"""
import argparse
import html
import re
import sys

LIST = re.compile(r"^(- |\d+\. )")


def inline(t):
    """Markdown inline to HTML. Backticks are dropped: X renders them literally.

    >>> inline('Call `askJev` on **every** [eager](https://e.com) turn')
    'Call askJev on <strong>every</strong> <a href="https://e.com">eager</a> turn'
    """
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def check(body):
    """Refuse what X cannot hold.

    >>> check('fine text')
    >>> check('```ts\\nx\\n```')
    Traceback (most recent call last):
    ValueError: code fence found: render code as an image first
    """
    if "```" in body:
        raise ValueError("code fence found: render code as an image first")
    if re.search(r"^\|.*\|\s*$", body, re.M):
        raise ValueError("table found: turn it into a list or an image first")


def media(kind, name, assets, note):
    path = f"{assets.rstrip('/')}/{name}"
    return (f'<div class="media">INSERT {kind}: <b>{html.escape(name)}</b><br>'
            f'<code style="user-select:all">{html.escape(path)}</code><br><span>{note}</span></div>')


def build(md, assets, title):
    body = md.split("---\n", 2)[2] if md.startswith("---\n") else md
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"^\s*# .*\n", "", body.lstrip(), count=1)  # the title goes in the title field
    check(body)
    out = []
    for block in re.split(r"\n\s*\n", body.strip()):
        b = block.strip()
        lines = b.split("\n")
        m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)$", b)
        if m:
            out.append(media("IMAGE", m.group(2).split("/")[-1], assets, "alt text: " + inline(m.group(1))))
        elif b.startswith(">> VIDEO"):
            name = re.search(r"`([^`]+)`", b).group(1).split("/")[-1]
            cap = b.split("Caption:", 1)[1].strip().strip('"') if "Caption:" in b else ""
            out.append(media("VIDEO", name, assets, "caption: " + inline(cap)))
        elif b.startswith(">> "):
            continue  # other working notes never reach the composer
        elif b.startswith("## ") or b.startswith("### "):
            out.append(f"<h2>{inline(b.lstrip('#').strip())}</h2>")
        elif all(LIST.match(l) for l in lines):
            tag = "ol" if re.match(r"\d+\. ", lines[0]) else "ul"
            items = "".join(f"<li>{inline(LIST.sub('', l))}</li>" for l in lines)
            out.append(f"<{tag}>{items}</{tag}>")
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    css = ("body{max-width:720px;margin:40px auto;font:17px/1.55 Georgia,serif;color:#111;background:#fff;padding:0 16px}"
           "h2{font-family:-apple-system,Helvetica,sans-serif}"
           ".media{border:2px dashed #c33;background:#fff4f4;padding:10px 14px;margin:18px 0;font:14px -apple-system,sans-serif;color:#a00}"
           ".media span{color:#555}.note{font:13px -apple-system,sans-serif;color:#555;border-bottom:1px solid #ddd;padding-bottom:10px}")
    note = (f'<p class="note">Copy source for the X Articles composer. Title: <b>{html.escape(title)}</b>. '
            "Select from the first box down, paste, then upload each red box's file in its spot and delete the box. "
            "Click a path to select it; Cmd+Shift+G in the file picker takes a pasted path.</p>")
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>X Article Paste</title><style>{css}</style></head><body>{note}\n" + "\n".join(out) + "\n</body></html>")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--assets", required=True, help="absolute path to the folder holding the media")
    ap.add_argument("--title", required=True)
    a = ap.parse_args(argv)
    try:
        page = build(open(a.src).read(), a.assets, a.title)
    except ValueError as e:
        sys.exit(f"x_paste: {e}")
    open(a.out, "w").write(page)
    print(f"wrote {a.out}: {page.count('INSERT ')} media boxes", file=sys.stderr)


if __name__ == "__main__":
    main()
