
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path


OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "research.json"

USER_AGENT = "AI-Documentary-Factory/1.0 (educational research project)"


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


# ------------------------------------------------------------
# SOURCE 1: WIKIPEDIA
# ------------------------------------------------------------

def search_wikipedia(person):
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": person,
        "format": "json",
        "srlimit": 5
    })

    url = "https://en.wikipedia.org/w/api.php?" + params
    data = fetch_json(url)

    results = []

    for item in data.get("query", {}).get("search", []):
        title = item.get("title", "")
        page_id = item.get("pageid")

        if not title or not page_id:
            continue

        results.append({
            "title": title,
            "url": "https://en.wikipedia.org/?curid=" + str(page_id),
            "summary": clean_html(item.get("snippet", "")),
            "publisher": "Wikipedia",
            "source_type": "encyclopedia",
            "published_date": None,
            "verification_status": "unverified"
        })

    return results


# ------------------------------------------------------------
# SOURCE 2: GOOGLE NEWS RSS
# ------------------------------------------------------------

def search_google_news(person):
    query = urllib.parse.urlencode({
        "q": '"' + person + '"',
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en"
    })

    url = "https://news.google.com/rss/search?" + query
    xml_data = fetch_text(url)

    root = ET.fromstring(xml_data)
    results = []

    for item in root.findall(".//item")[:10]:
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        description = item.findtext("description", default="")
        pub_date = item.findtext("pubDate", default="").strip()

        source_element = item.find("source")
        publisher = (
            source_element.text.strip()
            if source_element is not None and source_element.text
            else "Unknown publisher"
        )

        if not title or not link:
            continue

        results.append({
            "title": title,
            "url": link,
            "summary": clean_html(description),
            "publisher": publisher,
            "source_type": "news search result",
            "published_date": pub_date or None,
            "verification_status": "unverified"
        })

    return results


# ------------------------------------------------------------
# COMBINE AND SAVE RESEARCH
# ------------------------------------------------------------

def research_person(person):
    print(f"Researching: {person}")

    all_sources = []
    errors = []

    # Wikipedia search
    try:
        print("Searching Wikipedia...")
        wiki_results = search_wikipedia(person)
        all_sources.extend(wiki_results)
        print(f"Wikipedia results: {len(wiki_results)}")
    except Exception as error:
        print(f"Wikipedia search failed: {error}")
        errors.append({
            "source": "Wikipedia",
            "error": str(error)
        })

    time.sleep(1)

    # Google News RSS search
    try:
        print("Searching Google News RSS...")
        news_results = search_google_news(person)
        all_sources.extend(news_results)
        print(f"News results: {len(news_results)}")
    except Exception as error:
        print(f"News search failed: {error}")
        errors.append({
            "source": "Google News RSS",
            "error": str(error)
        })

    # Remove duplicate URLs.
    unique_sources = []
    seen_urls = set()

    for source in all_sources:
        url = source.get("url", "").strip()

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        unique_sources.append(source)

    package = {
        "person": person,
        "research_provider": [
            "Wikimedia APIs",
            "Google News RSS"
        ],
        "research_status": (
            "results_found" if unique_sources else "no_results_found"
        ),
        "source_count": len(unique_sources),
        "sources": unique_sources,
        "search_errors": errors,
        "verification_status": "not_verified",
        "important_warning": (
            "Search results are research leads, not verified facts. "
            "A news headline or search snippet is not sufficient "
            "evidence by itself. Open the original publisher's page, "
            "check the article date and context, and corroborate "
            "important claims with independent reliable sources. "
            "Multiple results may repeat the same original report."
        )
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            package,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Research saved to: {OUTPUT_FILE}")
    print(f"Unique results: {len(unique_sources)}")

    if errors:
        print("Warning: one or more research sources failed.")

    if not unique_sources:
        print("No results found. Manual research will be needed.")


def main():
    if len(sys.argv) < 2:
        print('Usage: python research.py "Person Name"')
        sys.exit(1)

    person = " ".join(sys.argv[1:]).strip()

    try:
        research_person(person)
    except (OSError, RuntimeError) as error:
        print(f"ERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
