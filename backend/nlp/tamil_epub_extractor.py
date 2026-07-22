import json
import os
from google import genai

# ==========================================
# CONFIGURATION
# ==========================================

BOOK_NAME = "deiva_yaanai"

INPUT_FILE = os.path.join(
    "output",
    BOOK_NAME,
    "chapters.json"
)

OUTPUT_FILE = os.path.join(
    "output",
    BOOK_NAME,
    "book_summary.json"
)

MODEL = "gemini-2.5-flash-lite"

# Gemini automatically reads GEMINI_API_KEY
client = genai.Client()


# ==========================================
# LOAD CHAPTERS
# ==========================================

def load_book_text():

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = data["chapters"]

    full_text = ""

    for chapter in chapters:

        full_text += (
            f"\n\n{chapter['title']}\n"
            f"{chapter['text']}"
        )

    return full_text


# ==========================================
# GENERATE SUMMARY
# ==========================================

def generate_summary(book_text):

    # Limit input to avoid exceeding token limits.
    # This can be increased later if needed.
    book_text = book_text[:60000]

    prompt = f"""
You are a Tamil literature assistant.

Read the following Tamil book and generate a spoiler-free summary.

Return ONLY valid JSON.

Format:

{{
  "summary":"...",
  "genre":"...",
  "themes":[
      "...",
      "...",
      "..."
  ],
  "recommended_age":"..."
}}

Rules:

- Write the summary in Tamil.
- Do NOT reveal the ending.
- Mention the main theme.
- Mention the important characters.
- Mention why someone should read the book.
- Genre should be in English.
- Themes should be in English.

BOOK:

{book_text}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text


# ==========================================
# SAVE
# ==========================================

def save_summary(summary_text):

    # Gemini may wrap JSON in ```json ... ```
    cleaned = (
        summary_text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    data = json.loads(cleaned)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4,
        )


# ==========================================
# MAIN
# ==========================================

def main():

    if not os.path.exists(INPUT_FILE):

        print("chapters.json not found.")
        return

    print("Loading chapters...")

    text = load_book_text()

    print("Generating AI summary...")

    summary = generate_summary(text)

    print("Saving...")

    save_summary(summary)

    print("\n====================================")
    print("Book summary generated successfully!")
    print(f"Saved to: {OUTPUT_FILE}")
    print("====================================")


if __name__ == "__main__":
    main()