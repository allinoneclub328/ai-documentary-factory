
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RESEARCH_FILE = Path("output/research.json")
FACT_CHECK_FILE = Path("output/fact_check.json")
OUTPUT_FILE = Path("output/story.json")

MODEL = "gemini-3.5-flash-lite"
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    f"models/{MODEL}:generateContent"
)


def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_evidence(research, fact_check):
    """Prepare source material without treating it as verified fact."""
    sources = research.get("sources", [])
    evidence = []

    for index, source in enumerate(sources, start=1):
        evidence.append({
            "source_id": f"S{index:03d}",
            "title": source.get("title", ""),
            "publisher": source.get("publisher", "Unknown"),
            "url": source.get("url", ""),
            "published_date": source.get("published_date"),
            "summary": source.get("summary", ""),
            "verification_status": "unverified"
        })

    return {
        "person": research.get("person", "Unknown"),
        "research_status": research.get("research_status", "unknown"),
        "sources": evidence,
        "fact_check_status": fact_check.get(
            "fact_check_status", "review_required"
        ),
        "important_warning": (
            "These are research leads, not verified facts. "
            "Do not claim a detail is confirmed merely because it appears "
            "in a headline, snippet, or repeated report."
        )
    }


def generate_with_gemini(api_key, prompt):
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "subject": {"type": "STRING"},
                    "language": {"type": "STRING"},
                    "opening_hook": {"type": "STRING"},
                    "narration": {"type": "STRING"},
                    "scenes": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "scene_number": {"type": "INTEGER"},
                                "scene_title": {"type": "STRING"},
                                "narration": {"type": "STRING"},
                                "visual_suggestion": {"type": "STRING"},
                                "source_ids": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"}
                                },
                                "verification_needed": {
                                    "type": "BOOLEAN"
                                }
                            },
                            "required": [
                                "scene_number",
                                "scene_title",
                                "narration",
                                "visual_suggestion",
                                "source_ids",
                                "verification_needed"
                            ]
                        }
                    },
                    "ending": {"type": "STRING"},
                    "source_notes": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "unverified_claims": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "human_review_required": {"type": "BOOLEAN"}
                },
                "required": [
                    "title",
                    "subject",
                    "language",
                    "opening_hook",
                    "narration",
                    "scenes",
                    "ending",
                    "source_notes",
                    "unverified_claims",
                    "human_review_required"
                ]
            }
        }
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    for attempt in range(3):
        try:
            with urlopen(request, timeout=90) as response:
                result = json.loads(response.read().decode("utf-8"))

            parts = result["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
            return json.loads(text)

        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")

            if error.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue

            raise RuntimeError(
                f"Gemini API error {error.code}: {details[:1000]}"
            ) from error

        except (URLError, TimeoutError) as error:
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Network error: {error}") from error

    raise RuntimeError("Gemini request failed after retries.")


def main():
    if len(sys.argv) > 1:
        subject = " ".join(sys.argv[1:]).strip()
    else:
        subject = ""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is missing.")

    research = load_json(RESEARCH_FILE)
    fact_check = load_json(FACT_CHECK_FILE)

    research_subject = research.get("person", "Unknown")
    if not subject:
        subject = research_subject

    if subject.lower() != research_subject.lower():
        raise ValueError(
            f"Requested subject '{subject}' does not match research subject "
            f"'{research_subject}'. Run research.py for the correct subject."
        )

    evidence = build_evidence(research, fact_check)

    if not evidence["sources"]:
        raise RuntimeError(
            "No research sources found. Refusing to generate a biography "
            "without source material."
        )

    prompt = f"""
You are a careful documentary writer.

SUBJECT: {subject}
OUTPUT LANGUAGE: English
FORMAT: An engaging short documentary draft.

SOURCE MATERIAL (UNVERIFIED):
{json.dumps(evidence, ensure_ascii=False, indent=2)}

RULES:
1. Treat every supplied source as unverified research material.
2. Do not invent events, dialogue, quotations, dates, awards, statistics,
   institutions, medical achievements, personal struggles, or motivations.
3. Do not claim to have read the full articles. Only titles, summaries,
   and metadata have been supplied.
4. Use only information explicitly supported by the supplied summaries.
5. If a detail is uncertain or only suggested by a headline, leave it out
   of the narration and add it to unverified_claims.
6. Make the story engaging through structure, pacing, and clear narration,
   not fabricated drama.
7. Do not invent a scene from the person's childhood or private life.
8. Give each scene source_ids using the supplied source IDs, such as S001.
   Use an empty array when a scene is general framing rather than factual.
9. A source reference indicates where a lead came from; it does not mean
   the claim is verified.
10. Set verification_needed to true for any scene containing biographical
    or historical claims that a human must verify.
11. If the evidence is too limited, explicitly say so and create a cautious
    draft rather than filling gaps with assumptions.
12. Include source_notes explaining that original articles must be checked.
13. Set human_review_required to true.
14. Use clear, natural English suitable for narration.
15. Return valid JSON matching the requested schema.

Create approximately 5 to 8 scenes. Every factual scene must include its
relevant source IDs. Do not add facts simply to reach the scene count.
"""

    story = generate_with_gemini(api_key, prompt)

    # Enforce review flags in the saved result.
    story["subject"] = subject
    story["language"] = "English"
    story["generation_status"] = "draft_requires_fact_check"
    story["research_status"] = evidence["research_status"]
    story["fact_check_status"] = evidence["fact_check_status"]
    story["human_review_required"] = True
    story["generated_by"] = MODEL
    story["source_registry"] = evidence["sources"]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(story, file, ensure_ascii=False, indent=2)

    print("Evidence-aware documentary draft created.")
    print(f"Subject: {subject}")
    print(f"Sources supplied to Gemini: {len(evidence['sources'])}")
    print(f"Scenes generated: {len(story.get('scenes', []))}")
    print(f"Output: {OUTPUT_FILE}")
    print("Reminder: The script still requires human fact-checking.")


if __name__ == "__main__":
    main()
