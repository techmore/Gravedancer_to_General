# Gravedancer to General — Anatomy of a Catastrophe

A static website for a Star Wars fan fiction series following **Qymaen jai
Sheelal** (the Gravedancer) on his pre-Clone Wars path toward becoming
General Grievous. Weekly episodes, day-by-day chapters, privacy-first.

Built as a Python-generated static site deployed to GitHub Pages via
GitHub Actions. No Jekyll, no frameworks, no tracking.

---

## Quick start (local)

```bash
# 1. Install build dependencies (one time)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Build the site into dist/
python build.py

# 3. Preview at http://localhost:8000
python build.py --serve
```

## How episodes work

Each episode is a single Markdown file in `episodes/`:

```
episodes/01-the-silencing-of-kaelen-voss.md
```

```markdown
---
title: "The Silencing of Kaelen Voss"
episode: 1
tagline: "A whisper in the rain becomes a death sentence."
target_jedi: "Kaelen Voss"
jedi_species: "Mirialan"
jedi_philosophy: "The Living Force hears all things, eventually."
jedi_fate: "Unresolved"
setting: "Kalee — The Jiwari lowlands"
status: published            # published | coming_soon | draft
published_at: 2026-06-20
---

## DAY 1: The First Rain

Your prose here...

## DAY 2: The Counting of Steps

More prose...
```

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| `title` | yes | Episode title |
| `episode` | yes | Sequential number |
| `tagline` | yes | One-line hook |
| `target_jedi` | yes | Jedi hunted this episode |
| `jedi_species` | recommended | Feeds the Jedi Index |
| `jedi_philosophy` | recommended | Feeds the Jedi Index |
| `jedi_fate` | recommended | Feeds the Jedi Index |
| `setting` | yes | Planet/location |
| `status` | yes | `published`, `coming_soon`, or `draft` (drafts are excluded) |
| `published_at` | yes if published | `YYYY-MM-DD` |

**Word count and reading time are computed automatically** from the body —
never hand-enter them.

### Day headers

Each daily chapter starts with a `## DAY N: Title` header. The build
splits on these and generates per-day navigation in the reader. The first
line after the frontmatter (`---`) should be `## DAY 1:`.

### Adding a new episode

1. Create `episodes/NN-slug.md` (filename order doesn't matter; `episode:`
   frontmatter controls ordering).
2. Fill in frontmatter + body.
3. Set `status: published` (or `coming_soon` to tease it).
4. Commit and push to `main`. GitHub Actions rebuilds and deploys
   automatically. (Or run `python build.py` locally to preview.)

## Lore pages

- `lore/about.md` → `/about.html`
- `lore/glossary.md` → `/glossary.html` (entries are `### Term — definition`)
- Jedi Index is auto-generated from episode frontmatter — no manual file.

## Site configuration

Edit `site.yml` for the title, author, description, base URL, and social
links. The `base_url` must match your deployed URL (e.g.
`https://techmore.github.io/Gravedancer_to_General`).

## Deployment (GitHub Pages)

Deployment is automatic via `.github/workflows/deploy.yml`. On every push
to `main` it builds and publishes `dist/` to Pages.

**One-time setup** (in the GitHub repo settings):

1. **Settings → Pages → Build and deployment → Source:** set to
   **GitHub Actions** (not "Deploy from a branch").
2. Push to `main`. The workflow runs; Pages goes live at your Pages URL.

If you rename the repo or use a custom domain, update `base_url` in
`site.yml` to match.

## Architecture

```
episodes/*.md          ← source: episode content (Markdown + YAML frontmatter)
lore/*.md              ← source: about + glossary (Markdown)
site.yml               ← source: site config (title, author, base_url, social)
src/
  templates/*.html     ← Jinja2 templates
  static/styles.css    ← stylesheet
  static/app.js        ← client-side JS (theme, day nav, filters, read-tracking)
  assets/              ← favicon + OG image
build.py               ← the generator: reads sources, writes dist/
dist/                  ← generated output (gitignored, never hand-edited)
.github/workflows/
  deploy.yml           ← CI: build on push → publish dist/ to Pages
```

### What the build produces

- `index.html` — episode archive with filters + read-tracking + latest banner
- `episodes/<slug>.html` — one reader page per episode (day-by-day nav)
- `about.html`, `jedi-index.html`, `glossary.html` — lore pages
- `feed.xml` — RSS 2.0 feed of published episodes
- `sitemap.xml`, `robots.txt` — SEO
- Open Graph + Twitter Card meta on every episode page

### Design

- **Dark mode default**, light mode toggle (persisted in `localStorage`,
  honors `prefers-color-scheme` on first visit, no flash on load).
- Palette: deep navy `#1a1a2e`, gold `#d4a373`, muted olive `#a8b088`.
- Fonts: Lora (serif prose) + Inter (UI), via Google Fonts.
- Mobile-first; breakpoints at 768px and 1024px.
- 700px prose measure, 1.8 line height in the reader.

## Privacy

No analytics. No cookies. No third-party trackers. Read-tracking is local
to your browser (`localStorage`) and never transmitted anywhere. The only
external requests are to Google Fonts (CSS) and GitHub Pages hosting.

## Disclaimer

Star Wars and all associated names are property of their respective owners
(Lucasfilm / Disney). This is a non-commercial fan work.
