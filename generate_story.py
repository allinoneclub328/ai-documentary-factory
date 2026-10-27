
import json
from pathlib import Path
from datetime import datetime, timezone

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_documentary(topic):
    story = {
        "topic": topic,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "languages": {
            "en": {
                "title": f"The Story of {topic}",
                "script": (
                    f"Every remarkable life has a story. "
                    f"This documentary explores {topic}, "
                    "the challenges faced, the decisions made, "
                    "and the impact left behind."
                )
            },
            "te": {
                "title": f"{topic} కథ",
                "script": (
                    f"{topic} జీవితంలోని ప్రయాణాన్ని ఈ కథనం "
                    "పరిచయం చేస్తుంది. వారి సవాళ్లు, నిర్ణయాలు, "
                    "సమాజంపై చూపిన ప్రభావాన్ని తెలుసుకుందాం."
                )
            },
            "hi": {
                "title": f"{topic} की कहानी",
                "script": (
                    f"यह कहानी {topic} के जीवन के सफर को "
                    "समझने का प्रयास करती है। इसमें उनकी "
                    "चुनौतियों, फैसलों और समाज पर पड़े प्रभाव "
                    "को जानेंगे।"
                )
            }
        }
    }

    output_file = OUTPUT_DIR / "story.json"
    output_file.write_text(
        json.dumps(story, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Story package created: {output_file}")
    return story

if __name__ == "__main__":
    import sys

    topic = " ".join(sys.argv[1:]).strip()

    if not topic:
        topic = "Dr. Vijayalakshmi Deshmane"

    generate_documentary(topic)
