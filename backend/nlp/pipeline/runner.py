"""
runner.py
=========
Orchestrates the full NLP pipeline for a Tamil EPUB:

    Step 1 — Extract  : Tamil text + cover image  → chapters.json, cover.jpg
    Step 2 — Summarise: Full-book + per-chapter   → book_summary.json
    Step 3 — Voiceover: Full chapter text → TTS   → audio/chapter_XX.mp3

Usage
-----
    # Run all three steps
    python runner.py --book books/deiva_yaanai.epub

    # Run only extraction (no AI, no audio)
    python runner.py --book books/deiva_yaanai.epub --steps extract

    # Run extraction + summarisation only
    python runner.py --book books/deiva_yaanai.epub --steps extract summarize

    # Override the book ID (output folder name)
    python runner.py --book books/deiva_yaanai.epub --id my_book
"""

import argparse
import os
import sys
import time

# Ensure pipeline package is importable whether run from nlp/ or its subdirs
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_NLP_DIR  = os.path.dirname(_THIS_DIR)
if _NLP_DIR not in sys.path:
    sys.path.insert(0, _NLP_DIR)

from pipeline.extractor       import extract_epub
from pipeline.summarizer      import summarize
from pipeline.voice_generator import generate_audio


# ─────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════╗
║   Tamil eBook Reader — NLP Pipeline              ║
║   Steps: Extract → Summarise → Voiceover         ║
╚══════════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(epub_path: str, book_id: str | None, steps: list[str]) -> dict:
    """
    Run the requested pipeline steps in order.

    Returns a summary dict with paths to all generated artefacts.
    """
    print(BANNER)
    t_start = time.time()

    result = {
        "epub_path":    epub_path,
        "book_id":      book_id,
        "out_dir":      None,
        "cover":        None,
        "chapters":     None,
        "summary":      None,
        "audio":        None,
        "errors":       [],
    }

    # ── Step 1: Extract ───────────────────────────────────────────────────
    if "extract" in steps:
        print("\n[STEP 1] Extracting Tamil text & cover image …")
        try:
            extraction = extract_epub(epub_path, book_id)
            result["book_id"]   = extraction["book_id"]
            result["out_dir"]   = extraction["out_dir"]
            result["cover"]     = extraction["cover"]
            result["chapters"]  = extraction["chapters_path"]
            book_id = extraction["book_id"]
            out_dir = extraction["out_dir"]
        except Exception as exc:
            msg = f"Extraction failed: {exc}"
            print(f"\n  [ERROR] {msg}")
            result["errors"].append(msg)
            return result           # Can't continue without chapters
    else:
        # If extract is skipped, we still need out_dir and chapters_path
        from pipeline.extractor import OUTPUT_ROOT
        out_dir = os.path.join(OUTPUT_ROOT, book_id)
        chapters_path = os.path.join(out_dir, "chapters.json")
        result["out_dir"]  = out_dir
        result["chapters"] = chapters_path
        if not os.path.isfile(chapters_path):
            msg = (
                f"chapters.json not found at {chapters_path}. "
                "Run with --steps extract first."
            )
            print(f"\n  [ERROR] {msg}")
            result["errors"].append(msg)
            return result

    # ── Step 2: Summarise ─────────────────────────────────────────────────
    if "summarize" in steps:
        print("\n[STEP 2] Generating Tamil summaries via Gemini …")
        try:
            summary_path    = summarize(result["chapters"], result["out_dir"])
            result["summary"] = summary_path
        except Exception as exc:
            msg = f"Summarisation failed: {exc}"
            print(f"\n  [ERROR] {msg}")
            result["errors"].append(msg)
            # Non-fatal — continue to audio if requested

    # ── Step 3: Voiceover ─────────────────────────────────────────────────
    if "audio" in steps:
        print("\n[STEP 3] Generating Tamil voiceovers (full chapter text) …")
        try:
            manifest_path  = generate_audio(result["chapters"], result["out_dir"])
            result["audio"] = manifest_path
        except Exception as exc:
            msg = f"Audio generation failed: {exc}"
            print(f"\n  [ERROR] {msg}")
            result["errors"].append(msg)

    # ── Done ──────────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{'='*55}")
    print(f"  Pipeline complete in {elapsed:.1f}s")
    print(f"  Book ID  : {result['book_id']}")
    print(f"  Output   : {result['out_dir']}")
    if result["cover"]:
        print(f"  Cover    : {result['cover']}")
    if result["chapters"]:
        print(f"  Chapters : {result['chapters']}")
    if result["summary"]:
        print(f"  Summary  : {result['summary']}")
    if result["audio"]:
        print(f"  Audio    : {result['audio']}")
    if result["errors"]:
        print(f"\n  Errors   : {len(result['errors'])}")
        for err in result["errors"]:
            print(f"    - {err}")
    print(f"{'='*55}\n")

    return result


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Tamil eBook Reader — NLP Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python runner.py --book books/deiva_yaanai.epub
  python runner.py --book books/deiva_yaanai.epub --steps extract
  python runner.py --book books/deiva_yaanai.epub --steps extract summarize
  python runner.py --book books/deiva_yaanai.epub --id my_book
        """,
    )
    parser.add_argument(
        "--book",
        required=True,
        help="Path to the .epub file to process",
    )
    parser.add_argument(
        "--id",
        dest="book_id",
        default=None,
        help="Book ID / output folder name (default: epub filename stem)",
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        default=["extract", "summarize", "audio"],
        choices=["extract", "summarize", "audio"],
        help="Pipeline steps to run (default: all three)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    epub_path = os.path.abspath(args.book)
    if not os.path.isfile(epub_path):
        print(f"ERROR: File not found: {epub_path}")
        sys.exit(1)

    result = run_pipeline(
        epub_path=epub_path,
        book_id=args.book_id,
        steps=args.steps,
    )

    if result["errors"]:
        sys.exit(1)
