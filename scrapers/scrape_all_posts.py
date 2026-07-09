import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import sys
from urllib.parse import urljoin

# Reconfigure stdout to print UTF-8 characters to the terminal safely
sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_url_with_retry(url, max_retries=5, delay=2):
    for i in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                return r
            print(f"  [Warning] status code {r.status_code} for {url}, retrying...")
        except Exception as e:
            print(f"  [Attempt {i+1}/{max_retries} failed] {url}: {e}")
            time.sleep(delay)
    return None

def resolve_redirect(url, max_retries=3, delay=1):
    if not url or not url.startswith("http"):
        return url
    
    # Do not follow redirects for social links
    if any(s in url.lower() for s in ["whatsapp.com", "t.me", "telegram.dog", "twitter.com", "instagram.com", "facebook.com"]):
        return url
        
    for i in range(max_retries):
        try:
            # Follow redirects using stream=True to avoid downloading large binary files
            r = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=10)
            return r.url
        except Exception as e:
            # NameResolutionErrors or similar DNS errors are caught here
            print(f"  [Redirect Attempt {i+1} failed] {url} -> {e}")
            time.sleep(delay)
            
    return url  # Return original if redirect resolution fails

def extract_posts_from_page(page_url):
    print(f"Fetching posts list from: {page_url}")
    r = get_url_with_retry(page_url)
    if not r:
        print(f"Error: Failed to fetch page {page_url}")
        return []
        
    soup = BeautifulSoup(r.text, 'html.parser')
    post_links = []
    
    # In Divi/Extra, the main content contains articles
    main_content = soup.find(id="main-content") or soup
    articles = main_content.find_all("article")
    
    for art in articles:
        header = art.find(["h2", "h1", "h3"])
        a = header.find("a") if header else art.find("a")
        if a and a.get("href"):
            href = a.get("href")
            # Filter internal category or listing urls
            if href.startswith("https://job4freshers.co.in/") and not any(k in href for k in ["/category/", "/page/", "/policy/", "/about-us/", "/post-a-job/", "?", "#"]):
                if href not in post_links:
                    post_links.append(href)
                    
    return post_links

def parse_post(url, index, total):
    print(f"\n[{index}/{total}] Scraping Post: {url}")
    r = get_url_with_retry(url)
    if not r:
        print(f"  [Error] Failed to fetch post: {url}")
        return None
        
    soup = BeautifulSoup(r.text, 'html.parser')
    
    title_el = soup.find("h1")
    title = title_el.text.strip() if title_el else "Unknown Title"
    print(f"  Title: {title}")
    
    # 1. TOC items (1-11)
    toc_items = []
    toc_container = soup.find(id="ez-toc-container")
    if toc_container:
        lis = toc_container.find_all("li")
        for li in lis[:11]:
            # Clean up text
            toc_items.append(li.text.strip())
            
    # Pad with empty strings if fewer than 11 items
    while len(toc_items) < 11:
        toc_items.append("")
        
    # 2. Find Apply Link
    apply_url = ""
    apply_text = ""
    content = soup.find("div", class_="post-content") or soup.find("div", class_="entry-content")
    if content:
        candidates = []
        for a in content.find_all("a"):
            text = a.text.strip()
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue
                
            href_lower = href.lower()
            text_lower = text.lower()
            
            # Filters
            is_social = any(s in href_lower for s in ["youtube.com", "t.me", "telegram.dog", "whatsapp.com", "twitter.com", "instagram.com", "facebook.com", "linkedin.com", "pinterest.com"])
            is_internal = "job4freshers.co.in" in href_lower
            is_openinapp = "openinapp.co" in href_lower
            
            # Skip internal and social links
            if is_internal or is_social or is_openinapp:
                continue
                
            # Score logic
            score = 0
            if "click here to apply" in text_lower or "click here to register" in text_lower:
                score = 100
            elif "apply" in text_lower and "click" in text_lower:
                score = 90
            elif "click here" in text_lower:
                score = 80
            elif "apply" in text_lower:
                score = 70
            elif "register" in text_lower:
                score = 60
            else:
                score = 10 # any external link
                
            candidates.append((score, text, href))
            
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates:
            apply_text = candidates[0][1]
            apply_url = candidates[0][2]
            print(f"  Best apply link candidate: '{apply_text}' -> '{apply_url}' (Score: {candidates[0][0]})")
        else:
            print("  No obvious apply link candidate found.")
            
    # Resolve redirect URL
    redirected_url = apply_url
    if apply_url:
        print(f"  Resolving redirect for: {apply_url}...")
        redirected_url = resolve_redirect(apply_url)
        print(f"  --> Final redirected URL: {redirected_url}")
    else:
        redirected_url = "Direct Walk-in (No Link)"
        apply_url = "Direct Walk-in (No Link)"
        apply_text = "N/A"
        
    data = {
        "Job Post Title": title,
        "Job Post URL": url,
        "Apply Link Text": apply_text,
        "Apply Link (Original)": apply_url,
        "Apply Link (Redirected/Company Site)": redirected_url
    }
    
    # Add TOC columns
    for idx in range(11):
        data[f"TOC Item {idx+1}"] = toc_items[idx]
        
    non_empty_toc = [t for t in toc_items if t]
    data["Combined TOC (1-11)"] = "\n".join(non_empty_toc)
    
    return data

