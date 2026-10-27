
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

MODEL = "gemini-3.8-flash"
OUTPUT_DIR = Path("output")


def generate_documentary(topic):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    prompt = f"""
Create a documentary script package about: {topic}

Return ONLY valid JSON with this structure:
{{
  "topic": "{topic}",
  "created_at": "{datetime.now(timezone.utc).isoformat()}",
  "fact_check_required": true,
  "languages": {{
    "en": {{"title": "...", "script": "..."}},
    "te": {{"title": "...", "script": "..."}},
    "hi": {{"title": "...", "script": "..."}}
  }},
  "verification_notes": ["claims that need checking"]
}}

Requirements:
- Write an engaging, cinematic documentary narration.
- Create separate, natural scripts in English, Telugu and Hindi.
- Include a strong opening, chronological storytelling and a conclusion.
- Never invent quotations, dates, awards or events.
- If a fact is uncertain, flag it in verification_notes.
- Do not claim that facts have been independently verified.
- Keep each script suitable for a short initial documentary draft.
"""

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 5000
        }
    }

    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Gemini API request failed with HTTP {error.code}. "
            "Check API access, model availability and usage limits."
        ) from None

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no generated content.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)

    story = json.loads(text)

    for language in ("en", "te", "hi"):
        if not story.get("languages", {}).get(language, {}).get("script"):
            raise RuntimeError(f"Missing script for language: {language}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / "story.json"
    output_file.write_text(
        json.dumps(story, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Gemini generated the story package: {output_file}")


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]).strip()

    if not topic:
        topic = "Dr. Vijayalakshmi Deshmane"

    generate_documentary(topic)
