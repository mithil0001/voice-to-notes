import io
import json
import os
import tempfile

import pytest

import app as app_module
from speech_service import SpeechServiceError


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    flask_app = app_module.create_app({"DATABASE": db_path, "TESTING": True})

    with flask_app.test_client() as test_client:
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_create_note_success(client):
    response = client.post(
        "/api/notes",
        data=json.dumps({"title": "Test Note", "content": "Hello world"}),
        content_type="application/json",
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Test Note"
    assert data["content"] == "Hello world"
    assert "id" in data


def test_create_note_missing_title(client):
    response = client.post(
        "/api/notes",
        data=json.dumps({"content": "No title here"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_create_note_missing_content(client):
    response = client.post(
        "/api/notes",
        data=json.dumps({"title": "No content"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_create_note_invalid_json(client):
    response = client.post("/api/notes", data="not json", content_type="application/json")
    assert response.status_code == 400


def test_get_notes_list(client):
    client.post(
        "/api/notes",
        data=json.dumps({"title": "A", "content": "B"}),
        content_type="application/json",
    )
    response = client.get("/api/notes")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_get_single_note(client):
    create_resp = client.post(
        "/api/notes",
        data=json.dumps({"title": "A", "content": "B"}),
        content_type="application/json",
    )
    note_id = create_resp.get_json()["id"]
    response = client.get(f"/api/notes/{note_id}")
    assert response.status_code == 200
    assert response.get_json()["id"] == note_id


def test_get_nonexistent_note(client):
    response = client.get("/api/notes/9999")
    assert response.status_code == 404


def test_update_note(client):
    create_resp = client.post(
        "/api/notes",
        data=json.dumps({"title": "Old Title", "content": "Old Content"}),
        content_type="application/json",
    )
    note_id = create_resp.get_json()["id"]

    update_resp = client.put(
        f"/api/notes/{note_id}",
        data=json.dumps({"title": "New Title", "content": "New Content"}),
        content_type="application/json",
    )
    assert update_resp.status_code == 200
    data = update_resp.get_json()
    assert data["title"] == "New Title"
    assert data["content"] == "New Content"


def test_update_nonexistent_note(client):
    response = client.put(
        "/api/notes/9999",
        data=json.dumps({"title": "X", "content": "Y"}),
        content_type="application/json",
    )
    assert response.status_code == 404


def test_delete_note(client):
    create_resp = client.post(
        "/api/notes",
        data=json.dumps({"title": "To Delete", "content": "Content"}),
        content_type="application/json",
    )
    note_id = create_resp.get_json()["id"]

    delete_resp = client.delete(f"/api/notes/{note_id}")
    assert delete_resp.status_code == 200

    get_resp = client.get(f"/api/notes/{note_id}")
    assert get_resp.status_code == 404


def test_delete_nonexistent_note(client):
    response = client.delete("/api/notes/9999")
    assert response.status_code == 404


def test_speech_to_text_no_file(client):
    response = client.post("/api/speech-to-text")
    assert response.status_code == 400


def test_speech_to_text_invalid_extension(client):
    data = {"audio": (io.BytesIO(b"fake data"), "audio.mp3")}
    response = client.post("/api/speech-to-text", data=data, content_type="multipart/form-data")
    assert response.status_code == 400


def test_speech_to_text_success(client, monkeypatch):
    monkeypatch.setattr(
        app_module, "transcribe_audio_file", lambda path: "Hello from mocked speech"
    )

    data = {"audio": (io.BytesIO(b"RIFF....WAVEfmt "), "recording.wav")}
    response = client.post("/api/speech-to-text", data=data, content_type="multipart/form-data")
    assert response.status_code == 200
    assert response.get_json()["text"] == "Hello from mocked speech"


def test_speech_to_text_service_error(client, monkeypatch):
    def raise_error(_path):
        raise SpeechServiceError("Azure Speech credentials are not configured.")

    monkeypatch.setattr(app_module, "transcribe_audio_file", raise_error)

    data = {"audio": (io.BytesIO(b"RIFF....WAVEfmt "), "recording.wav")}
    response = client.post("/api/speech-to-text", data=data, content_type="multipart/form-data")
    assert response.status_code == 502
    assert "error" in response.get_json()
