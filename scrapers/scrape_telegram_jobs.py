import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import time
import sys
from urllib.parse import urljoin

sys.stdout.reconfigure(encoding='utf-8')

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_url_with_retry(url, max_retries=3, delay=1):
    for i in range(max_retries):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                return r
        except Exception as e:
            time.sleep(delay)
    return None

def resolve_redirect(url, max_retries=3, delay=1):
    if not url or not url.startswith("http"):
        return url
    if any(s in url.lower() for s in ["whatsapp.com", "t.me", "telegram.dog", "twitter.com", "instagram.com", "facebook.com"]):
        return url
    for i in range(max_retries):
        try:
            r = requests.get(url, headers=headers, allow_redirects=True, stream=True, timeout=8)
            return r.url
        except Exception:
            time.sleep(delay)
    return url

def extract_actual_apply_link_from_blog(blog_url):
    """
    If the telegram apply link points to job4freshers.co.in,
    visit that blog post and extract the actual company application URL.
    """
    if "job4freshers.co.in" not in blog_url.lower():
        return blog_url, "Direct Link"
        
    print(f"    -> Fetching blog post details from: {blog_url}")
    r = get_url_with_retry(blog_url)
    if not r:
        return blog_url, "Failed to load blog post"
        
    soup = BeautifulSoup(r.text, 'html.parser')
    content = soup.find("div", class_="post-content") or soup.find("div", class_="entry-content")
    if not content:
        return blog_url, "No content div found in blog"
        
    candidates = []
    for a in content.find_all("a"):
        text = a.text.strip()
        href = a.get("href", "")
        if not href or href.startswith("#"):
            continue
            
        href_lower = href.lower()
        text_lower = text.lower()
        
        is_social = any(s in href_lower for s in ["youtube.com", "t.me", "telegram.dog", "whatsapp.com", "twitter.com", "instagram.com", "facebook.com", "linkedin.com"])
        is_internal = "job4freshers.co.in" in href_lower
        is_openinapp = "openinapp.co" in href_lower
        
        if is_internal or is_social or is_openinapp:
            continue
            
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
            score = 10
            
        candidates.append((score, text, href))
        
    candidates.sort(key=lambda x: x[0], reverse=True)
    if candidates:
        best_href = candidates[0][2]
        best_text = candidates[0][1]
        print(f"       Found actual apply link candidate: '{best_text}' -> '{best_href}'")
        return best_href, best_text
        
    return "Direct Walk-in (No Link)", "Walk-in"

def parse_message_text(text):
    # Regex parsing for structured telegram job posts
    company = re.search(r"(?:Company\s+Name|Company|Employer)\s*:\s*(.*)", text, re.IGNORECASE)
    role = re.search(r"(?:Post\s+Name|Role|Position|Job\s+Role)\s*:\s*(.*)", text, re.IGNORECASE)
    salary = re.search(r"(?:Expected\s+)?Salary\s*:\s*(.*)", text, re.IGNORECASE)
    location = re.search(r"(?:Job\s+)?Location\s*:\s*(.*)", text, re.IGNORECASE)
    experience = re.search(r"(?:Experience|JobType|Eligibility)\s*:\s*(.*)", text, re.IGNORECASE)
    
    comp_val = company.group(1).strip() if company else ""
    role_val = role.group(1).strip() if role else ""
    sal_val = salary.group(1).strip() if salary else ""
    loc_val = location.group(1).strip() if location else ""
    exp_val = experience.group(1).strip() if experience else ""
    
    return comp_val, role_val, sal_val, loc_val, exp_val

def main(channel_name=None):
    if not channel_name:
        channel_name = "work4freshers"
    url = f"https://t.me/s/{channel_name}"
    print(f"Fetching posts from Telegram public web preview: {url}")
    
    r = get_url_with_retry(url)
    if not r:
        print(f"Error: Failed to fetch Telegram channel: {url}")
        return
        
    soup = BeautifulSoup(r.text, 'html.parser')
    messages = soup.find_all(class_="tgme_widget_message")
    print(f"Found {len(messages)} messages on the public preview page.")
    
    results = []
    job_count = 0
    
    for idx, msg in enumerate(messages):
        text_div = msg.find(class_="tgme_widget_message_text")
        if not text_div:
            continue
            
        text = text_div.get_text(separator="\n").strip()
        comp, role, sal, loc, exp = parse_message_text(text)
        
        # Check if this represents a job post
        is_job = False
        if comp or role:
            is_job = True
        else:
            # Fallback parsing for non-structured channels/messages
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                comp = f"@{channel_name}"
                first_line = lines[0]
                # Truncate first line for role/title if it's too long
                if len(first_line) > 80:
                    role = first_line[:77] + "..."
                else:
                    role = first_line
                is_job = True

        if is_job:
            job_count += 1
            print(f"\n[{job_count}] Processing job message index {idx+1}:")
            print(f"    Company: {comp} | Role: {role}")
            
            # Find the Telegram post link
            info_div = msg.find(class_="tgme_widget_message_info")
            tg_post_url = ""
            if info_div:
                a_link = info_div.find(class_="tgme_widget_message_date")
                if a_link:
                    tg_post_url = a_link.get("href")
            
            # Find primary apply link inside the message
            tg_apply_link = ""
            for a in text_div.find_all("a"):
                href = a.get("href", "")
                if href and not any(s in href.lower() for s in ["youtube.com", "t.me", "telegram.me", "telegram.dog", "whatsapp.com", "facebook.com", "instagram.com", "twitter.com"]):
                    tg_apply_link = href
                    break
            
            # If the apply link points to their blog, extract the real apply link
            actual_apply_link = tg_apply_link
            link_source = "Direct Link in Telegram"
            if tg_apply_link:
                actual_apply_link, link_source = extract_actual_apply_link_from_blog(tg_apply_link)
                
            # Follow redirects to get the company page
            final_company_url = actual_apply_link
            if actual_apply_link and actual_apply_link.startswith("http") and "job4freshers.co.in" not in actual_apply_link:
                print(f"    Resolving redirect for actual link: {actual_apply_link}...")
                final_company_url = resolve_redirect(actual_apply_link)
                print(f"    --> Final company URL: {final_company_url}")
                
            results.append({
                "Channel": f"@{channel_name}",
                "Company Name": comp if comp else "Unknown",
                "Role/Post Name": role if role else "Unknown",
                "Salary": sal if sal else "Not Mentioned",
                "Location": loc if loc else "Not Mentioned",
                "Experience": exp if exp else "Not Mentioned",
                "Telegram Post URL": tg_post_url,
                "Telegram Apply Link (Original)": tg_apply_link,
                "Actual Apply Link": actual_apply_link,
                "Link Source/Text": link_source,
                "Final Company Application URL": final_company_url
            })
            
            # Small sleep to be polite
            time.sleep(1.0)
            
    if not results:
        print("No job posts matched our parser on this page.")
        return
        
    df = pd.DataFrame(results)
    excel_file = "telegram_jobs_data.xlsx"
    csv_file = "telegram_jobs_data.csv"
    
    try:
        df.to_excel(excel_file, index=False)
    except PermissionError:
        raise PermissionError(f"Permission denied: Please close '{excel_file}' if it is open in another program (like Excel) and try again.")
        
    try:
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    except PermissionError:
        raise PermissionError(f"Permission denied: Please close '{csv_file}' if it is open in another program (like Excel) and try again.")
    
    print(f"\nSuccessfully scraped and parsed {len(results)} jobs from @{channel_name}!")
    print(f"Excel file created: {excel_file}")
    print(f"CSV file created: {csv_file}")

if __name__ == "__main__":
    main()
