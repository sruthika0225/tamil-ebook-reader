"""
extractor.py
============
Extracts Tamil text (chapter-by-chapter) and the cover image from an EPUB file.

Output layout (written to output/<book_id>/):
    chapters.json   — structured chapter list with Tamil text
    cover.jpg       — cover image (JPEG or PNG, saved as .jpg)
    metadata.json   — book-level metadata
"""

import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE
from bs4 import BeautifulSoup
from PIL import Image
import io


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

OUTPUT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "output"
)

TAMIL_UNICODE_RANGE = ("\u0B80", "\u0BFF")   # Tamil Unicode block

# Tags whose text counts as a chapter separator / heading
HEADING_TAGS = {"h1", "h2", "h3", "h4"}

# Minimum Tamil characters a segment must have to be considered a real chapter
MIN_TAMIL_CHARS = 100


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _is_tamil_char(ch: str) -> bool:
    """Return True if the character is in the Tamil Unicode block."""
    return "\u0B80" <= ch <= "\u0BFF"


def _tamil_char_count(text: str) -> int:
    """Count how many Tamil script characters are in a string."""
    return sum(1 for ch in text if _is_tamil_char(ch))


def _clean_text(text: str) -> str:
    """
    Normalise whitespace and remove junk characters from extracted text.
    Preserves Tamil characters and common punctuation.
    """
    # Unicode NFC normalisation
    text = unicodedata.normalize("NFC", text)
    # Collapse runs of whitespace / newlines to a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse multiple blank lines to at most two newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _soup_to_text(soup: BeautifulSoup) -> str:
    """Convert a BeautifulSoup document to clean plain text."""
    # Remove script / style noise
    for tag in soup(["script", "style"]):
        tag.decompose()
    return _clean_text(soup.get_text(separator="\n"))


def _extract_metadata(book: epub.EpubBook, book_id: str) -> dict:
    """Pull standard Dublin-Core metadata from an EpubBook object."""
    def _first(items):
        return items[0][0] if items else "Unknown"

    title     = _first(book.get_metadata("DC", "title"))
    author    = _first(book.get_metadata("DC", "creator"))
    publisher = _first(book.get_metadata("DC", "publisher"))
    language  = _first(book.get_metadata("DC", "language"))

    return {
        "id":        book_id,
        "title":     title,
        "author":    author,
        "publisher": publisher,
        "language":  language,
    }


# ─────────────────────────────────────────────
# COVER EXTRACTION
# ─────────────────────────────────────────────

def _extract_cover(book: epub.EpubBook, out_dir: str) -> str | None:
    """
    Find and save the cover image from the EPUB.

    Strategy (in priority order):
      1. Item whose media-type is 'cover-image' or whose ID is 'cover'
      2. First <img> in the first spine document that looks like a cover page
      3. First image item in the manifest

    Returns the filename ('cover.jpg') if found, else None.
    """
    cover_item = None

    # Strategy 1 — look by item ID / properties
    for item in book.get_items_of_type(ITEM_IMAGE):
        item_id   = (item.get_id() or "").lower()
        item_name = (item.get_name() or "").lower()
        props     = getattr(item, "properties", "") or ""
        if (
            "cover" in item_id
            or "cover" in item_name
            or "cover-image" in props
        ):
            cover_item = item
            break

    # Strategy 2 — first HTML document that contains a single large image
    if cover_item is None:
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            soup   = BeautifulSoup(item.get_content(), "html.parser")
            images = soup.find_all("img")
            text   = _clean_text(soup.get_text())
            if images and _tamil_char_count(text) < 20:
                # Looks like a cover page (mostly image, very little text)
                src = images[0].get("src", "")
                # Resolve relative src to an epub item
                for img_item in book.get_items_of_type(ITEM_IMAGE):
                    if img_item.get_name().endswith(src.split("/")[-1]):
                        cover_item = img_item
                        break
                if cover_item:
                    break

    # Strategy 3 — just take the first image in the manifest
    if cover_item is None:
        for item in book.get_items_of_type(ITEM_IMAGE):
            cover_item = item
            break

    if cover_item is None:
        print("  [WARN] No cover image found in this EPUB.")
        return None

    # Save the cover image, converting to JPEG if necessary
    cover_path = os.path.join(out_dir, "cover.jpg")
    try:
        img = Image.open(io.BytesIO(cover_item.get_content()))
        # Convert palette / RGBA images to RGB before saving as JPEG
        if img.mode in ("P", "RGBA", "LA"):
            img = img.convert("RGB")
        img.save(cover_path, "JPEG", quality=92)
        print(f"  [OK]   Cover image saved → cover.jpg")
        return "cover.jpg"
    except Exception as exc:
        print(f"  [WARN] Could not save cover image: {exc}")
        return None


# ─────────────────────────────────────────────
# CHAPTER EXTRACTION
# ─────────────────────────────────────────────

