# Australian NFP AI Tracker

Self-updating tracker. A nightly GitHub Action reads RSS feeds, asks Claude to extract Australian NFP AI initiatives, and commits `data/*.json`. GitHub Pages serves `index.html`.

## Setup (about 15 minutes)
1. Create a GitHub repo and upload all these files (keep the folder structure, including `.github`).
2. Settings > Pages > Deploy from branch > `main` / root.
3. Settings > Secrets and variables > Actions > New secret: `ANTHROPIC_API_KEY`.
4. Create Google Alerts (google.com/alerts), set "Deliver to" = RSS feed, and paste each feed URL into `feeds.txt`.
5. Actions tab > nightly-update > Run workflow (to test). After that it runs nightly.

## Sectors and on-demand crawling
- `sectors.txt` lists sectors that are searched nightly via Google News RSS (Australia). Add lines to widen coverage.
- Visitors type a sector on the site and see everything already collected instantly. If nothing matches, a link opens a "Sector request" issue.
- To crawl a new sector immediately: Actions > nightly-update > Run workflow > enter the sector.
- LinkedIn is not crawled (see notes in chat): scraping it breaches its terms. Use the submission issue form instead.

## How it works
- Confidence >= 0.85 -> `data/initiatives.json` (shown on site as "auto-added").
- Lower confidence -> `data/review.json`. Move good ones into `initiatives.json` and set `"verified": true`.
- Change the thresholds and caps at the top of `scripts/update.py`.
