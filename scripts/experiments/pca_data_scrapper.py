#!/usr/bin/env python3
"""
BAILII Case Law Summary Scraper & Exporter

This script:
  - Crawls a specified BAILII jurisdiction URL,
    recursively (up to 2 levels) for .html files under '/cases/'.
  - Extracts each case's title, date, and headnote summary.
  - Excludes non-case pages (e.g., databases, help, feedback).
  - Saves results to JSON or CSV for training your legal AI chatbot.

Usage:
    python pca_data_scrapper.py [jurisdiction_url] [limit] [output_file]

Example:
    python pca_data_scrapper.py https://www.bailii.org/ew/cases/EWCA/ 100 export.json
"""
import sys, os, json, csv
import requests
from bs4 import BeautifulSoup
import re
import time
import logging

# Setup logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# HTTP session with headers
def make_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/115.0.0.0 Safari/537.36'
    })
    return s

# Fetch .html links under '/cases/'
def fetch_case_list(base_url, limit=None, retries=3, backoff=2):
    session = make_session()
    collected = []

    def recurse(url, depth):
        if limit and len(collected) >= limit:
            return
        for attempt in range(1, retries+1):
            try:
                resp = session.get(url, timeout=10)
                status = resp.status_code
            except Exception as e:
                logging.warning(f"[{url}] Attempt {attempt} failed: {e}")
                time.sleep(backoff*attempt)
                continue
            if status == 200:
                break
            if status in (403,429,500,502,503,504):
                logging.warning(f"[{url}] HTTP {status}, retrying...")
                time.sleep(backoff*attempt)
            else:
                resp.raise_for_status()
        else:
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href in ('../','./'): continue
            full = requests.compat.urljoin(url, href)
            # Only case pages under '/cases/'
            if '/cases/' in full and href.lower().endswith('.html'):
                if full not in collected:
                    collected.append(full)
                    logging.debug(f"Added case: {full}")
                    if limit and len(collected)>=limit: return
            # Recurse into subfolders
            elif href.endswith('/') and depth<2:
                recurse(full, depth+1)
                if limit and len(collected)>=limit: return

    recurse(base_url, depth=0)
    logging.info(f"Collected {len(collected)} case links from {base_url}")
    return collected

# Extract summary
def extract_summary(session, case_url, retries=3, backoff=2):
    for attempt in range(1, retries+1):
        try:
            resp = session.get(case_url, timeout=10)
            code = resp.status_code
        except Exception as e:
            logging.warning(f"[{case_url}] Attempt {attempt} failed: {e}")
            time.sleep(backoff*attempt)
            continue
        if code==200: break
        if code in (403,429,500,502,503,504):
            logging.warning(f"[{case_url}] HTTP {code}, retrying...")
            time.sleep(backoff*attempt)
        else:
            resp.raise_for_status()
    else:
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, 'html.parser')
    title_tag = soup.find('h1')
    title = title_tag.get_text(strip=True) if title_tag else ''
    date = None
    date_div = soup.find('div', class_='date')
    if date_div:
        date = date_div.get_text(strip=True)
    else:
        p = soup.find('p')
        if p and re.search(r"\d{1,2}\s+\w+\s+\d{4}", p.get_text()):
            date = p.get_text(strip=True)
    headnote = soup.find('div', class_='headnote')
    if headnote:
        summary = headnote.get_text(' ', strip=True)
    else:
        paras = soup.find_all('p', limit=2)
        summary = ' '.join(p.get_text(strip=True) for p in paras)
    return {'url': case_url, 'title': title, 'date': date, 'summary': summary}

# Save to file
def save_results(results, output_file):
    ext = os.path.splitext(output_file)[1].lower()
    if ext == '.json':
        with open(output_file,'w',encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved JSON to {output_file}")
    elif ext in ('.csv','.tsv'):
        sep = ',' if ext=='.csv' else '\t'
        keys = ['url','title','date','summary']
        with open(output_file,'w',encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys, delimiter=sep)
            writer.writeheader()
            for row in results:
                writer.writerow(row)
        logging.info(f"Saved CSV/TSV to {output_file}")
    else:
        logging.error(f"Unsupported format: {ext}")

# Main execution
if __name__=='__main__':
    setup_logging()
    if len(sys.argv)<4:
        print(__doc__)
        sys.exit(1)
    base = sys.argv[1]
    lim = int(sys.argv[2])
    out = sys.argv[3]

    session = make_session()
    urls = fetch_case_list(base, limit=lim)
    results = []
    for u in urls:
        try:
            data = extract_summary(session, u)
            results.append(data)
        except Exception as e:
            logging.error(f"Error scraping {u}: {e}")
    save_results(results, out)
    print(f"Done: {len(results)} cases saved to {out}")