def _parse_chapters(book: epub.EpubBook) -> list[dict]:
    """
    Walk the EPUB spine in order and build a list of chapters.

    Each chapter is a dict:
        {
            "index":  <int>,
            "title":  <str>,   # chapter heading or fallback name
            "text":   <str>,   # full Tamil text
        }

    Rules:
    - Each spine document becomes at most one chapter.
    - If a document has a heading tag the heading text becomes the title.
    - Documents with fewer than MIN_TAMIL_CHARS Tamil characters are skipped
      (front-matter, TOC, colophon, etc.).
    - If consecutive spine items have no heading, they are merged if either
      alone is below MIN_TAMIL_CHARS (handles books split weirdly).
    """
    raw_segments: list[dict] = []

    for item_ref in book.spine:
        item_id = item_ref[0] if isinstance(item_ref, tuple) else item_ref
        item    = book.get_item_with_id(item_id)
        if item is None or item.get_type() != 9:   # 9 == ITEM_DOCUMENT
            continue

        try:
            soup = BeautifulSoup(item.get_content(), "html.parser")
        except Exception:
            continue

        # Find a chapter title from the first heading
        heading_tag = soup.find(HEADING_TAGS)
        title = _clean_text(heading_tag.get_text()) if heading_tag else ""

        # Remove the heading from the soup so we don't duplicate it in text
        if heading_tag:
            heading_tag.decompose()

        body_text = _soup_to_text(soup)

        raw_segments.append({
            "title": title,
            "text":  body_text,
        })

    # ── Filter + index ────────────────────────────────────────────────────
    chapters  = []
    chapter_n = 0
    pending   = None       # segment waiting to be merged

    for seg in raw_segments:
        tamil_count = _tamil_char_count(seg["text"])

        if tamil_count < MIN_TAMIL_CHARS:
            # Skip near-empty segments (TOC, cover page, etc.)
            continue

        if pending is not None:
            # Merge previous pending segment into current one
            if not seg["title"]:
                seg["title"] = pending["title"]
            seg["text"] = pending["text"] + "\n\n" + seg["text"]
            pending = None

        chapter_n += 1
        title = seg["title"] or f"அத்தியாயம் {chapter_n}"

        chapters.append({
            "index": chapter_n,
            "title": title,
            "text":  seg["text"],
        })

    return chapters


# ─────────────────────────────────────────────
# READING TIME ESTIMATE
# ─────────────────────────────────────────────

def _reading_time(chapters: list[dict]) -> str:
    """Estimate total reading time at ~120 Tamil words per minute."""
    total_words = sum(len(ch["text"].split()) for ch in chapters)
    minutes     = total_words // 120
    hours       = minutes // 60
    mins        = minutes % 60
    if hours > 0:
        return f"{hours} hr {mins} min"
    return f"{mins} min"


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def extract_epub(epub_path: str, book_id: str | None = None) -> dict:
    """
    Full extraction pipeline for one EPUB file.

    Parameters
    ----------
    epub_path : str
        Absolute or relative path to the .epub file.
    book_id : str, optional
        Slug used as the output folder name. Defaults to the file stem.

    Returns
    -------
    dict
        {
            "book_id":       str,
            "out_dir":       str,
            "metadata":      dict,
            "cover":         str | None,
            "chapter_count": int,
            "chapters_path": str,
        }
    """
    epub_path = os.path.abspath(epub_path)
    if not os.path.isfile(epub_path):
        raise FileNotFoundError(f"EPUB not found: {epub_path}")

    if book_id is None:
        book_id = Path(epub_path).stem

    out_dir = os.path.join(OUTPUT_ROOT, book_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  Extracting: {os.path.basename(epub_path)}")
    print(f"  Output dir: {out_dir}")
    print(f"{'='*55}")

    # ── Open EPUB ─────────────────────────────────────────────────────────
    book = epub.read_epub(epub_path)

    # ── Metadata ──────────────────────────────────────────────────────────
    metadata = _extract_metadata(book, book_id)
    print(f"  Title  : {metadata['title']}")
    print(f"  Author : {metadata['author']}")

    # ── Cover Image ───────────────────────────────────────────────────────
    cover_filename = _extract_cover(book, out_dir)

    # ── Chapters ──────────────────────────────────────────────────────────
    print("  Parsing chapters …")
    chapters = _parse_chapters(book)
    print(f"  [OK]   {len(chapters)} chapter(s) extracted.")

    if not chapters:
        raise RuntimeError(
            "No Tamil chapters found in this EPUB. "
            "The book may not contain Tamil text, or the encoding may be unusual."
        )

    # ── Compute reading time & update metadata ────────────────────────────
    metadata["chapter_count"] = len(chapters)
    metadata["reading_time"]  = _reading_time(chapters)
    metadata["cover"]         = cover_filename

    # ── Save chapters.json ────────────────────────────────────────────────
    chapters_path = os.path.join(out_dir, "chapters.json")
    with open(chapters_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metadata": metadata, "chapters": chapters},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  [OK]   chapters.json saved ({len(chapters)} chapters).")

    # ── Save metadata.json ────────────────────────────────────────────────
    metadata_path = os.path.join(out_dir, "metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    print(f"  [OK]   metadata.json saved.")

    return {
        "book_id":       book_id,
        "out_dir":       out_dir,
        "metadata":      metadata,
        "cover":         cover_filename,
        "chapter_count": len(chapters),
        "chapters_path": chapters_path,
    }
