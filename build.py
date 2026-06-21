#!/usr/bin/env python3
"""
Gravedancer to General — static site generator.

Reads episodes/*.md and lore/*.md and emits a complete static site into dist/.

Episode markdown files use YAML frontmatter for metadata and a body with
"## DAY N: Title" headers marking each daily chapter.

Usage:
    python build.py            # build to dist/
    python build.py --serve    # build, then serve dist/ at http://localhost:8000
"""

import argparse
import datetime as dt
import glob
import html
import http.server
import os
import re
import shutil
import socketserver
import sys
import xml.sax.saxutils as sx
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).parent.resolve()
EPISODES_DIR = ROOT / "episodes"
LORE_DIR = ROOT / "lore"
SRC_DIR = ROOT / "src"
TEMPLATES_DIR = SRC_DIR / "templates"
STATIC_DIR = SRC_DIR / "static"
ASSETS_DIR = ROOT / "src" / "assets"
DIST_DIR = ROOT / "dist"

WORDS_PER_MINUTE = 250  # for reading-time estimate

# ── Helpers ──────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Make a URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def count_words(text: str) -> int:
    """Word count from plain (markdown) text, ignoring markup noise."""
    # strip code fences and inline code first
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    return len(re.findall(r"\b[\w'’-]+\b", cleaned))


def reading_time(word_count: int) -> str:
    mins = max(1, round(word_count / WORDS_PER_MINUTE))
    return f"{mins} min read"


def fmt_date(date_val) -> str:
    """Format a date (date or 'YYYY-MM-DD' string) as 'Jun 20, 2026'."""
    if isinstance(date_val, str):
        date_val = dt.date.fromisoformat(date_val)
    if isinstance(date_val, dt.datetime):
        date_val = date_val.date()
    return date_val.strftime("%b %-d, %Y")


def iso_date(date_val) -> str:
    if isinstance(date_val, str):
        date_val = dt.date.fromisoformat(date_val)
    if isinstance(date_val, dt.datetime):
        date_val = date_val.date()
    return date_val.isoformat()


DAY_HEADER_RE = re.compile(r"^##\s+DAY\s+(\d+)\s*:?\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def split_into_days(body_md: str):
    """
    Split an episode body into day chapters.

    Returns a list of dicts: [{num, title, md, html, word_count, reading_time}]
    in order. If no DAY headers are found, the whole body is day 1.
    """
    matches = list(DAY_HEADER_RE.finditer(body_md))
    if not matches:
        html_body = render_markdown(body_md)
        wc = count_words(body_md)
        return [{
            "num": 1, "title": "Day 1", "md": body_md, "html": html_body,
            "word_count": wc, "reading_time": reading_time(wc),
        }]

    days = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        title = m.group(2).strip() or f"Day {num}"
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_md)
        chunk = body_md[start:end].strip()
        days.append({
            "num": num,
            "title": title,
            "md": chunk,
            "html": render_markdown(chunk),
            "word_count": count_words(chunk),
            "reading_time": reading_time(count_words(chunk)),
        })
    return days


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "smarty", "sane_lists", "toc"],
        output_format="html5",
    )


def first_paragraph_text(md_text: str, limit: int = 280) -> str:
    """Extract a plain-text excerpt (for meta description / cards)."""
    rendered = render_markdown(md_text)
    text = re.sub(r"<[^>]+>", " ", rendered)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


# ── Data loading ─────────────────────────────────────────────────────────

