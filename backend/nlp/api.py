"""
api.py
======
Flask REST API for the Tamil eBook Reader backend.

Exposes the NLP pipeline over HTTP so the Flutter app can:
  - Upload an EPUB
  - Track processing status
  - Fetch book metadata, chapters, summaries, audio, and cover

Run:
    python api.py
    python api.py --port 8080

Endpoints
---------
POST   /api/upload                          Upload & process an EPUB
GET    /api/books                           List all processed books
GET    /api/books/<book_id>                 Book metadata + summary
GET    /api/books/<book_id>/status          Processing status
GET    /api/books/<book_id>/chapters        All chapters (text + per-chapter summary)
GET    /api/books/<book_id>/chapters/<n>    Single chapter (1-indexed)
GET    /api/books/<book_id>/audio/<n>       Stream chapter MP3 (1-indexed)
GET    /api/books/<book_id>/cover           Cover image
"""

import json
import os
import sys
import threading
import uuid
from pathlib import Path
from functools import wraps

from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS

# ── make pipeline importable ──────────────────────────────────────────────
_API_DIR  = os.path.dirname(os.path.abspath(__file__))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from pipeline.extractor       import extract_epub, OUTPUT_ROOT
from pipeline.summarizer      import summarize
from pipeline.voice_generator import generate_audio


# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = Flask(__name__)
CORS(app)   # Allow Flutter web / localhost requests

UPLOAD_FOLDER = os.path.join(_API_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"epub"}

# In-memory job tracker  { book_id: { status, steps_done, error } }
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _book_out_dir(book_id: str) -> str:
    return os.path.join(OUTPUT_ROOT, book_id)


def _book_exists(book_id: str) -> bool:
    return os.path.isfile(
        os.path.join(_book_out_dir(book_id), "chapters.json")
    )


def _load_json(path: str) -> dict | list | None:
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _error(message: str, code: int = 400):
    return jsonify({"error": message}), code


