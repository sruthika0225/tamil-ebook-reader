"""
summarizer.py
=============
Generates Tamil-language summaries using Google Gemini:

  1. Full book summary  → spoiler-free "back-cover blurb" in Tamil
  2. Per-chapter summaries → 3–5 sentence Tamil summary per chapter
                             (useful for chapter-preview / Kindle X-Ray style feature)

Both are written into book_summary.json inside the book's output folder.
"""

import json
import os
import time
import re

from google import genai


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

MODEL = "gemini-2.5-flash-lite"

# How many chapters to feed Gemini for the full-book summary
# (keeps the prompt within token budget for large books)
BOOK_SUMMARY_MAX_CHAPTERS = 12

# Character limit per chapter sent to Gemini for the full-book summary
BOOK_SUMMARY_CHAR_LIMIT = 5000

# Character limit per chapter for per-chapter summarisation
CHAPTER_SUMMARY_CHAR_LIMIT = 8000

# Seconds to wait between Gemini calls (rate-limit courtesy)
GEMINI_DELAY = 1.0


# ─────────────────────────────────────────────
# GEMINI CLIENT (lazy — created on first use)
# ─────────────────────────────────────────────

_client = None

def _get_client():
    """Return a cached Gemini client, reading GEMINI_API_KEY from env."""
    global _client
    if _client is None:
        _client = genai.Client()   # reads GEMINI_API_KEY automatically
    return _client


# ─────────────────────────────────────────────
# JSON CLEANING HELPERS
# ─────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json … ``` wrappers that Gemini sometimes adds."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*",     "", text)
    text = re.sub(r"\s*```$",     "", text)
    return text.strip()


def _safe_parse_json(raw: str) -> dict:
    """Parse JSON returned by Gemini, raising a clear error on failure."""
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned invalid JSON.\n"
            f"Raw response (first 500 chars):\n{raw[:500]}\n"
            f"Error: {exc}"
        )


# ─────────────────────────────────────────────
# FULL-BOOK SUMMARY
# ─────────────────────────────────────────────

def _build_book_summary_prompt(chapters: list[dict]) -> str:
    """Build the Gemini prompt for the full-book Tamil summary."""
    # Use the first N chapters, each trimmed to the char limit
    selected = chapters[:BOOK_SUMMARY_MAX_CHAPTERS]

    book_text = ""
    for ch in selected:
        title = ch.get("title", "")
        text  = ch.get("text",  "")[:BOOK_SUMMARY_CHAR_LIMIT]
        book_text += f"\n\n{title}\n{text}"

    return f"""
நீங்கள் ஒரு தமிழ் இலக்கிய நிபுணர்.

கீழே ஒரு தமிழ் நாவலின் முதல் அத்தியாயங்கள் கொடுக்கப்பட்டுள்ளன.

இந்த புத்தகத்திற்கு ஒரு சிறந்த பின்புற அட்டை விளக்கம் (back-cover blurb) எழுதுங்கள்.

விதிகள்:
- சுருக்கம் தமிழில் மட்டுமே இருக்க வேண்டும்.
- கதையின் முடிவை வெளிப்படுத்தாதீர்கள்.
- கதையின் சூழல், முக்கிய கதாபாத்திரங்கள், மையக் கருவை குறிப்பிடுங்கள்.
- வாசகரை ஈர்க்கும் வகையில் எழுதுங்கள்.
- genre மற்றும் themes ஆங்கிலத்தில் இருக்கலாம்.

திரும்பி அனுப்புவது கட்டாயமாக valid JSON மட்டுமே:

{{
    "summary": "<தமிழ் சுருக்கம்>",
    "genre": "<English genre>",
    "themes": ["<theme1>", "<theme2>", "<theme3>"],
    "recommended_age": "<age range>"
}}

புத்தகம்:

{book_text}
"""


