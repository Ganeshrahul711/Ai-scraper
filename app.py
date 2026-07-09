import os
import sys
import threading
import traceback

import pandas as pd
from flask import Flask, jsonify, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPERS_DIR = os.path.join(BASE_DIR, "scrapers")
sys.path.insert(0, SCRAPERS_DIR)

# Your actual scraper modules
import scrape_all_posts       # website scraper (job4freshers.co.in)
import scrape_telegram_jobs   # telegram scraper (@work4freshers)

app = Flask(__name__)

# The scrapers write their CSV/XLSX into the current working directory,
# so we run them with BASE_DIR as the working directory and read from there.
CSV_PATHS = {
    "website": os.path.join(BASE_DIR, "job4freshers_scraped_data.csv"),
    "telegram": os.path.join(BASE_DIR, "telegram_jobs_data.csv"),
}

# In-memory status tracker, shared across requests
status = {
    "website": {"state": "idle", "message": "", "count": 0},
    "telegram": {"state": "idle", "message": "", "count": 0},
}
status_lock = threading.Lock()


def run_scraper(source, channel_name=None):
    msg = "Scraping in progress... this can take a few minutes."
    if source == "telegram" and channel_name:
        msg = f"Scraping @{channel_name} in progress... this can take a few minutes."
        
    with status_lock:
        status[source] = {"state": "running", "message": msg, "count": 0}

    prev_cwd = os.getcwd()
    try:
        os.chdir(BASE_DIR)
        if source == "website":
            scrape_all_posts.main()
        else:
            scrape_telegram_jobs.main(channel_name=channel_name)

        path = CSV_PATHS[source]
        if os.path.exists(path):
            df = pd.read_csv(path)
            with status_lock:
                status[source] = {"state": "done", "message": f"Scraped {len(df)} jobs", "count": len(df)}
        else:
            with status_lock:
                status[source] = {"state": "error", "message": "Scraper finished but no CSV file was produced.", "count": 0}
    except Exception as e:
        traceback.print_exc()
        with status_lock:
            status[source] = {"state": "error", "message": f"Scraper failed: {e}", "count": 0}
    finally:
        os.chdir(prev_cwd)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/scrape/<source>", methods=["POST"])
def start_scrape(source):
    if source not in CSV_PATHS:
        return jsonify({"error": "unknown source"}), 400
    with status_lock:
        if status[source]["state"] == "running":
            return jsonify({"error": "already running"}), 409
            
    channel_name = None
    if source == "telegram":
        from flask import request
        data = request.get_json(silent=True) or {}
        channel_name = data.get("channel") or "work4freshers"
        # Clean channel name
        if channel_name.startswith("@"):
            channel_name = channel_name[1:]
        channel_name = channel_name.strip()
        if not channel_name:
            return jsonify({"error": "Channel name is required"}), 400

    thread = threading.Thread(target=run_scraper, args=(source, channel_name), daemon=True)
    thread.start()
    return jsonify({"started": True})


@app.route("/api/status/<source>")
def get_status(source):
    if source not in CSV_PATHS:
        return jsonify({"error": "unknown source"}), 400
    with status_lock:
        return jsonify(status[source])


@app.route("/api/data/<source>")
def get_data(source):
    if source not in CSV_PATHS:
        return jsonify({"error": "unknown source"}), 400
    path = CSV_PATHS[source]
    if not os.path.exists(path):
        return jsonify({"rows": [], "columns": []})
    df = pd.read_csv(path).fillna("")
    return jsonify({"rows": df.to_dict(orient="records"), "columns": list(df.columns)})


if __name__ == "__main__":
    print("Starting job dashboard at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)