def _require_book(f):
    """Decorator: return 404 if book_id doesn't exist yet."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        book_id = kwargs.get("book_id")
        if book_id and not _book_exists(book_id):
            return _error(f"Book '{book_id}' not found.", 404)
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# BACKGROUND PIPELINE JOB
# ─────────────────────────────────────────────

def _run_pipeline_async(epub_path: str, book_id: str):
    """
    Run the full pipeline (extract → summarize → audio) in a background thread.
    Updates _jobs[book_id] with progress.
    """
    def _update(status: str, step: str = ""):
        with _jobs_lock:
            _jobs[book_id]["status"]    = status
            _jobs[book_id]["step"]      = step

    try:
        _update("processing", "extract")
        extraction = extract_epub(epub_path, book_id)
        out_dir    = extraction["out_dir"]
        chapters   = extraction["chapters_path"]

        _update("processing", "summarize")
        summarize(chapters, out_dir)

        _update("processing", "audio")
        generate_audio(chapters, out_dir)

        _update("done", "complete")

    except Exception as exc:
        with _jobs_lock:
            _jobs[book_id]["status"] = "error"
            _jobs[book_id]["error"]  = str(exc)
        print(f"[ERROR] Pipeline failed for {book_id}: {exc}")


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

# ── Health ────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "Tamil eBook Reader NLP API"})


# ── Upload & process ──────────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def upload_book():
    """
    POST /api/upload
    Form-data: file=<epub file>, book_id=<optional slug>

    Starts the pipeline asynchronously.
    Returns: { book_id, status }
    """
    if "file" not in request.files:
        return _error("No file part in request.")

    file = request.files["file"]
    if file.filename == "":
        return _error("No file selected.")
    if not _allowed_file(file.filename):
        return _error("Only .epub files are supported.")

    # Use provided book_id or derive from filename
    book_id = (
        request.form.get("book_id")
        or Path(file.filename).stem.lower().replace(" ", "_")
    )

    # Save the uploaded file
    epub_path = os.path.join(UPLOAD_FOLDER, f"{book_id}.epub")
    file.save(epub_path)

    # Register job
    with _jobs_lock:
        _jobs[book_id] = {
            "status": "queued",
            "step":   "",
            "error":  None,
        }

    # Start pipeline in background thread
    thread = threading.Thread(
        target=_run_pipeline_async,
        args=(epub_path, book_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "book_id": book_id,
        "status":  "queued",
        "message": "Book uploaded. Processing started.",
    }), 202


# ── List books ────────────────────────────────────────────────────────────

@app.route("/api/books", methods=["GET"])
def list_books():
    """
    GET /api/books
    Returns a list of all books that have been processed (have chapters.json).
    """
    books = []
    if os.path.isdir(OUTPUT_ROOT):
        for entry in os.scandir(OUTPUT_ROOT):
            if entry.is_dir():
                meta_path = os.path.join(entry.path, "metadata.json")
                if os.path.isfile(meta_path):
                    meta = _load_json(meta_path) or {}
                    # Attach job status if available
                    with _jobs_lock:
                        job = _jobs.get(entry.name, {})
                    meta["processing_status"] = job.get("status", "done")
                    books.append(meta)

    return jsonify({"books": books, "total": len(books)})


# ── Book metadata + summary ───────────────────────────────────────────────

@app.route("/api/books/<book_id>", methods=["GET"])
@_require_book
def get_book(book_id: str):
    """
    GET /api/books/<book_id>
    Returns metadata.json merged with book_summary.json (if available).
    """
    out_dir = _book_out_dir(book_id)

    metadata = _load_json(os.path.join(out_dir, "metadata.json")) or {}
    summary  = _load_json(os.path.join(out_dir, "book_summary.json")) or {}

    # Merge, but keep chapter_summaries separate (it's big)
    chapter_summaries = summary.pop("chapter_summaries", [])

    return jsonify({
        **metadata,
        **summary,
        "chapter_summary_count": len(chapter_summaries),
    })


# ── Processing status ─────────────────────────────────────────────────────

@app.route("/api/books/<book_id>/status", methods=["GET"])
def get_status(book_id: str):
    """
    GET /api/books/<book_id>/status
    Returns the current processing status for this book.
    """
    with _jobs_lock:
        job = _jobs.get(book_id)

    if job is None:
        # Book exists but was processed before this server started
        if _book_exists(book_id):
            return jsonify({"book_id": book_id, "status": "done", "step": "complete"})
        return _error(f"Book '{book_id}' not found.", 404)

    return jsonify({"book_id": book_id, **job})


# ── Chapters ──────────────────────────────────────────────────────────────

@app.route("/api/books/<book_id>/chapters", methods=["GET"])
@_require_book
def get_chapters(book_id: str):
    """
    GET /api/books/<book_id>/chapters
    Returns all chapters with text + per-chapter summaries merged in.

    Query params:
      ?text=false   — omit full text (returns titles + summaries only)
    """
    out_dir       = _book_out_dir(book_id)
    include_text  = request.args.get("text", "true").lower() != "false"

    chapters_data = _load_json(os.path.join(out_dir, "chapters.json")) or {}
    chapters      = chapters_data.get("chapters", [])

    # Load per-chapter summaries
    summary_data      = _load_json(os.path.join(out_dir, "book_summary.json")) or {}
    chapter_summaries = {
        s["index"]: s.get("summary", "")
        for s in summary_data.get("chapter_summaries", [])
    }

    # Merge summaries into chapter list
    result_chapters = []
    for ch in chapters:
        entry = {
            "index":   ch["index"],
            "title":   ch["title"],
            "summary": chapter_summaries.get(ch["index"], ""),
        }
        if include_text:
            entry["text"] = ch["text"]
        result_chapters.append(entry)

    return jsonify({
        "book_id":  book_id,
        "total":    len(result_chapters),
        "chapters": result_chapters,
    })


@app.route("/api/books/<book_id>/chapters/<int:n>", methods=["GET"])
@_require_book
def get_chapter(book_id: str, n: int):
    """
    GET /api/books/<book_id>/chapters/<n>
    Returns a single chapter by index (1-based).
    Includes full text + per-chapter summary.
    """
    out_dir       = _book_out_dir(book_id)
    chapters_data = _load_json(os.path.join(out_dir, "chapters.json")) or {}
    chapters      = chapters_data.get("chapters", [])

    chapter = next((ch for ch in chapters if ch["index"] == n), None)
    if chapter is None:
        return _error(f"Chapter {n} not found.", 404)

    # Attach summary if available
    summary_data = _load_json(os.path.join(out_dir, "book_summary.json")) or {}
    summaries    = {
        s["index"]: s.get("summary", "")
        for s in summary_data.get("chapter_summaries", [])
    }
    chapter["summary"] = summaries.get(n, "")

    return jsonify(chapter)


# ── Audio ─────────────────────────────────────────────────────────────────

@app.route("/api/books/<book_id>/audio/<int:n>", methods=["GET"])
@_require_book
def get_audio(book_id: str, n: int):
    """
    GET /api/books/<book_id>/audio/<n>
    Streams the MP3 file for chapter n (1-based).
    """
    audio_path = os.path.join(
        _book_out_dir(book_id),
        "audio",
        f"chapter_{n:02d}.mp3",
    )
    if not os.path.isfile(audio_path):
        return _error(
            f"Audio for chapter {n} not found. "
            "Processing may still be in progress.", 404
        )
    return send_file(audio_path, mimetype="audio/mpeg")


# ── Cover image ───────────────────────────────────────────────────────────

@app.route("/api/books/<book_id>/cover", methods=["GET"])
@_require_book
def get_cover(book_id: str):
    """
    GET /api/books/<book_id>/cover
    Returns the cover image (JPEG).
    """
    cover_path = os.path.join(_book_out_dir(book_id), "cover.jpg")
    if not os.path.isfile(cover_path):
        return _error("Cover image not found.", 404)
    return send_file(cover_path, mimetype="image/jpeg")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tamil eBook Reader — NLP API")
    parser.add_argument("--host",  default="0.0.0.0",  help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port",  default=5000, type=int, help="Port to listen on (default: 5000)")
    parser.add_argument("--debug", action="store_true",   help="Enable Flask debug mode")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════╗
║   Tamil eBook Reader — NLP REST API              ║
╠══════════════════════════════════════════════════╣
║   POST  /api/upload                              ║
║   GET   /api/books                               ║
║   GET   /api/books/<id>                          ║
║   GET   /api/books/<id>/status                   ║
║   GET   /api/books/<id>/chapters                 ║
║   GET   /api/books/<id>/chapters/<n>             ║
║   GET   /api/books/<id>/audio/<n>                ║
║   GET   /api/books/<id>/cover                    ║
╚══════════════════════════════════════════════════╝
    Listening on http://{args.host}:{args.port}
    """)

    app.run(host=args.host, port=args.port, debug=args.debug)
