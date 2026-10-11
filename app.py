import os
import sqlite3
import tempfile
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, render_template
from werkzeug.utils import secure_filename

from speech_service import transcribe_audio_file, SpeechServiceError

load_dotenv()

ALLOWED_AUDIO_EXTENSIONS = {"wav"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "notes.db"),
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
    )

    if test_config:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(
                app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
        return g.db

    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.commit()

    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/notes", methods=["GET"])
    def get_notes():
        db = get_db()
        rows = db.execute("SELECT * FROM notes ORDER BY updated_at DESC").fetchall()
        return jsonify([dict(row) for row in rows]), 200

    @app.route("/api/notes", methods=["POST"])
    def create_note():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()

        if not title:
            return jsonify({"error": "Title is required"}), 400
        if not content:
            return jsonify({"error": "Content is required"}), 400

        now = datetime.utcnow().isoformat()
        db = get_db()
        cur = db.execute(
            "INSERT INTO notes (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, content, now, now),
        )
        db.commit()
        note = db.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(note)), 201

    @app.route("/api/notes/<int:note_id>", methods=["GET"])
    def get_note(note_id):
        db = get_db()
        note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            return jsonify({"error": "Note not found"}), 404
        return jsonify(dict(note)), 200

    @app.route("/api/notes/<int:note_id>", methods=["PUT"])
    def update_note(note_id):
        db = get_db()
        note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            return jsonify({"error": "Note not found"}), 404

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        title = (data.get("title") if data.get("title") is not None else note["title"]).strip()
        content = (
            data.get("content") if data.get("content") is not None else note["content"]
        ).strip()

        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400
        if not content:
            return jsonify({"error": "Content cannot be empty"}), 400

        now = datetime.utcnow().isoformat()
        db.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, now, note_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return jsonify(dict(updated)), 200

    @app.route("/api/notes/<int:note_id>", methods=["DELETE"])
    def delete_note(note_id):
        db = get_db()
        note = db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if note is None:
            return jsonify({"error": "Note not found"}), 404
        db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        db.commit()
        return jsonify({"message": "Note deleted"}), 200

    @app.route("/api/speech-to-text", methods=["POST"])
    def speech_to_text():
        if "audio" not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        if audio_file.filename == "":
            return jsonify({"error": "Empty filename"}), 400

        filename = secure_filename(audio_file.filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return jsonify({"error": "Only WAV audio files are supported"}), 400

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_file.save(tmp.name)
                tmp_path = tmp.name

            text = transcribe_audio_file(tmp_path)
            return jsonify({"text": text}), 200

        except SpeechServiceError as exc:
            return jsonify({"error": str(exc)}), 502
        except Exception:
            app.logger.exception("Unexpected error during transcription")
            return jsonify({"error": "Internal server error during transcription"}), 500
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    @app.errorhandler(413)
    def request_too_large(_e):
        return jsonify({"error": "Audio file is too large"}), 413

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Resource not found"}), 404

    return app


app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