def generate_book_summary(chapters: list[dict]) -> dict:
    """
    Call Gemini to produce a full-book Tamil summary.

    Returns a dict with keys: summary, genre, themes, recommended_age
    """
    print("  Generating full-book summary …")
    prompt   = _build_book_summary_prompt(chapters)
    response = _get_client().models.generate_content(model=MODEL, contents=prompt)
    result   = _safe_parse_json(response.text)

    # Validate required keys
    for key in ("summary", "genre", "themes", "recommended_age"):
        if key not in result:
            raise ValueError(f"Missing key '{key}' in Gemini book-summary response.")

    print("  [OK]   Full-book summary generated.")
    return result


# ─────────────────────────────────────────────
# PER-CHAPTER SUMMARIES
# ─────────────────────────────────────────────

def _build_chapter_summary_prompt(chapter: dict) -> str:
    """Build the Gemini prompt for a single chapter's Tamil summary."""
    title = chapter.get("title", "")
    text  = chapter.get("text",  "")[:CHAPTER_SUMMARY_CHAR_LIMIT]

    return f"""
நீங்கள் ஒரு தமிழ் இலக்கிய நிபுணர்.

கீழே ஒரு தமிழ் நாவலின் ஒரு அத்தியாயம் கொடுக்கப்பட்டுள்ளது.

இந்த அத்தியாயத்திற்கு 3 முதல் 5 வாக்கியங்களில் ஒரு சுருக்கம் எழுதுங்கள்.

விதிகள்:
- சுருக்கம் தமிழில் மட்டுமே இருக்க வேண்டும்.
- இந்த அத்தியாயத்தில் நடப்பதை மட்டுமே குறிப்பிடுங்கள்.
- கதையின் மொத்த முடிவை வெளிப்படுத்தாதீர்கள்.

திரும்பி அனுப்புவது கட்டாயமாக valid JSON மட்டுமே:

{{
    "summary": "<தமிழ் சுருக்கம்>"
}}

அத்தியாயம் தலைப்பு: {title}

அத்தியாய உரை:
{text}
"""


def generate_chapter_summaries(chapters: list[dict]) -> list[dict]:
    """
    Call Gemini once per chapter to produce a Tamil per-chapter summary.

    Returns a list of dicts:
        [{"index": 1, "title": "...", "summary": "..."}, ...]
    """
    print(f"  Generating per-chapter summaries for {len(chapters)} chapter(s) …")
    results = []

    for ch in chapters:
        idx   = ch.get("index", len(results) + 1)
        title = ch.get("title", f"அத்தியாயம் {idx}")

        print(f"    Chapter {idx}: {title[:40]} …")
        try:
            prompt   = _build_chapter_summary_prompt(ch)
            response = _get_client().models.generate_content(model=MODEL, contents=prompt)
            parsed   = _safe_parse_json(response.text)
            summary  = parsed.get("summary", "")
        except Exception as exc:
            print(f"    [WARN] Chapter {idx} summary failed: {exc}")
            summary = ""

        results.append({
            "index":   idx,
            "title":   title,
            "summary": summary,
        })

        # Be gentle with the API
        time.sleep(GEMINI_DELAY)

    print(f"  [OK]   {len(results)} chapter summaries generated.")
    return results


# ─────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────

def save_summaries(
    out_dir: str,
    book_summary: dict,
    chapter_summaries: list[dict],
) -> str:
    """
    Write book_summary.json to out_dir.

    Returns the path of the saved file.
    """
    data = {
        **book_summary,
        "chapter_summaries": chapter_summaries,
    }

    path = os.path.join(out_dir, "book_summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  [OK]   book_summary.json saved → {path}")
    return path


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def summarize(chapters_path: str, out_dir: str) -> str:
    """
    Load chapters.json, generate full-book + per-chapter Tamil summaries,
    and save book_summary.json.

    Parameters
    ----------
    chapters_path : str   Path to chapters.json
    out_dir       : str   Directory to write book_summary.json

    Returns
    -------
    str   Path to the saved book_summary.json
    """
    with open(chapters_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = data.get("chapters", [])
    if not chapters:
        raise ValueError(f"No chapters found in {chapters_path}")

    print(f"\n  Loaded {len(chapters)} chapters for summarisation.")

    book_summary      = generate_book_summary(chapters)
    chapter_summaries = generate_chapter_summaries(chapters)

    return save_summaries(out_dir, book_summary, chapter_summaries)
