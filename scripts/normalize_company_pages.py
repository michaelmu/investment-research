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


def normalize_heading(line: str) -> str:
    """Keep entry titles readable while preventing giant nested headings.

    Policy:
    - Keep H3 (###) as-is (used for per-entry titles)
    - Demote H1/H2 by +3 (so they become H4/H5)
    - Keep H4+ as-is
    - If a previous normalization produced H6 entry titles, upgrade H6->H3
    """
    m = re.match(r"^(#{1,6})\s+(.*)$", line)
    if not m:
        return line
    level = len(m.group(1))
    rest = m.group(2)

    # Upgrade mistakenly-demoted entry titles
    if level == 6:
        return "### " + rest + "\n"

    if level == 3:
        return line
    if level in (1, 2):
        new_level = min(6, level + 3)
        return ("#" * new_level) + " " + rest + "\n"
    return line


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

        # Normalize headings to avoid nested huge headings
        if ln.lstrip().startswith("#"):
            out.append(normalize_heading(ln))
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