def main():
    print("Starting Scraper for job4freshers.co.in")
    
    # 1. Get all post URLs from Page 1 and Page 2
    page1_url = "https://job4freshers.co.in/freshers-jobs/"
    page2_url = "https://job4freshers.co.in/freshers-jobs/page/2/"
    
    links = []
    links.extend(extract_posts_from_page(page1_url))
    links.extend(extract_posts_from_page(page2_url))
    
    # Deduplicate while preserving order
    unique_links = []
    for l in links:
        if l not in unique_links:
            unique_links.append(l)
            
    total_posts = len(unique_links)
    print(f"\nFound total {total_posts} unique posts to scrape.")
    
    # 2. Scrape each post
    results = []
    for idx, url in enumerate(unique_links):
        # Scrape and catch any errors to ensure the script doesn't crash halfway
        try:
            post_data = parse_post(url, idx + 1, total_posts)
            if post_data:
                results.append(post_data)
        except Exception as e:
            print(f"  [ERROR] Failed processing post {url}: {e}")
            
        # Polite delay to prevent rate limits
        time.sleep(1.0)
        
    if not results:
        print("Error: No data was scraped.")
        return
        
    # 3. Write data to Excel and CSV
    df = pd.DataFrame(results)
    
    excel_path = "job4freshers_scraped_data.xlsx"
    csv_path = "job4freshers_scraped_data.csv"
    
    # Reorder columns to place key info first, then TOC items, then combined TOC
    cols = [
        "Job Post Title",
        "Job Post URL",
        "Apply Link Text",
        "Apply Link (Original)",
        "Apply Link (Redirected/Company Site)"
    ] + [f"TOC Item {i+1}" for i in range(11)] + ["Combined TOC (1-11)"]
    
    # Filter columns to only include existing ones, just in case
    cols = [c for c in cols if c in df.columns]
    df = df[cols]
    
    try:
        df.to_excel(excel_path, index=False)
    except PermissionError:
        raise PermissionError(f"Permission denied: Please close '{excel_path}' if it is open in another program (like Excel) and try again.")
        
    try:
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    except PermissionError:
        raise PermissionError(f"Permission denied: Please close '{csv_path}' if it is open in another program (like Excel) and try again.")
    
    print(f"\nSuccessfully scraped {len(results)} posts!")
    print(f"Saved to Excel: {excel_path}")
    print(f"Saved to CSV: {csv_path}")

if __name__ == "__main__":
    main()
