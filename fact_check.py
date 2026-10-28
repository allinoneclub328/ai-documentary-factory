
import json
import re
from pathlib import Path
from collections import defaultdict

INPUT_FILE = Path("output/research.json")
OUTPUT_FILE = Path("output/fact_check.json")


def normalize(text):
    """Normalize text to help identify exact or near-identical repeats."""
    text = text.lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def split_sentences(text):
    """Split summaries into sentence-sized evidence candidates."""
    if not isinstance(text, str):
        return []

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip().split()) >= 5
    ]


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Research file not found: {INPUT_FILE}. "
            "Run research.py first."
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        research = json.load(file)

    sources = research.get("sources", [])
    grouped_claims = defaultdict(list)
    source_records = []

    for index, source in enumerate(sources, start=1):
        title = source.get("title", "").strip()
        summary = source.get("summary", "").strip()
        url = source.get("url", "").strip()

        source_records.append({
            "source_id": f"S{index:03d}",
            "title": title,
            "url": url,
            "publisher": source.get("publisher", "Unknown"),
            "source_type": source.get("source_type", "Unknown"),
            "published_date": source.get("published_date"),
            "verification_status": "not_independently_verified"
        })

        # Titles help identify topics; summaries provide candidate claims.
        for sentence in split_sentences(summary):
            key = normalize(sentence)

            if key:
                grouped_claims[key].append({
                    "source_id": f"S{index:03d}",
                    "source_title": title,
                    "publisher": source.get("publisher", "Unknown"),
                    "url": url,
                    "published_date": source.get("published_date")
                })

    claims = []

    for number, (key, evidence) in enumerate(
        grouped_claims.items(), start=1
    ):
        claims.append({
            "claim_id": f"C{number:03d}",
            "claim_text": evidence[0]["source_title"]
            if not key else next(
                sentence
                for source in sources
                for sentence in split_sentences(
                    source.get("summary", "")
                )
                if normalize(sentence) == key
            ),
            "evidence_count": len(evidence),
            "evidence": evidence,
            "verification_status": "needs_manual_verification",
            "review_notes": [
                "Check the original article, not just the headline or snippet.",
                "Confirm the claim using reliable primary or independent sources.",
                "Repeated wording may come from the same original report.",
                "Do not treat this claim as a confirmed fact yet."
            ]
        })

    report = {
        "person": research.get("person", "Unknown"),
        "fact_check_status": "review_required",
        "research_status": research.get("research_status", "unknown"),
        "source_count": len(sources),
        "candidate_claim_count": len(claims),
        "verified_claim_count": 0,
        "sources": source_records,
        "candidate_claims": claims,
        "limitations": [
            "This program organizes research; it does not establish truth.",
            "Source summaries may be incomplete or inaccurate.",
            "Multiple articles may repeat the same original reporting.",
            "All candidate claims require human verification."
        ]
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print("Fact-check report created successfully.")
    print(f"Sources reviewed: {len(sources)}")
    print(f"Candidate claims: {len(claims)}")
    print(f"Output: {OUTPUT_FILE}")
    print("Reminder: No claims have been verified automatically.")


if __name__ == "__main__":
    main()
