import re

import requests 
from bs4 import BeautifulSoup
import json
import time
import os
from typing import Optional
from collections import Counter
# ─── Configuration ───────────────────────────────────────────
BASE_URL = "http://homeoint.org/books/boericmm/"
OUTPUT_FILE = "boericke_remedies.json"
FAILED_FILE = "failed_urls.txt"
DELAY = 0.7  # seconds between requests
LETTERS = [chr(i) for i in range(ord('a'), ord('z') + 1)]
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; JarvisCareBot/1.0)"
})
# ─── Helper Utilities ─────────────────────────────────────────

def load_existing_data() -> list[dict]:
    
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"📂 Loaded {len(data)} existing remedies from {OUTPUT_FILE}")
        return data
    return []


def get_scraped_urls(data: list[dict]) -> set[str]:
    
    return {remedy["source_url"] for remedy in data}


def log_failed_url(url: str) -> None:
    
    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")


def save_output(data: list[dict]) -> None:
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved {len(data)} remedies → {OUTPUT_FILE}")


def clean_text(text: str) -> str:
    
    return re.sub(r"\s+", " ", text).strip()

# ─── Bonus: Keyword Extraction ────────────────────────────────

# Ye common English words hain jo symptoms mein kaam ke nahi hain
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "it", "its", "this", "that", "as", "if", "when",
    "which", "who", "not", "no", "may", "can", "more", "also", "after",
    "before", "during", "over", "under", "than", "then", "so", "up", "out",
    "all", "into", "through", "pain", "great", "very", "much", "one", "two",
}


def extract_keywords(general: str, sections: dict[str, str], top_n: int = 10) -> list[str]:
    
   
    combined = general + " " + " ".join(sections.values())
    words = re.findall(r"[a-z]{4,}", combined.lower())
    filtered = [w for w in words if w not in STOPWORDS]
    most_common = Counter(filtered).most_common(top_n)
    return [word for word, _ in most_common]


# ─── Bonus: Potency Extraction ────────────────────────────────

def extract_potencies(sections: dict[str, str]) -> list[str]:
    
    dose_text = ""
    for key in sections:
        if key.lower() == "dose":
            dose_text = sections[key].lower()
            break

   
    potencies = re.findall(r"\b(?:\d+\s*(?:x|c|m|lm|cm)|lm|cm)\b", dose_text)

   
    return [re.sub(r"\s+", "", p) for p in potencies]

def fetch_letter_index(letter: str) -> Optional[BeautifulSoup]:
    url = f"{BASE_URL}{letter}.htm"
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"  ❌ Failed to fetch index for '{letter.upper()}': {e}")
        log_failed_url(url)
        return None


def parse_remedy_links(soup: BeautifulSoup, letter: str) -> list[dict]:
    remedies = []
    blockquote = soup.find("blockquote")
    if not blockquote:
        return remedies

    for a_tag in blockquote.find_all("a", href=True):
        abbr = clean_text(a_tag.get_text()).upper()
        href = a_tag["href"].strip()

        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE_URL + href.lstrip("/")

        if abbr:
            remedies.append({
                "abbreviation": abbr,
                "url": full_url,
                "letter": letter.upper(),
            })

    return remedies


def scrape_remedy_page(url: str, abbreviation: str, letter: str) -> Optional[dict]:
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"    ❌ Failed: {url} — {e}")
        log_failed_url(url)
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    full_name   = ""
    common_name = None

    for tag in soup.find_all(["h1", "h2", "h3", "b"], limit=10):
        text = clean_text(tag.get_text())
        if text and re.search(r"[A-Z]{3,}", text):
            paren_match = re.search(r"\(([^)]+)\)", text)
            if paren_match:
                common_name = clean_text(paren_match.group(1))
                full_name   = clean_text(text[:text.index("(")]).strip("- ").strip()
            else:
                full_name = text.strip("- ").strip()
            break

    if not full_name:
        full_name = abbreviation

    general  = ""
    sections: dict[str, str] = {}
    relationships: Optional[str] = None

    current_section     = None
    current_text        = []
    general_parts       = []
    found_first_section = False

    body = soup.find("body") or soup

    for element in body.descendants:
        if element.name == "b":
            heading_text = clean_text(element.get_text())

            if re.match(r"^[A-Z][a-zA-Z\s]+\.--", heading_text):
                section_name = heading_text.replace(".--", "").strip()

                if not found_first_section:
                    general = clean_text(" ".join(general_parts))
                    found_first_section = True
                else:
                    if current_section:
                        section_text = clean_text(" ".join(current_text))
                        if current_section.lower() == "relationships":
                            relationships = section_text
                        else:
                            sections[current_section] = section_text

                current_section = section_name
                current_text    = []

        elif element.name is None:
            text = clean_text(str(element))
            if not text:
                continue

            if not found_first_section:
                general_parts.append(text)
            elif current_section:
                current_text.append(text)

    if current_section and current_text:
        section_text = clean_text(" ".join(current_text))
        if current_section.lower() == "relationships":
            relationships = section_text
        else:
            sections[current_section] = section_text

    if not found_first_section:
        general = clean_text(" ".join(general_parts))

    keywords  = extract_keywords(general, sections)
    potencies = extract_potencies(sections)

    return {
        "abbreviation": abbreviation,
        "full_name":     full_name,
        "common_name":   common_name,
        "source_url":    url,
        "letter":        letter,
        "general":       general,
        "sections":      sections,
        "relationships": relationships,
        "keywords":      keywords,
        "potencies":     potencies,
    }

def main() -> None:
    data = load_existing_data()
    scraped_urls = get_scraped_urls(data)

    for letter in LETTERS:
        print(f"\n📖 Processing letter: {letter.upper()}")

        soup = fetch_letter_index(letter)
        if not soup:
            continue

        remedy_links = parse_remedy_links(soup, letter)
        total = len(remedy_links)
        print(f"   Found {total} remedies")

        for idx, remedy_info in enumerate(remedy_links, start=1):
            url          = remedy_info["url"]
            abbreviation = remedy_info["abbreviation"]
            letter_upper = remedy_info["letter"]

            if url in scraped_urls:
                print(f"  ⏭️  Skipping (already scraped): {abbreviation}")
                continue

            result = scrape_remedy_page(url, abbreviation, letter_upper)

            if result:
                data.append(result)
                scraped_urls.add(url)
                print(f"  [{letter_upper}] Scraped {idx}/{total} - {result['full_name']}")

            save_output(data)
            time.sleep(DELAY)

    print(f"\n✅ Done! Total remedies scraped: {len(data)}")
    save_output(data)


if __name__ == "__main__":
    main()
