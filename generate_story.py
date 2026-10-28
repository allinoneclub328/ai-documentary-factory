
import json
import os
import sys
import time
import random
import urllib.error
import urllib.request
from pathlib import Path

# Gemini model
MODEL = "gemini-3.5-flash-lite"

# Output file
OUTPUT_FILE = Path("output/story.json")


def generate_documentary(person_name):
    """Generate a documentary story using the Gemini API."""

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. "
            "Add it to your GitHub repository secrets."
        )

    prompt = f"""
You are an experienced documentary filmmaker and researcher.

Create a compelling, fact-based documentary story about:
{person_name}

Requirements:
1. Research-minded storytelling with a strong opening hook.
2. Explain the person's background, challenges, work, and impact.
3. Build a clear narrative with engaging character development.
4. Include a meaningful climax and memorable ending.
5. Use simple, natural language suitable for voice-over narration.
6. Do not invent quotes, events, awards, dates, or achievements.
7. Clearly mark any information that needs independent verification.
8. Avoid presenting uncertain information as established fact.

Return ONLY valid JSON with this structure:
{{
  "person": "Person's name",
  "title": "Documentary title",
  "hook": "Opening hook",
  "research_notes": [
    "Important fact to verify"
  ],
  "story": {{
    "introduction": "Opening section",
    "background": "Early life and context",
    "struggle": "Challenges and obstacles",
    "turning_point": "Key turning point",
    "impact": "Work and impact",
    "climax": "Narrative climax",
    "conclusion": "Memorable ending"
  }},
  "telugu_adaptation": "A natural Telugu adaptation of the story",
  "hindi_adaptation": "A natural Hindi adaptation of the story",
  "fact_check_required": true
}}

Make the story detailed enough to serve as the foundation
for a documentary video. Do not claim you performed live
research unless you actually did.
"""

    
    payload = {
    "contents": [
        {
            "parts": [
                {"text": prompt}
            ]
        }
    ],
    "tools": [
        {
            "google_search": {}
        }
    ],
    "generationConfig": {
        "temperature": 1.0
    }
}

    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    result = None
    retryable_codes = {408, 429, 500, 502, 503, 504}

    # Retry temporary API failures up to 4 times.
    for attempt in range(4):
        try:
            print(f"Calling Gemini API (attempt {attempt + 1}/4)...")

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
                    f"Response: {error_body[:1500]}"
                ) from None

            if attempt == 3:
                raise RuntimeError(
                    f"Gemini API remained unavailable after 4 attempts. "
                    f"Last HTTP status: {error_code}.\n"
                    f"Response: {error_body[:1500]}"
                ) from None

            delay = (2 ** (attempt + 1)) + random.uniform(0, 1)

            print(
                f"Temporary API error {error_code}. "
                f"Retrying in {delay:.1f} seconds..."
            )
            time.sleep(delay)

        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == 3:
                raise RuntimeError(
                    "Gemini could not be reached after 4 attempts. "
                    f"Connection error: {error}"
                ) from None

            delay = (2 ** (attempt + 1)) + random.uniform(0, 1)

            print(
                f"Connection problem. "
                f"Retrying in {delay:.1f} seconds..."
            )
            time.sleep(delay)

    if result is None:
        raise RuntimeError("Gemini did not return a response.")

    # Extract the generated text.
    # Extract the generated text and Google Search research sources.
try:
    candidate = result["candidates"][0]

    generated_text = "".join(
        part.get("text", "")
        for part in candidate["content"]["parts"]
    )

    grounding = candidate.get("groundingMetadata", {})

    sources = [
        {
            "title": item["web"].get("title", "Untitled source"),
            "url": item["web"].get("uri", "")
        }
        for item in grounding.get("groundingChunks", [])
        if item.get("web", {}).get("uri")
    ]

except (KeyError, IndexError, TypeError):
    raise RuntimeError(
        "Gemini returned an unexpected response:\n"
        + json.dumps(result, ensure_ascii=False)[:1500]
    ) from None

    # Convert the JSON response into a Python object.
    try:
        story_data["research_sources"] = sources
story_data["search_queries"] = grounding.get("webSearchQueries", [])
    except json.JSONDecodeError:
        raise RuntimeError(
            "Gemini did not return valid JSON. Response:\n"
            + generated_text[:1500]
        ) from None

    return story_data


def main():
    if len(sys.argv) > 1:
        person_name = " ".join(sys.argv[1:])
    else:
        person_name = "Dr. Vijayalakshmi Deshmane"

    print(f"Generating documentary package for: {person_name}")

    story_data = generate_documentary(person_name)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            story_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Documentary package saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
