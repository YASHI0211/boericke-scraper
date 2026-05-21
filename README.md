# Boericke's Materia Medica Scraper

A Python web scraper that extracts all remedy data from Boericke's Homoeopathic Materia Medica and saves it as structured JSON — built for jarvis.care.

## Setup

```bash
git clone <your-repo-url>
cd boericke-scraper
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python scraper.py
```

## Output Files

| File | Description |
|---|---|
| boericke_remedies.json | Full scraped dataset (all A-Z remedies) |
| sample_output.json | 5 remedy sample for review |
| failed_urls.txt | Any failed URLs for retry |

## Features

- Scrapes all A-Z remedy pages automatically
- Resumable — skips already scraped URLs if restarted
- Extracts name, common name, general description, sections, relationships
- Bonus: keyword extraction and potency parsing
- Polite scraping with 0.7s delay between requests
- Failed URLs logged separately

## Dependencies

- requests
- beautifulsoup4