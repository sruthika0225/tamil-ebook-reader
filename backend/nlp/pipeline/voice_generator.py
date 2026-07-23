"""
voice_generator.py
==================
Generates Tamil voiceover MP3 files from the FULL chapter text (not summaries).

For each chapter the full text is read aloud using gTTS (Google Text-to-Speech)
with language set to Tamil ("ta").

Because gTTS has a practical limit of ~5 000 characters per request, long chapters
are automatically split into overlapping chunks that are concatenated into a single
MP3 using pydub (if installed) or saved as sequential numbered files otherwise.

Output:
    output/<book_id>/audio/chapter_01.mp3
    output/<book_id>/audio/chapter_02.mp3
    ...
    output/<book_id>/audio/audio_manifest.json
"""

import json
import os
import time
from io import BytesIO
from pathlib import Path

from gtts import gTTS


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# gTTS soft character limit per request
GTTS_CHUNK_SIZE = 4500

# Pause between gTTS API calls (seconds) to avoid rate-limiting
GTTS_DELAY = 1.5

# Language code for Tamil TTS
TTS_LANG = "ta"


# ─────────────────────────────────────────────
# TEXT CHUNKING
# ─────────────────────────────────────────────

def _split_into_chunks(text: str, chunk_size: int = GTTS_CHUNK_SIZE) -> list[str]:
    """
    Split text into chunks of at most `chunk_size` characters.

    Splits are made at sentence boundaries (। or .) where possible so that
    gTTS does not cut off mid-sentence.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks    = []
    remaining = text

    while len(remaining) > chunk_size:
        # Try to split at a sentence ending within the window
        window = remaining[:chunk_size]
        # Search for Tamil sentence-end characters or common punctuation
        split_pos = max(
            window.rfind("।"),
            window.rfind("."),
            window.rfind("?"),
            window.rfind("!"),
            window.rfind("\n"),
        )
        if split_pos < chunk_size // 2:
            # No good break found — hard split at chunk_size
            split_pos = chunk_size - 1

        chunks.append(remaining[: split_pos + 1].strip())
        remaining = remaining[split_pos + 1 :].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


# ─────────────────────────────────────────────
# SINGLE CHAPTER AUDIO
# ─────────────────────────────────────────────

def _generate_chapter_audio(
    chapter: dict,
    audio_dir: str,
) -> dict:
    """
    Generate MP3 audio for one chapter from its FULL text.

    If the chapter text fits within GTTS_CHUNK_SIZE it is sent as one request.
    Otherwise the text is split into chunks; each chunk is synthesised separately
    and the resulting audio bytes are concatenated (raw MP3 concatenation —
    works well enough for sequential playback without pydub dependency).

    Returns a manifest entry dict.
    """
    idx   = chapter.get("index", 0)
    title = chapter.get("title", f"அத்தியாயம் {idx}")
    text  = chapter.get("text",  "").strip()

    filename   = f"chapter_{idx:02d}.mp3"
    audio_path = os.path.join(audio_dir, filename)

    if not text:
        print(f"    [SKIP] Chapter {idx}: no text, skipping.")
        return {"index": idx, "title": title, "file": None, "status": "skipped"}

    chunks = _split_into_chunks(text)
    print(f"    Chapter {idx:02d}: {title[:40]} — {len(chunks)} chunk(s)")

    # Collect raw MP3 bytes from each chunk
    audio_bytes_list = []
    for chunk_idx, chunk in enumerate(chunks, start=1):
        try:
            tts = gTTS(text=chunk, lang=TTS_LANG, slow=False)
            buf = BytesIO()
            tts.write_to_fp(buf)
            audio_bytes_list.append(buf.getvalue())
            if len(chunks) > 1:
                print(f"      Chunk {chunk_idx}/{len(chunks)} done")
            time.sleep(GTTS_DELAY)
        except Exception as exc:
            print(f"    [WARN] Chapter {idx} chunk {chunk_idx} failed: {exc}")

    if not audio_bytes_list:
        print(f"    [FAIL] Chapter {idx}: all chunks failed.")
        return {"index": idx, "title": title, "file": None, "status": "failed"}

    # Concatenate raw MP3 bytes and write to file
    # (MP3 frames from gTTS are individually self-contained — concatenation works)
    with open(audio_path, "wb") as f:
        for audio_bytes in audio_bytes_list:
            f.write(audio_bytes)

    size_kb = os.path.getsize(audio_path) // 1024
    print(f"    [OK]  chapter_{idx:02d}.mp3 saved ({size_kb} KB)")

    return {
        "index":  idx,
        "title":  title,
        "file":   filename,
        "status": "ok",
        "size_kb": size_kb,
    }


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def generate_audio(chapters_path: str, out_dir: str) -> str:
    """
    Generate Tamil voiceover MP3s for every chapter from FULL chapter text.

    Parameters
    ----------
    chapters_path : str   Path to chapters.json
    out_dir       : str   Book output directory (audio/ will be created inside)

    Returns
    -------
    str   Path to audio_manifest.json
    """
    with open(chapters_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chapters = data.get("chapters", [])
    if not chapters:
        raise ValueError(f"No chapters found in {chapters_path}")

    audio_dir = os.path.join(out_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    print(f"\n  Generating audio for {len(chapters)} chapter(s) …")
    print(f"  Audio mode: FULL CHAPTER TEXT")
    print(f"  Language  : Tamil (ta)")

    manifest_entries = []
    success_count    = 0

    for chapter in chapters:
        entry = _generate_chapter_audio(chapter, audio_dir)
        manifest_entries.append(entry)
        if entry["status"] == "ok":
            success_count += 1

    # Save manifest
    manifest = {
        "total_chapters": len(chapters),
        "generated":      success_count,
        "audio_dir":      audio_dir,
        "entries":        manifest_entries,
    }

    manifest_path = os.path.join(audio_dir, "audio_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n  [OK]  {success_count}/{len(chapters)} audio files created.")
    print(f"  [OK]  audio_manifest.json saved.")

    return manifest_path
