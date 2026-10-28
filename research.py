
import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path


OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "research.json"

USER_AGENT = "AI-Documentary-Factory/1.0 (educational research project)"


def fetch_json(url):
    """Fetch JSON from a public API without requiring an API key."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def search_wikipedia(person):
    """Search English Wikipedia for potentially relevant articles."""
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
            "url": (
                "https://en.wikipedia.org/?curid="
                + str(page_id)
            ),
            "snippet": item.get("snippet", "")
                .replace("<span class=\"searchmatch\">", "")
                .replace("</span>", ""),
            "source_type": "Wikipedia search result",
            "verification_status": "unverified"
        })

    return results


def fetch_summary(title):
    """Fetch an article summary through Wikipedia's REST API."""
    encoded_title = urllib.parse.quote(title.replace(" ", "_"), safe="")
    url = (
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + encoded_title
    )

    try:
        data = fetch_json(url)

        return {
            "title": data.get("title", title),
            "summary": data.get("extract", ""),
            "url": data.get("content_urls", {})
                .get("desktop", {})
                .get("page", ""),
            "source_type": "Wikipedia article summary",
            "verification_status": "unverified"
        }

    except (urllib.error.URLError, TimeoutError, ValueError):
        return {
            "title": title,
            "summary": "",
            "url": (
                "https://en.wikipedia.org/wiki/"
                + encoded_title
            ),
            "source_type": "Wikipedia article",
            "verification_status": "summary_unavailable"
        }


def research_person(person):
    print(f"Researching: {person}")
    print("Searching the free Wikipedia API...")

    try:
        search_results = search_wikipedia(person)
    except Exception as error:
        raise RuntimeError(
            "The research request failed. Check the network "
            "and try again. Details: " + str(error)
        ) from None

    articles = []

    for result in search_results:
        title = result["title"]
        print(f"Collecting article summary: {title}")

        summary = fetch_summary(title)
        articles.append(summary)

        # Be polite to the public API.
        time.sleep(0.5)

    package = {
        "person": person,
        "research_provider": "Wikimedia APIs",
        "research_status": (
            "results_found" if articles else "no_results_found"
        ),
        "source_count": len(articles),
        "sources": articles,
        "important_warning": (
            "These are discovery leads, not verified facts. "
            "Wikipedia may be incomplete or inaccurate. "
            "Check independent reliable sources before using "
            "claims in a documentary."
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
    print(f"Potential sources found: {len(articles)}")


def main():
    if len(sys.argv) < 2:
        print('Usage: python research.py "Person Name"')
        sys.exit(1)

    person = " ".join(sys.argv[1:]).strip()

    try:
        research_person(person)
    except (RuntimeError, OSError) as error:
        print(f"ERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
