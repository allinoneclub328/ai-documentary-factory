
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent"
)

OUTPUT_DIR = Path("output")
OUTPUT_FILE = OUTPUT_DIR / "story.json"

MAX_ATTEMPTS = 3


# ============================================================
# DOCUMENTARY GENERATION INSTRUCTIONS
# ============================================================

def build_prompt(person):
    return f"""
You are an experienced documentary researcher, fact-checker,
screenwriter, and multilingual documentary editor.

Create a documentary story package about this real person:

PERSON: {person}

IMPORTANT:
You do not have verified live research sources in this task.
Your own knowledge is not equivalent to verified evidence.

NEVER invent:
- Childhood incidents or poverty anecdotes
- Conversations or private thoughts
- Dates, statistics, awards, appointments, or achievements
- Medical cases, patient counts, or lives saved
- Quotes, dramatic scenes, or claims about family members
- Institutional affiliations that you cannot confidently support

If a specific claim is uncertain, either omit it or put it in
the verification list. Do not make it sound like an established fact.

STORYTELLING GOAL:
Make the documentary engaging, emotionally compelling, and
cinematic without sacrificing factual accuracy.

Avoid generic motivational writing such as:
"She overcame every obstacle and changed thousands of lives."

Instead, build the narrative around documented milestones,
real decisions, verified obstacles, and meaningful consequences.

Do not invent a dramatic climax merely to make the story exciting.
Use the most meaningful verified turning point available.
If the available evidence is insufficient, state that more research
is required before producing a final documentary script.

OUTPUT REQUIREMENTS:

Return ONLY valid JSON. Do not use Markdown fences or commentary.

Use exactly this structure:

{{
  "person": "{person}",
  "title": "A concise documentary title",
  "hook": "A compelling opening based only on supportable facts",
  "research_notes": [
    "Important claims that require verification"
  ],
  "story": {{
    "introduction": "Introduce the person and the central question.",
    "background": "Describe only supportable background information.",
    "struggle": "Describe documented challenges, if established.",
    "turning_point": "Explain a documented turning point, if known.",
    "impact": "Describe documented work and its significance.",
    "climax": "Build around a meaningful documented event or decision.",
    "conclusion": "End with a thoughtful, evidence-based takeaway."
  }},
  "telugu_adaptation": "A natural Telugu adaptation of the story.",
  "hindi_adaptation": "A natural Hindi adaptation of the story.",
  "fact_check_required": true,
  "factual_claims_to_verify": [
    {{
      "claim": "A specific factual claim",
      "reason": "Why it needs checking",
      "status": "unverified"
    }}
  ],
  "research_sources": [],
  "search_queries": []
}}

ADDITIONAL RULES:

1. Keep the person's name accurate in all three languages.
2. Use natural Telugu script for Telugu and Devanagari for Hindi.
3. Do not mix scripts accidentally.
4. Do not translate a person's surname into a different surname.
5. Keep the Telugu and Hindi adaptations faithful to the English story.
6. Do not claim that sources were consulted when none were provided.
7. Do not fabricate source URLs or citations.
8. Keep research_sources empty unless actual source information
   has been supplied and verified.
9. Keep search_queries empty because no live search was performed.
10. Every uncertain, important biographical claim should be listed
    in factual_claims_to_verify.
11. If the person's identity or biography is ambiguous, explicitly
    mention that identity verification is needed.
12. The result is a DRAFT, not a publication-ready documentary.
13. Return a complete JSON object with all required keys.
"""


# ============================================================
# CALL GEMINI API
# ============================================================

