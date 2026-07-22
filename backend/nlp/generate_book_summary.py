import json
import os
import re
from google import genai

# ======================================================
# CONFIGURATION
# ======================================================

API_KEY = "YOUR_GEMINI_API_KEY"

MODEL = "gemini-2.5-flash-lite"

BOOK_FOLDER = "output/deiva_yaanai"

CHAPTERS_FILE = os.path.join(
    BOOK_FOLDER,
    "chapters.json"
)

OUTPUT_FILE = os.path.join(
    BOOK_FOLDER,
    "book_summary.json"
)

SUMMARY_CHAPTERS = 10


# ======================================================
# GEMINI CLIENT
# ======================================================

client = genai.Client(api_key=API_KEY)


# ======================================================
# LOAD CHAPTERS
# ======================================================

def load_chapters():

    if not os.path.exists(CHAPTERS_FILE):
        raise FileNotFoundError(f"Cannot find {CHAPTERS_FILE}")

    with open(CHAPTERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract the chapters list
    chapters = data.get("chapters", [])

    if not chapters:
        raise ValueError("No chapters found in chapters.json")

    return chapters


# ======================================================
# BUILD BOOK TEXT
# ======================================================

def build_book_text(chapters):

    selected = chapters[:min(SUMMARY_CHAPTERS, len(chapters))]

    print(
        f"Using {len(selected)} chapter(s) for summary..."
    )

    text = ""

    for chapter in selected:

        title = chapter.get("title", "")

        body = chapter.get("text", "")

        text += f"\n\n{title}\n\n{body}"

    return text


# ======================================================
# PROMPT
# ======================================================

def build_prompt(book_text):

    return f"""
You are an expert Tamil literature editor.

Below are the first chapters of a Tamil novel.

Generate a spoiler-free back-cover style summary.

Rules:

- Write the summary in Tamil.
- Do NOT reveal the ending.
- Do NOT invent events.
- Only use the provided text.
- Mention the setting.
- Mention the main characters.
- Mention the central conflict.
- Mention the overall mood.
- Keep it engaging.

Return ONLY valid JSON.

JSON format:

{{
    "summary":"",
    "genre":"",
    "themes":[
        "",
        "",
        ""
    ],
    "recommended_age":""
}}

Book:

{book_text}
"""
# ======================================================
# GENERATE SUMMARY
# ======================================================

def generate_summary(book_text):

    prompt = build_prompt(book_text)

    print("Generating AI summary...")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    if not response.text:
        raise Exception("Gemini returned an empty response.")

    return response.text


# ======================================================
# CLEAN RESPONSE
# ======================================================

def clean_json(text):

    text = text.strip()

    if text.startswith("```json"):
        text = text.replace("```json", "", 1)

    if text.startswith("```"):
        text = text.replace("```", "", 1)

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# ======================================================
# PARSE JSON
# ======================================================

def parse_summary(response_text):

    cleaned = clean_json(response_text)

    try:
        summary = json.loads(cleaned)

    except json.JSONDecodeError as e:

        print("\nGemini Response:\n")
        print(cleaned)

        raise Exception(
            f"Invalid JSON returned by Gemini.\n{e}"
        )

    return summary


# ======================================================
# VALIDATE OUTPUT
# ======================================================

def validate_summary(summary):

    required_keys = [
        "summary",
        "genre",
        "themes",
        "recommended_age"
    ]

    for key in required_keys:

        if key not in summary:
            raise Exception(
                f"Missing key: {key}"
            )

    if not isinstance(summary["themes"], list):
        raise Exception(
            "'themes' must be a list."
        )

    return summary

# ======================================================
# SAVE SUMMARY
# ======================================================

def save_summary(summary):

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=4
        )

    print(f"\nSummary saved to:\n{OUTPUT_FILE}")


# ======================================================
# MAIN
# ======================================================

def main():

    print("=" * 50)
    print("Tamil Book AI Summary Generator")
    print("=" * 50)

    print("\nLoading chapters...")

    chapters = load_chapters()

    print(f"Found {len(chapters)} chapters.")

    book_text = build_book_text(chapters)

    print("\nSending first chapters to Gemini...")

    response = generate_summary(book_text)

    print("Processing response...")

    summary = parse_summary(response)

    summary = validate_summary(summary)

    save_summary(summary)

    print("\nDone!")
    print("=" * 50)


# ======================================================
# ENTRY POINT
# ======================================================

if __name__ == "__main__":

    try:
        main()

    except Exception as e:

        print("\nERROR")
        print("-" * 50)
        print(e)
        print("-" * 50)