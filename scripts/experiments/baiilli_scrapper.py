#!/usr/bin/env python3
"""
PRA Rulebook bulk PDF exporter – v5.0  (2025-06)

• Resilient HTTP session (10 s connect, 60 s read, 7 retries, back-off)
• Partial-file resume with *.part
• Direct PDF download when available, otherwise print-view → PDF (pdfkit)
• Skips historical “YYYY-MM-DD” versions so the crawl finishes quickly
• Progress lines BEFORE each network request + tqdm byte bar
"""

from __future__ import annotations
import os, re, time, random, unicodedata, tempfile
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import pdfkit               # ── fallback: HTML → PDF

# ────────── configuration ──────────────────────────────────────────────
BASE        = "https://www.prarulebook.co.uk"
START_URL   = f"{BASE}/pra-rules"
OUT_DIR     = "pra_rulebook_pdfs"
FAILED_LOG  = "failed_urls.txt"
os.makedirs(OUT_DIR, exist_ok=True)

# ────────── resilient session ──────────────────────────────────────────
def make_session() -> requests.Session:
    retry = Retry(
        total=8, backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        raise_on_status=False,
    )
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (RulebookCrawler/5.0)"})
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    return s

S = make_session()

# ────────── helpers ────────────────────────────────────────────────────
_slug_rx = re.compile(r"[^0-9A-Za-z\-]+")
_date_tail_rx = re.compile(r"/\d{4}-\d{2}-\d{2}$")  # e.g. /capital-buffers/2025-05-31

def slugify(text: str) -> str:
    return _slug_rx.sub("_", unicodedata.normalize("NFKD", text)).strip("_").lower()

def get_soup(url: str, read_timeout: int = 60) -> BeautifulSoup:
    print("↷ GET", url)           # always show activity
    r = S.get(url, timeout=(10, read_timeout))
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def discover_parts() -> list[str]:
    """
    Breadth-first crawl starting at /pra-rules.
    Only collects canonical pages:
        /pra-rules/<slug>
    Ignores dated versions like /pra-rules/<slug>/YYYY-MM-DD
    """
    todo   : list[str] = [START_URL]
    seen   : set[str]  = set()
    parts  : set[str]  = set()

    part_rx = re.compile(r"^/pra-rules/[^/?#]+/?$")   # canonical only

    while todo:
        url = todo.pop()
        if url in seen:
            continue
        seen.add(url)

        try:
            soup = get_soup(url)
        except Exception as e:
            print("✗ idx", url, "→", e)
            continue

        for a in soup.select("a[href]"):
            href_raw = a["href"]
            href = urljoin(BASE, href_raw) if href_raw.startswith("/") else href_raw

            # enqueue sub-pages to crawl
            if href.startswith(BASE + "/pra-rules/") and href not in seen:
                if part_rx.match(urlparse(href).path):           # canonical page
                    todo.append(href)

            # collect canonical parts
            if part_rx.match(urlparse(href).path):
                parts.add(href)

        time.sleep(0.5 + random.random())

    return sorted(parts)

def find_pdf_anchor(soup: BeautifulSoup):
    """
    Look for an <a> that definitely links to a *.pdf .
    1) The site sometimes wraps the red button as
       <a class="icon-pdf"...>
    2) Otherwise, use any anchor whose href ends with .pdf (case-insensitive)
    """
    a = soup.select_one('a.icon-pdf[href$=".pdf" i]')
    if a:
        return a
    for a in soup.select('a[href$=".pdf" i]'):
        return a
    return None                                # no direct PDF found

def resolve_fname(pdf_url: str, anchor) -> str:
    # 1.  data-download-title attribute (nicest)
    title = anchor.get("data-download-title")
    if title:
        return slugify(title) + ".pdf"

    # 2.  Content-Disposition filename
    try:
        h = S.head(pdf_url, allow_redirects=True, timeout=30)
        cd = h.headers.get("content-disposition", "")
        m  = re.search(r'filename="?([^";]+)', cd, re.I)
        if m:
            return slugify(unquote(m.group(1)))
    except Exception:
        pass

    # 3.  last segment of the URL
    slug = urlparse(pdf_url).path.split("/")[-1] or "part.pdf"
    return slugify(slug if slug.lower().endswith(".pdf") else slug + ".pdf")

def save_pdf(pdf_url: str, out_path: str):
    """
    Stream-download with resume, tqdm bar.
    """
    tmp     = out_path + ".part"
    resume  = os.path.exists(tmp)
    pos     = os.path.getsize(tmp) if resume else 0
    headers = {"Range": f"bytes={pos}-"} if resume else {}

    print("⇓", os.path.basename(out_path))
    with S.get(pdf_url, headers=headers, stream=True, timeout=(10, 60)) as r:
        ct = r.headers.get("content-type", "").lower()
        if "pdf" not in ct and r.status_code != 206:
            raise ValueError(f"non-PDF payload (content-type={ct!r})")

        total = int(r.headers.get("content-length", 0)) + pos
        bar = tqdm(
            total = total, initial = pos,
            unit = "B", unit_scale = True,
            desc = os.path.basename(out_path), leave = False
        )
        mode = "ab" if resume else "wb"
        with open(tmp, mode) as f:
            for chunk in r.iter_content(chunk_size=2**14):
                f.write(chunk)
                bar.update(len(chunk))
        bar.close()

    os.replace(tmp, out_path)

def html_print_to_pdf(part_url: str, out_path: str):
    """
    When no direct PDF is available, fall back to the rule's print view
    and convert it client-side via wkhtmltopdf.
    """
    print("✚ print-view → PDF", os.path.basename(out_path))
    print_url = part_url.rstrip("/") + "?format=print"
    html = get_soup(print_url).prettify()

    with tempfile.NamedTemporaryFile("w+", suffix=".html", delete=False) as tmp:
        tmp.write(html)
        tmp.flush()
        pdfkit.from_file(tmp.name, out_path, options={"quiet": ""})

def log_fail(url: str):
    with open(FAILED_LOG, "a", encoding="utf-8") as fh:
        fh.write(url + "\n")

# ────────── main ───────────────────────────────────────────────────────
def main():
    print("⋯ Discovering rule pages …")
    parts = discover_parts()
    print(f"✓ Found {len(parts):,} canon­ical Part/Chapter pages")

    ok = 0
    for part in parts:
        try:
            soup   = get_soup(part)
            anchor = find_pdf_anchor(soup)
            fname  : str
            path   : str

            if anchor:                                   # direct PDF
                pdf_url = urljoin(BASE, anchor["href"])
                fname   = resolve_fname(pdf_url, anchor)
                path    = os.path.join(OUT_DIR, fname)
                if not os.path.exists(path):
                    save_pdf(pdf_url, path)
            else:                                        # print-view fallback
                fname = slugify(urlparse(part).path.split("/")[-1]) + ".pdf"
                path  = os.path.join(OUT_DIR, fname)
                if not os.path.exists(path):
                    html_print_to_pdf(part, path)

            ok += 1
            if ok % 25 == 0:
                print(f"✓ {ok} PDFs so far …")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("✗", part, "→", e)
            log_fail(part)

    print(f"\nCompleted. {ok} PDFs saved to {OUT_DIR}/  – failures logged in {FAILED_LOG}")

if __name__ == "__main__":
    main()
