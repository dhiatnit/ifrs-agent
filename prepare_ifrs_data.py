#!/usr/bin/env python3
"""
Extract selected IFRS/IAS standards from the EU-endorsed full text
(Regulation (EU) 2023/1803, downloaded from the Publications Office
Cellar as XHTML) into per-standard Markdown files for indexing.

This plays the role crawler.py plays in the original studentsbot:
it produces the .md files in output_crawler/ that bot_review.py indexes.

Usage:
    python prepare_ifrs_data.py [path/to/ifrs_eurlex_full.html]
"""

import os
import re
import sys

from bs4 import BeautifulSoup

SOURCE_HTML = "data_src/ifrs_eurlex_full.html"
OUTPUT_DIR = "output_crawler"

# (regex number key, short id, full name) — the standards we keep
TARGET_STANDARDS = {
    ("ACCOUNTING", 2): ("IAS 2", "Inventories"),
    ("ACCOUNTING", 16): ("IAS 16", "Property, Plant and Equipment"),
    ("ACCOUNTING", 36): ("IAS 36", "Impairment of Assets"),
    ("FINANCIAL REPORTING", 15): ("IFRS 15", "Revenue from Contracts with Customers"),
    ("FINANCIAL REPORTING", 16): ("IFRS 16", "Leases"),
}

TITLE_RE = re.compile(
    r'<p[^>]*class="oj-ti-grseq-1"[^>]*>\s*'
    r'<span class="oj-bold">\s*'
    r'INTERNATIONAL (ACCOUNTING|FINANCIAL REPORTING) STANDARD (\d+)\s*</span>',
)


def clean(text):
    """Collapse whitespace in extracted text."""
    return re.sub(r"\s+", " ", text or "").strip()


MARKER_RE = re.compile(r"[0-9]+[A-Z]?\.?|\([a-z]+\)|\([ivxl]+\)|[A-Z][0-9]*\.?")


def table_to_markdown(table):
    """Render an OJ table. Numbered-paragraph rows become '**n** text'
    lines; anything else becomes a plain ' | '-joined row dump.

    Sub-lists like (a)/(b)/(c) are nested tables INSIDE a paragraph's
    cell. We only walk this table's own rows and own cells; the nested
    content is captured once via get_text on the containing cell."""
    lines = []
    for tr in table.find_all("tr"):
        # skip rows that belong to a nested table — their text is already
        # included by get_text() on the outer cell that contains them
        if tr.find_parent("table") is not table:
            continue
        cells = [clean(td.get_text(" ")) for td in tr.find_all(["td", "th"], recursive=False)]
        cells = [c for c in cells if c]
        if not cells:
            continue
        # typical paragraph row: ['2', 'This Standard applies to ...']
        # or with sub-marker: ['(a)', 'held for sale ...']
        if (len(cells) >= 2
                and all(MARKER_RE.fullmatch(c) for c in cells[:-1])
                and not MARKER_RE.fullmatch(cells[-1])):
            marker = " ".join(cells[:-1])
            lines.append(f"**{marker}** {cells[-1]}")
        else:
            lines.append(" | ".join(cells))
    return "\n\n".join(lines)


def fragment_to_markdown(html_fragment, std_id, std_name):
    """Convert one standard's XHTML slice to Markdown."""
    soup = BeautifulSoup(html_fragment, "html.parser")
    out = [f"# {std_id} — {std_name}", ""]
    seen_name_heading = False
    for el in soup.find_all(["p", "table"], recursive=False):
        if el.name == "table":
            md = table_to_markdown(el)
            if md:
                out.append(md)
                out.append("")
            continue
        text = clean(el.get_text(" "))
        if not text:
            continue
        classes = el.get("class") or []
        is_heading = any(c.startswith("oj-ti-grseq") for c in classes)
        if is_heading:
            # skip the standard's own title/name headings (already in #)
            if text.upper().startswith(("INTERNATIONAL ACCOUNTING STANDARD",
                                        "INTERNATIONAL FINANCIAL REPORTING STANDARD")):
                continue
            if not seen_name_heading and text == std_name:
                seen_name_heading = True
                continue
            out.append(f"## {text}")
            out.append("")
        else:
            out.append(text)
            out.append("")
    return "\n".join(out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SOURCE_HTML
    if not os.path.exists(src):
        print(f"Source file not found: {src}")
        sys.exit(1)

    html = open(src, encoding="utf-8").read()
    print(f"Loaded {src} ({len(html) / 1e6:.1f} MB)")

    # locate every standard title; slice the document between titles
    matches = list(TITLE_RE.finditer(html))
    print(f"Found {len(matches)} standard titles in the document")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    written = []
    for i, m in enumerate(matches):
        kind, num = m.group(1), int(m.group(2))
        key = (kind, num)
        if key not in TARGET_STANDARDS:
            continue
        std_id, std_name = TARGET_STANDARDS[key]
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        print(f"Extracting {std_id} {std_name} ({(end - start) / 1e3:.0f} kB of XHTML)...")
        md = fragment_to_markdown(html[start:end], std_id, std_name)
        fname = f"{std_id.replace(' ', '_')}_{re.sub(r'[^A-Za-z]+', '_', std_name).strip('_')}.md"
        path = os.path.join(OUTPUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        written.append((path, len(md)))

    print()
    for path, size in written:
        print(f"  wrote {path} ({size / 1e3:.0f} kB)")
    print(f"\n{len(written)}/{len(TARGET_STANDARDS)} target standards extracted into {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
