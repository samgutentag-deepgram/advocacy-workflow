"""Tag the owned links in a markdown draft with UTM parameters.

Only links on the domains you list get tagged. Everything else (the vendor
you wrote about, GitHub, X itself) is left alone, because a UTM on someone
else's site pollutes their analytics and tells you nothing.

    python3 utm.py draft.md out.md --domains example.com \
        --source x --medium social --campaign my_post --content jane_doe_article

Run the examples with: python3 -m doctest utm.py -v
"""
import argparse
import re
import sys
from urllib.parse import urlencode

LINK = re.compile(r"\]\((https?://[^)\s]+)\)|^\[[^\]]+\]:\s*(https?://\S+)", re.M)


def owned(url, domains):
    """True when the URL's host is one of the domains or a subdomain of one.

    >>> owned('https://docs.example.com/x', ['example.com'])
    True
    >>> owned('https://notexample.com/x', ['example.com'])
    False
    """
    host = re.match(r"https?://([^/?#]+)", url).group(1).lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def tag_url(url, params):
    """Append params, keeping any query and fragment already on the URL.

    >>> tag_url('https://example.com/a#b', {'utm_source': 'x'})
    'https://example.com/a?utm_source=x#b'
    >>> tag_url('https://example.com/a?q=1', {'utm_source': 'x'})
    'https://example.com/a?q=1&utm_source=x'
    >>> tag_url('https://example.com/a?utm_source=old', {'utm_source': 'x'})
    'https://example.com/a?utm_source=old'
    """
    if "utm_source=" in url:
        return url  # already tagged, never double-tag
    base, _, frag = url.partition("#")
    joined = base + ("&" if "?" in base else "?") + urlencode(params)
    return joined + ("#" + frag if frag else "")


def tag(text, domains, params):
    """Tag every owned inline link and reference-style definition.

    >>> tag('[a](https://example.com/p) [b](https://other.com/p)', ['example.com'], {'utm_source': 'x'})
    '[a](https://example.com/p?utm_source=x) [b](https://other.com/p)'
    >>> tag('[r]: https://example.com/p', ['example.com'], {'utm_source': 'x'})
    '[r]: https://example.com/p?utm_source=x'
    """
    def repl(m):
        url = m.group(1) or m.group(2)
        if not owned(url, domains):
            return m.group(0)
        return m.group(0).replace(url, tag_url(url, params), 1)

    return LINK.sub(repl, text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--domains", required=True, help="comma separated, e.g. example.com,example.dev")
    for k in ("source", "medium", "campaign", "content"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args(argv)
    params = {"utm_source": a.source, "utm_medium": a.medium, "utm_campaign": a.campaign, "utm_content": a.content}
    domains = [d.strip().lower() for d in a.domains.split(",") if d.strip()]
    text = open(a.src).read()
    out = tag(text, domains, params)
    open(a.out, "w").write(out)
    n = out.count("utm_content=" + a.content)
    print(f"tagged {n} links on {', '.join(domains)}", file=sys.stderr)


if __name__ == "__main__":
    main()
