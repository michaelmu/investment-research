#!/usr/bin/env python3
"""Publish a research note into the investment-research Jekyll site.

This is a local tool. It does NOT push to GitHub.

It supports two outputs:
- A per-company living page in `_companies/<ticker>.md` (append newest entry at top)
- An optional dated post in `_posts/YYYY-MM-DD-<ticker>-<slug>.md`

Usage examples:
  ./scripts/publish.py --ticker ETN --name "Eaton" --category "compounder, ai-beneficiary" \
    --title "Eaton deep dive" --kind deep-dive --body-file /tmp/note.md --also-post

  echo "hello" | ./scripts/publish.py --ticker CPRT --name "Copart" --title "CPRT note" --stdin

Conventions:
- All content is "Not financial advice" by default.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import subprocess


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "note"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_body(args: argparse.Namespace) -> str:
    if args.stdin:
        return Path("/dev/stdin").read_text(encoding="utf-8")
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    raise SystemExit("Provide --stdin or --body-file")


@dataclass
class Entry:
    title: str
    kind: str
    updated: str
    body: str


def entry_block(e: Entry) -> str:
    return (
        f"\n\n---\n\n"
        f"### {e.title}\n"
        f"*Kind:* {e.kind}  \\ \n"
        f"*Updated:* {e.updated}\n\n"
        f"{e.body.strip()}\n\n"
        f"**Not financial advice.**\n"
    )


def ensure_company_page(path: Path, ticker: str, name: str, category: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"ticker: {ticker}\n"
        f"name: {name}\n"
        f"category: {category}\n"
        f"updated: {date.today().isoformat()}\n"
        "---\n\n"
        f"## {name} ({ticker})\n\n"
        "**Not financial advice.**\n",
        encoding="utf-8",
    )


def update_frontmatter(md: str, updated: str, category: Optional[str] = None, name: Optional[str] = None) -> str:
    # Extremely small YAML edit: update 'updated:' line and optionally name/category if provided.
    if not md.startswith("---\n"):
        return md
    parts = md.split("---\n", 2)
    if len(parts) < 3:
        return md
    fm = parts[1].splitlines()
    out = []
    seen_updated = False
    for ln in fm:
        if ln.startswith("updated:"):
            out.append(f"updated: {updated}")
            seen_updated = True
        elif name and ln.startswith("name:"):
            out.append(f"name: {name}")
        elif category and ln.startswith("category:"):
            out.append(f"category: {category}")
        else:
            out.append(ln)
    if not seen_updated:
        out.append(f"updated: {updated}")
    return "---\n" + "\n".join(out) + "\n---\n" + parts[2]


def insert_after_h2(md: str, block: str) -> str:
    # Insert right after the first H2 heading ("## ...") if present.
    lines = md.splitlines(True)
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            # insert after heading line + possible blank line(s)
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            return "".join(lines[:j]) + block + "".join(lines[j:])
    return md + block


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--category", default="")
    ap.add_argument("--title", required=True)
    ap.add_argument("--kind", default="note")
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--also-post", action="store_true")
    ap.add_argument("--post-tag", default="research", help="slug fragment for post filename")
    ap.add_argument("--commit", action="store_true", help="git add + commit the generated files")
    ap.add_argument("--commit-message", default=None, help="commit message (default auto)")
    ap.add_argument("--push", action="store_true", help="git push after commit")

    args = ap.parse_args()
    ticker = args.ticker.upper().strip()
    name = args.name or ticker
    category = args.category

    body = read_body(args)

    updated = date.today().isoformat()
    entry = Entry(title=args.title, kind=args.kind, updated=updated, body=body)
    block = entry_block(entry)

    company_path = Path("_companies") / f"{ticker.lower()}.md"
    ensure_company_page(company_path, ticker=ticker, name=name, category=category or "")

    md = company_path.read_text(encoding="utf-8")
    md = update_frontmatter(md, updated=updated, category=category or None, name=name)
    md = insert_after_h2(md, block)
    company_path.write_text(md, encoding="utf-8")

    post_path: Optional[Path] = None
    if args.also_post:
        posts = Path("_posts")
        posts.mkdir(parents=True, exist_ok=True)
        slug = slugify(f"{ticker}-{args.post_tag}-{args.title}")
        fname = f"{updated}-{slug}.md"
        post_path = posts / fname
        post_path.write_text(
            "---\n"
            f"layout: post\n"
            f"title: " + args.title.replace('"', '\\"') + "\n"
            f"ticker: {ticker}\n"
            f"kind: {args.kind}\n"
            f"published_at: {now_iso()}\n"
            "---\n\n"
            f"## {name} ({ticker})\n\n"
            f"{body.strip()}\n\n"
            "**Not financial advice.**\n",
            encoding="utf-8",
        )

    # Optional git ops
    commit_sha = None
    pushed = False
    if args.commit or args.push:
        # Stage generated files
        paths = [str(company_path)]
        if post_path:
            paths.append(str(post_path))
        subprocess.run(["git", "add", "--"] + paths, check=True)

        msg = args.commit_message or f"Publish {ticker} {args.kind}: {args.title}"
        # Commit may fail if no changes; treat that as non-fatal.
        c = subprocess.run(["git", "commit", "-m", msg], capture_output=True, text=True)
        if c.returncode == 0:
            # Read HEAD sha
            commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        else:
            stderr = (c.stderr or "") + (c.stdout or "")
            if "nothing to commit" not in stderr.lower():
                raise SystemExit(stderr.strip())

        if args.push:
            p = subprocess.run(["git", "push"], capture_output=True, text=True)
            if p.returncode != 0:
                # Don't crash the whole publish; surface actionable error.
                eprint("WARN: git push failed. Configure auth (SSH deploy key or PAT).")
                eprint((p.stderr or p.stdout or "").strip())
            else:
                pushed = True

    lines = [
        "ok: true",
        f"company_page: {company_path}",
        *( [f"post: {post_path}"] if post_path else [] ),
        *( [f"commit: {commit_sha}"] if commit_sha else [] ),
        f"pushed: {str(pushed).lower()}",
    ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
