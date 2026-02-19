#!/usr/bin/env python3
"""Normalize formatting in _companies/*.md.

Goals:
- Avoid giant nested H1/H2 headings inside company pages (Jekyll already provides page title).
- Remove duplicate/disruptive disclaimer headings.

Heuristics (safe, reversible via git):
- Keep YAML frontmatter unchanged.
- Keep the first H2 heading (company title) unchanged.
- For the remainder of the file:
  - demote Markdown headings by +3 levels (# -> ####, ## -> #####, ### -> ######)
  - drop lines that are exactly "## Not financial advice." or "# Not financial advice." etc.
  - collapse consecutive duplicate "**Not financial advice.**" lines into one.
"""

from __future__ import annotations

import re
from pathlib import Path


def split_frontmatter(md: str) -> tuple[str, str]:
    if not md.startswith("---\n"):
        return "", md
    parts = md.split("---\n", 2)
    if len(parts) < 3:
        return "", md
    fm = "---\n" + parts[1] + "---\n"
    body = parts[2]
    return fm, body


def demote_heading(line: str) -> str:
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if not m:
        return line
    hashes, rest = m.group(1), m.group(2)
    level = len(hashes)
    # Demote by +3, cap at 6.
    new_level = min(6, level + 3)
    return ("#" * new_level) + " " + rest + "\n"


def normalize_company(md: str) -> str:
    fm, body = split_frontmatter(md)
    lines = body.splitlines(True)

    # Find first H2 (company title) and keep it as-is.
    first_h2_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            first_h2_idx = i
            break

    out = []
    if first_h2_idx is None:
        # No H2 found; just normalize all lines.
        first_h2_idx = -1

    # Pass-through up to and including the first H2
    if first_h2_idx >= 0:
        out.extend(lines[: first_h2_idx + 1])
        rest_lines = lines[first_h2_idx + 1 :]
    else:
        rest_lines = lines

    # Normalize the rest
    prev_disclaimer = False
    for ln in rest_lines:
        stripped = ln.strip()

        # Drop disclaimer headings (they render weirdly)
        if re.fullmatch(r"#{1,6}\s+Not financial advice\.?", stripped, flags=re.I):
            continue

        # Collapse repeated bold disclaimers
        if stripped == "**Not financial advice.**":
            if prev_disclaimer:
                continue
            prev_disclaimer = True
            out.append(ln)
            continue
        prev_disclaimer = False

        # Demote headings to avoid nested huge headings
        if ln.lstrip().startswith("#"):
            out.append(demote_heading(ln))
        else:
            out.append(ln)

    normalized = (fm + "".join(out)).rstrip() + "\n"
    return normalized


def main() -> None:
    root = Path("_companies")
    paths = sorted(p for p in root.glob("*.md") if p.is_file())
    changed = 0
    for p in paths:
        before = p.read_text(encoding="utf-8")
        after = normalize_company(before)
        if after != before:
            p.write_text(after, encoding="utf-8")
            changed += 1
    print(f"ok: true\nchanged: {changed}\n")


if __name__ == "__main__":
    main()