def load_site_config() -> dict:
    with open(ROOT / "site.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_episodes() -> list:
    """Load and sort all published-or-coming-soon episodes (drafts excluded)."""
    episodes = []
    for path in sorted(EPISODES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        if meta.get("status") == "draft":
            continue
        slug = slugify(meta.get("title", path.stem)) or path.stem
        days = split_into_days(body)
        total_words = sum(d["word_count"] for d in days)
        date_val = meta.get("published_at")
        ep = {
            **meta,
            "slug": slug,
            "days": days,
            "num_days": len(days),
            "word_count": total_words,
            "reading_time": reading_time(total_words),
            "date_obj": date_val,
            "date_long": fmt_date(date_val) if date_val else None,
            "date_iso": iso_date(date_val) if date_val else None,
            "excerpt": first_paragraph_text(body),
            "path": path,
        }
        episodes.append(ep)
    # newest first by episode number
    episodes.sort(key=lambda e: e.get("episode", 0), reverse=True)
    return episodes


def parse_frontmatter(text: str):
    """Split raw file text into (frontmatter_dict, body_str)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].strip()
    return {}, text.strip()


def load_lore() -> dict:
    """Load lore markdown files keyed by stem (about, glossary)."""
    lore = {}
    if not LORE_DIR.exists():
        return lore
    for path in sorted(LORE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        lore[path.stem] = {
            "title": meta.get("title", path.stem.replace("-", " ").title()),
            "html": render_markdown(body),
            "meta": meta,
        }
    return lore


def build_jedi_index(episodes: list) -> list:
    """Aggregate jedi info across episodes, deduped by name."""
    index = {}
    for ep in episodes:
        name = ep.get("target_jedi")
        if not name:
            continue
        entry = index.setdefault(name, {
            "name": name,
            "species": ep.get("jedi_species", "—"),
            "philosophy": ep.get("jedi_philosophy", "—"),
            "fate": ep.get("jedi_fate", "Unknown"),
            "episodes": [],
        })
        entry["episodes"].append({"episode": ep.get("episode"), "slug": ep["slug"],
                                  "title": ep.get("title")})
        # carry the most recent non-default values forward
        if ep.get("jedi_fate"):
            entry["fate"] = ep["jedi_fate"]
        if ep.get("jedi_species"):
            entry["species"] = ep["jedi_species"]
        if ep.get("jedi_philosophy"):
            entry["philosophy"] = ep["jedi_philosophy"]
    return sorted(index.values(), key=lambda j: j["name"])


def build_glossary(lore: dict) -> list:
    """Parse glossary.md '### Term — definition' lines into entries."""
    glossary = lore.get("glossary")
    if not glossary:
        return []
    text = (LORE_DIR / "glossary.md").read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    entries = []
    for block in re.split(r"\n(?=#{3,}\s)", body):
        block = block.strip()
        if not block.startswith("###"):
            continue
        m = re.match(r"###\s+(.+?)(?:\s*[—–-]\s*|\n)(.*)", block, re.DOTALL)
        if m:
            term = m.group(1).strip()
            definition = m.group(2).strip()
        else:
            term = block.lstrip("# ").split("\n", 1)[0].strip()
            definition = " ".join(block.split("\n", 1)[1:]).strip()
        entries.append({
            "term": term,
            "definition_html": render_markdown(definition),
        })
    return sorted(entries, key=lambda e: e["term"].lower())


# ── Rendering ────────────────────────────────────────────────────────────

def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["slugify"] = slugify
    env.filters["fmt_date"] = fmt_date
    env.filters["iso_date"] = iso_date
    env.filters["first_paragraph"] = first_paragraph_text
    env.filters["xml_escape"] = lambda s: sx.escape(str(s))
    env.filters["attrs"] = attrs_for_status
    env.filters["status_label"] = status_label
    return env


def attrs_for_status(status: str) -> str:
    """CSS class tokens for a status badge."""
    mapping = {
        "published": "badge badge-published",
        "coming_soon": "badge badge-soon",
        "draft": "badge badge-draft",
    }
    return mapping.get(status, "badge")


def status_label(status: str) -> str:
    return {
        "published": "Published",
        "coming_soon": "Coming Soon",
        "draft": "Draft",
    }.get(status, status or "—")


def write_page(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_site():
    config = load_site_config()
    episodes = load_episodes()
    lore = load_lore()
    jedi = build_jedi_index(episodes)
    glossary = build_glossary(lore)

    env = make_env()
    base_context = {
        "site": config,
    }

    published = [e for e in episodes if e.get("status") == "published"]
    coming_soon = [e for e in episodes if e.get("status") == "coming_soon"]
    latest = max(published, key=lambda e: e.get("episode", 0)) if published else None

    # Wipe and recreate dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # Copy static + assets
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, DIST_DIR / "static")
    if ASSETS_DIR.exists():
        shutil.copytree(ASSETS_DIR, DIST_DIR / "assets")

    # ── index.html ──
    tmpl = env.get_template("index.html")
    write_page(DIST_DIR / "index.html", tmpl.render(
        **base_context,
        episodes=episodes, published=published, coming_soon=coming_soon,
        latest=latest, jedi_count=len(jedi),
        nav_active="archive",
    ))

    # ── episode pages ──
    ep_tmpl = env.get_template("episode.html")
    by_num = sorted(episodes, key=lambda e: e.get("episode", 0))
    for i, ep in enumerate(by_num):
        prev_ep = by_num[i - 1] if i > 0 else None
        next_ep = by_num[i + 1] if i < len(by_num) - 1 else None
        html_out = ep_tmpl.render(
            **base_context,
            episode=ep, prev_ep=prev_ep, next_ep=next_ep,
            nav_active=None,
        )
        write_page(DIST_DIR / "episodes" / f"{ep['slug']}.html", html_out)

    # ── about ──
    if "about" in lore:
        about_tmpl = env.get_template("lore.html")
        write_page(DIST_DIR / "about.html", about_tmpl.render(
            **base_context, page=lore["about"], nav_active="about",
            page_title="About the Series",
        ))

    # ── jedi index ──
    jedi_tmpl = env.get_template("jedi-index.html")
    write_page(DIST_DIR / "jedi-index.html", jedi_tmpl.render(
        **base_context, jedi=jedi, nav_active="jedi",
        page_title="Jedi Index",
    ))

    # ── glossary ──
    gloss_tmpl = env.get_template("glossary.html")
    write_page(DIST_DIR / "glossary.html", gloss_tmpl.render(
        **base_context, entries=glossary, nav_active="glossary",
        page_title="Glossary",
    ))

    # ── feed.xml ──
    feed_tmpl = env.get_template("feed.xml")
    write_page(DIST_DIR / "feed.xml", feed_tmpl.render(
        **base_context, episodes=published,
        build_date=dt.datetime.now(dt.timezone.utc),
    ))

    # ── sitemap.xml ──
    sitemap_tmpl = env.get_template("sitemap.xml")
    urls = ["/"]
    for ep in published:
        urls.append(f"/episodes/{ep['slug']}.html")
    for page in ["about.html", "jedi-index.html", "glossary.html"]:
        urls.append(f"/{page}")
    write_page(DIST_DIR / "sitemap.xml", sitemap_tmpl.render(
        **base_context, urls=urls, episodes=published,
        build_date=dt.datetime.now(dt.timezone.utc),
    ))

    # ── robots.txt ──
    robots = (
        f"User-agent: *\nAllow: /\n\n"
        f"Sitemap: {config['base_url']}/sitemap.xml\n"
    )
    write_page(DIST_DIR / "robots.txt", robots)

    # Summary
    print(f"✓ Built {len(episodes)} episodes ({len(published)} published, "
          f"{len(coming_soon)} coming soon)")
    print(f"  Jedi index: {len(jedi)} entries")
    print(f"  Glossary: {len(glossary)} terms")
    print(f"  Output: {DIST_DIR}")


def serve_site(port: int = 8000):
    os.chdir(DIST_DIR)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"▶ Serving at http://localhost:{port}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n■ Stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the Gravedancer to General site.")
    parser.add_argument("--serve", action="store_true",
                        help="Build then serve dist/ on localhost:8000")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    build_site()
    if args.serve:
        serve_site(args.port)
