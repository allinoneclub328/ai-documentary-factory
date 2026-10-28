
import json
import os
import sys
import time
import random
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-3.5-flash-lite"
OUTPUT_FILE = Path("output/story.json")


def generate_documentary(person_name):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from GitHub repository secrets."
        )

    prompt = f"""
You are a documentary researcher and experienced screenwriter.

Create a compelling, factual documentary story about:
{person_name}

Research requirements:
- Use Google Search to research the person's real life and achievements.
- Prefer official biographies, government announcements, reputable news
  organizations, institutional websites, and published interviews.
- Do not invent childhood events, quotes, dates, awards, statistics,
  workplaces, patient counts, or personal experiences.
- If a fact cannot be verified, say it needs verification.
- Keep the story engaging without exaggerating the person's achievements.
- Write a detailed English documentary narrative first.
- Also provide natural Telugu and Hindi adaptations based on the same facts.

Return ONLY valid JSON using this structure:
{{
  "person": "Full name",
  "title": "Documentary title",
  "hook": "Opening hook",
  "research_notes": [
    "Facts that still require verification"
  ],
  "story": {{
    "introduction": "Opening",
    "background": "Verified background",
    "struggle": "Documented challenges",
    "turning_point": "Verified turning point",
    "impact": "Documented achievements and impact",
    "climax": "Narrative high point based on verified events",
    "conclusion": "Ending"
  }},
  "telugu_adaptation": "Complete Telugu documentary narration",
  "hindi_adaptation": "Complete Hindi documentary narration",
  "fact_check_required": true
}}

Do not include Markdown fences around the JSON.
The Google Search sources will be saved separately by the program.
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
      
        "generationConfig": {
            "temperature": 0.7
        }
    }

    request = urllib.request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{MODEL}:generateContent"
        ),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    result = None
    retryable_codes = {408, 429, 500, 502, 503, 504}

    for attempt in range(4):
        try:
            print(f"Gemini API attempt {attempt + 1}/4...")

            with urllib.request.urlopen(
                request,
                timeout=180
            ) as response:
                result = json.loads(
                    response.read().decode("utf-8")
                )

            break

        except urllib.error.HTTPError as error:
            error_code = error.code
            error_body = error.read().decode(
                "utf-8", errors="replace"
            )

            if error_code not in retryable_codes:
                raise RuntimeError(
                    f"Gemini API returned HTTP {error_code}.\n"
                    f"Response: {error_body[:2000]}"
                ) from None

            if attempt == 3:
                raise RuntimeError(
                    f"Gemini failed after 4 attempts. "
                    f"Last HTTP status: {error_code}.\n"
                    f"Response: {error_body[:2000]}"
                ) from None

            delay = 2 ** (attempt + 1) + random.uniform(0, 1)

            print(
                f"Temporary HTTP {error_code}. "
                f"Retrying in {delay:.1f} seconds..."
            )
            time.sleep(delay)

        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(
                    f"Connection failed after 4 attempts: {error}"
                ) from None

            delay = 2 ** (attempt + 1) + random.uniform(0, 1)
            print(f"Connection problem. Retrying in {delay:.1f}s...")
            time.sleep(delay)

    if result is None:
        raise RuntimeError("Gemini returned no response.")

    # Read the generated text and search-grounding metadata.
    try:
        candidate = result["candidates"][0]
        parts = candidate["content"]["parts"]

        generated_text = "".join(
            part.get("text", "")
            for part in parts
        )

        grounding = candidate.get("groundingMetadata", {})

    except (KeyError, IndexError, TypeError):
        raise RuntimeError(
            "Unexpected Gemini response:\n"
            + json.dumps(result, ensure_ascii=False)[:2000]
        ) from None

    if not generated_text.strip():
        raise RuntimeError("Gemini returned empty text.")

    # Parse the story JSON.
    try:
        story_data = json.loads(generated_text)

    except json.JSONDecodeError:
        raise RuntimeError(
            "Gemini did not return valid JSON. Response:\n"
            + generated_text[:2000]
        ) from None

    # Preserve source URLs returned by Google Search grounding.
    sources = []

    for item in grounding.get("groundingChunks", []):
        web_item = item.get("web", {})
        url = web_item.get("uri")

        if url:
            sources.append({
                "title": web_item.get("title", "Untitled source"),
                "url": url
            })

    # Remove duplicate source URLs.
    unique_sources = []
    seen_urls = set()

    for source in sources:
        if source["url"] not in seen_urls:
            seen_urls.add(source["url"])
            unique_sources.append(source)

    story_data["research_sources"] = unique_sources
    story_data["search_queries"] = grounding.get(
        "webSearchQueries", []
    )

    # Flag for human verification before publishing.
    story_data["fact_check_required"] = True

    return story_data


def main():
    if len(sys.argv) > 1:
        person_name = " ".join(sys.argv[1:])
    else:
        person_name = "Dr. Vijayalakshmi Deshmane"

    print(f"Generating documentary for: {person_name}")

    story_data = generate_documentary(person_name)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            story_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Story package saved to: {OUTPUT_FILE}")
    print(f"Research sources saved: {len(story_data['research_sources'])}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