def call_gemini(prompt):
    if not API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Check your GitHub repository "
            "secret and workflow environment variables."
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "maxOutputTokens": 7000
        }
    }

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(
                f"Calling Gemini API "
                f"(attempt {attempt}/{MAX_ATTEMPTS})..."
            )

            with urllib.request.urlopen(
                request,
                timeout=120
            ) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )

            candidates = response_data.get("candidates", [])

            if not candidates:
                raise RuntimeError(
                    "Gemini returned no candidates. "
                    "The response may have been blocked or incomplete."
                )

            parts = (
                candidates[0]
                .get("content", {})
                .get("parts", [])
            )

            text_parts = [
                part["text"]
                for part in parts
                if isinstance(part.get("text"), str)
            ]

            generated_text = "\n".join(text_parts).strip()

            if not generated_text:
                raise RuntimeError(
                    "Gemini returned an empty text response."
                )

            return generated_text

        except urllib.error.HTTPError as error:
            error_body = error.read().decode(
                "utf-8",
                errors="replace"
            )

            # Do not print the API key or request headers.
            print(f"Gemini HTTP error: {error.code}")

            if error.code == 429:
                raise RuntimeError(
                    "Gemini quota or rate limit reached. "
                    "Check the model's available quota and retry later. "
                    "Do not enable paid billing unless you decide to."
                ) from None

            retryable = error.code in (500, 502, 503, 504)

            if retryable and attempt < MAX_ATTEMPTS:
                wait_seconds = 2 ** attempt
                print(
                    f"Temporary server error. "
                    f"Retrying in {wait_seconds} seconds..."
                )
                time.sleep(wait_seconds)
                continue

            # Show a short, sanitized diagnostic if available.
            try:
                details = json.loads(error_body)
                message = (
                    details.get("error", {}).get("message", "")
                )
            except (json.JSONDecodeError, AttributeError):
                message = ""

            if message:
                print(f"API message: {message[:500]}")

            raise RuntimeError(
                f"Gemini API request failed with HTTP {error.code}."
            ) from None

        except urllib.error.URLError as error:
            if attempt < MAX_ATTEMPTS:
                wait_seconds = 2 ** attempt
                print(
                    f"Network error. Retrying in {wait_seconds} seconds..."
                )
                time.sleep(wait_seconds)
            else:
                raise RuntimeError(
                    f"Could not connect to Gemini: {error.reason}"
                ) from None

    raise RuntimeError("Gemini request failed after all attempts.")


# ============================================================
# PARSE AND VALIDATE JSON
# ============================================================

def parse_json_response(text):
    cleaned = text.strip()

    # Remove Markdown fences if the model unexpectedly adds them.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Gemini returned invalid JSON near character "
            f"{error.pos}. Try running the workflow again."
        ) from None

    if not isinstance(data, dict):
        raise RuntimeError("The generated JSON must be an object.")

    required_keys = [
        "person",
        "title",
        "hook",
        "research_notes",
        "story",
        "telugu_adaptation",
        "hindi_adaptation",
        "fact_check_required",
        "factual_claims_to_verify",
        "research_sources",
        "search_queries"
    ]

    missing = [
        key for key in required_keys
        if key not in data
    ]

    if missing:
        raise RuntimeError(
            "Generated JSON is missing required keys: "
            + ", ".join(missing)
        )

    if not isinstance(data["story"], dict):
        raise RuntimeError("'story' must be a JSON object.")

    story_sections = [
        "introduction",
        "background",
        "struggle",
        "turning_point",
        "impact",
        "climax",
        "conclusion"
    ]

    for section in story_sections:
        if not isinstance(data["story"].get(section), str):
            raise RuntimeError(
                f"Story section '{section}' is missing or invalid."
            )

    # The script did not perform live research. Do not allow the
    # model to imply that source verification happened automatically.
    data["research_sources"] = []
    data["search_queries"] = []
    data["fact_check_required"] = True

    if not isinstance(data["factual_claims_to_verify"], list):
        data["factual_claims_to_verify"] = []

    if not isinstance(data["research_notes"], list):
        data["research_notes"] = []

    data["generation_status"] = "draft_requires_fact_check"
    data["research_status"] = "not_performed"
    data["generated_by"] = MODEL

    return data


# ============================================================
# SAVE OUTPUT
# ============================================================

def save_story(data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(f"Documentary package saved to: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(
            'Usage: python generate_story.py "Person Name"'
        )
        sys.exit(1)

    person = " ".join(sys.argv[1:]).strip()

    if not person:
        print("Error: Please provide a person's name.")
        sys.exit(1)

    print("=" * 60)
    print("AI DOCUMENTARY FACTORY")
    print("=" * 60)
    print(f"Person: {person}")
    print(f"Model: {MODEL}")

    try:
        prompt = build_prompt(person)
        generated_text = call_gemini(prompt)
        story_package = parse_json_response(generated_text)
        save_story(story_package)

        print("Documentary draft generated successfully.")
        print("Fact-checking is still required before publication.")

    except (RuntimeError, OSError) as error:
        print(f"ERROR: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
