# Job scraper dashboard

A local web app with two "Scrape now" buttons that run your actual scraper
scripts (`scrape_all_posts.py` and `scrape_telegram_jobs.py`), then let you
browse the results and click straight through to each job's apply link.

## Setup

```bash
cd job_dashboard_app
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## How it works

- Clicking **Scrape now** on either card calls your real scraper's `main()`
  function in a background thread (so the page doesn't freeze) and writes
  the CSV/XLSX into the app folder, exactly like running the script directly.
- The page polls scrape status every 2 seconds and shows a spinner while
  running. The website scraper visits every individual post, so it can take
  a few minutes; the Telegram scraper is much faster since it only reads one
  page.
- When done, click **View results** to load the fresh CSV straight into the
  job list — no manual upload needed.
- If `job4freshers_scraped_data.csv` or `telegram_jobs_data.csv` already
  exist in the folder from a previous run, they load automatically when you
  open the page.
- The dropdown filters by source; the search box filters by any text in any
  column (title, company, salary, location, etc).

## Files

- `app.py` — Flask backend: triggers scrapers, tracks status, serves CSV data as JSON
- `scrapers/scrape_all_posts.py` — your website scraper (unchanged)
- `scrapers/scrape_telegram_jobs.py` — your Telegram scraper (unchanged)
- `templates/index.html` — the dashboard UI

## Notes

- Both scraper scripts are used exactly as you wrote them — nothing was
  changed inside them. The app just imports and calls their `main()`.
- Re-running a scrape overwrites the previous CSV for that source.
- If a scrape errors out (e.g. the site structure changed or a network
  request times out), the card will show the error message instead of
  hanging silently.
