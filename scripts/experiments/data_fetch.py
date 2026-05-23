import requests
import feedparser
import os
from time import sleep

# Configuration
OUTPUT_DIR = '/mnt/data/uk_finance_law_corpus'
LEGIS_FEED_URL = 'https://www.legislation.gov.uk/data/feed/publicationLog/data.feed'
CASELAW_API_BASE = 'https://www.legislation.gov.uk'
CASELAW_API_ENDPOINT = 'https://caselaw.nationalarchives.gov.uk/judgments'

# Ensure directories exist
os.makedirs(OUTPUT_DIR + '/legislation', exist_ok=True)
os.makedirs(OUTPUT_DIR + '/case_law', exist_ok=True)

def download_legislation(max_entries=100):
    """
    Download recent legislation XML entries from the publication feed.
    """
    feed = feedparser.parse(LEGIS_FEED_URL)
    count = 0
    for entry in feed.entries:
        if count >= max_entries:
            break
        # Each entry ID holds the URL to the legislation page
        leg_url = entry.id
        xml_url = leg_url + '/data.xml'
        filename = xml_url.split('/')[-3] + '_' + xml_url.split('/')[-2] + '.xml'
        filepath = os.path.join(OUTPUT_DIR, 'legislation', filename)
        if not os.path.exists(filepath):
            resp = requests.get(xml_url)
            if resp.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                print(f"Saved: {filename}")
            else:
                print(f"Failed to fetch: {xml_url} (Status {resp.status_code})")
            sleep(0.5)  # respectful rate limiting
        count += 1

def download_case_law(max_pages=2, page_size=50):
    """
    Download judgments from the National Archives Find Case Law API.
    """
    for page in range(1, max_pages + 1):
        params = {'page': page, 'size': page_size}
        resp = requests.get(CASELAW_API_ENDPOINT, params=params)
        if resp.status_code != 200:
            print(f"Failed API page {page}: Status {resp.status_code}")
            break
        data = resp.json()
        for j in data.get('results', []):
            jid = j.get('judgmentUri')
            xml_url = CASELAW_API_ENDPOINT + f"/{jid}.xml"
            filename = jid.replace('/', '_') + '.xml'
            filepath = os.path.join(OUTPUT_DIR, 'case_law', filename)
            if not os.path.exists(filepath):
                r2 = requests.get(xml_url)
                if r2.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(r2.content)
                    print(f"Saved judgment: {filename}")
                else:
                    print(f"Failed to fetch judgment XML: {xml_url}")
                sleep(0.5)
        # stop if fewer results than page_size
        if len(data.get('results', [])) < page_size:
            break

# Run downloads
download_legislation(max_entries=50)
download_case_law(max_pages=3, page_size=100)


