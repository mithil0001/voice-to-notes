const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const recordingStatus = document.getElementById("recordingStatus");
const transcriptionText = document.getElementById("transcriptionText");
const noteTitle = document.getElementById("noteTitle");
const saveNoteBtn = document.getElementById("saveNoteBtn");
const notesList = document.getElementById("notesList");
const statusBanner = document.getElementById("statusBanner");

let audioContext = null;
let mediaStreamSource = null;
let scriptProcessor = null;
let mediaStream = null;
let recordedChunks = [];
let isRecording = false;

function showStatus(message, type, autoHideMs) {
    if (type === undefined) type = "info";
    if (autoHideMs === undefined) autoHideMs = 4000;
    statusBanner.textContent = message;
    statusBanner.className = "status-banner " + type;
    statusBanner.classList.remove("hidden");
    if (autoHideMs) {
        clearTimeout(showStatus._timer);
        showStatus._timer = setTimeout(function () {
            statusBanner.classList.add("hidden");
        }, autoHideMs);
    }
}

function mergeFloat32Buffers(buffers) {
    let totalLength = 0;
    buffers.forEach(function (b) { totalLength += b.length; });
    const result = new Float32Array(totalLength);
    let offset = 0;
    buffers.forEach(function (b) { result.set(b, offset); offset += b.length; });
    return result;
}

function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
}

function encodeWAV(samples, sampleRate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, "WAVE");
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([view], { type: "audio/wav" });
}

async function startRecording() {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
        showStatus("Microphone access was denied or is unavailable. Please allow microphone permissions.", "error", 6000);
        return;
    }

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    mediaStreamSource = audioContext.createMediaStreamSource(mediaStream);
    scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
    recordedChunks = [];

    scriptProcessor.onaudioprocess = function (event) {
        recordedChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };

    mediaStreamSource.connect(scriptProcessor);
    scriptProcessor.connect(audioContext.destination);

    isRecording = true;
    recordBtn.disabled = true;
    stopBtn.disabled = false;
    recordingStatus.textContent = "Recording...";
    recordingStatus.classList.add("active");
    showStatus("Recording started. Speak clearly into your microphone.", "info", 3000);
}

function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    scriptProcessor.disconnect();
    mediaStreamSource.disconnect();
    mediaStream.getTracks().forEach(function (track) { track.stop(); });

    const sampleRate = audioContext.sampleRate;
    const merged = mergeFloat32Buffers(recordedChunks);
    const wavBlob = encodeWAV(merged, sampleRate);
    audioContext.close();

    recordBtn.disabled = false;
    stopBtn.disabled = true;
    recordingStatus.textContent = "Processing...";
    recordingStatus.classList.remove("active");

    sendAudioForTranscription(wavBlob);
}

async function sendAudioForTranscription(wavBlob) {
    showStatus("Transcribing audio with Azure AI Speech...", "info", 0);
    const formData = new FormData();
    formData.append("audio", wavBlob, "recording.wav");

    try {
        const response = await fetch("/api/speech-to-text", { method: "POST", body: formData });
        const data = await response.json();

        if (!response.ok) {
            showStatus(data.error || "Transcription failed.", "error", 6000);
            recordingStatus.textContent = "Idle";
            return;
        }
        if (!data.text) {
            showStatus("No speech was detected. Please try again.", "error", 5000);
        } else {
            transcriptionText.value = data.text;
            showStatus("Transcription complete. You can edit the text before saving.", "success");
        }
        recordingStatus.textContent = "Idle";
    } catch (err) {
        showStatus("Could not reach the server. Please check your connection.", "error", 6000);
        recordingStatus.textContent = "Idle";
    }
}

recordBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecording);

async function loadNotes() {
    try {
        const response = await fetch("/api/notes");
        const notes = await response.json();
        renderNotes(notes);
    } catch (err) {
        showStatus("Failed to load notes.", "error");
    }
}

function renderNotes(notes) {
    notesList.innerHTML = "";
    if (!notes || notes.length === 0) {
        notesList.innerHTML = '<p class="empty-state">No notes yet. Record something and save it!</p>';
        return;
    }

    notes.forEach(function (note) {
        const item = document.createElement("div");
        item.className = "note-item";
        item.dataset.id = note.id;
        const updated = new Date(note.updated_at).toLocaleString();

        item.innerHTML =
            '<h3 class="note-title-display">' + escapeHtml(note.title) + '</h3>' +
            '<p class="note-content-display">' + escapeHtml(note.content) + '</p>' +
            '<div class="note-meta">Last updated: ' + updated + '</div>' +
            '<div class="note-actions">' +
            '<button class="btn btn-secondary btn-small edit-btn">Edit</button>' +
            '<button class="btn btn-danger delete-btn">Delete</button>' +
            '</div>';

        item.querySelector(".edit-btn").addEventListener("click", function () { enterEditMode(item, note); });
        item.querySelector(".delete-btn").addEventListener("click", function () { deleteNote(note.id); });
        notesList.appendChild(item);
    });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function enterEditMode(item, note) {
    item.innerHTML =
        '<input type="text" class="edit-title-input" value="' + escapeHtml(note.title) + '" maxlength="120" />' +
        '<textarea class="note-edit-textarea">' + escapeHtml(note.content) + '</textarea>' +
        '<div class="note-actions">' +
        '<button class="btn btn-primary btn-small save-edit-btn">Save</button>' +
        '<button class="btn btn-secondary btn-small cancel-edit-btn">Cancel</button>' +
        '</div>';

    item.querySelector(".save-edit-btn").addEventListener("click", async function () {
        const newTitle = item.querySelector(".edit-title-input").value.trim();
        const newContent = item.querySelector(".note-edit-textarea").value.trim();

        if (!newTitle || !newContent) {
            showStatus("Title and content cannot be empty.", "error");
            return;
        }

        try {
            const response = await fetch("/api/notes/" + note.id, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newTitle, content: newContent }),
            });
            if (!response.ok) {
                const data = await response.json();
                showStatus(data.error || "Failed to update note.", "error");
                return;
            }
            showStatus("Note updated successfully.", "success");
            loadNotes();
        } catch (err) {
            showStatus("Failed to update note.", "error");
        }
    });

    item.querySelector(".cancel-edit-btn").addEventListener("click", loadNotes);
}

async function deleteNote(noteId) {
    if (!confirm("Are you sure you want to delete this note?")) return;
    try {
        const response = await fetch("/api/notes/" + noteId, { method: "DELETE" });
        if (!response.ok) {
            const data = await response.json();
            showStatus(data.error || "Failed to delete note.", "error");
            return;
        }
        showStatus("Note deleted.", "success");
        loadNotes();
    } catch (err) {
        showStatus("Failed to delete note.", "error");
    }
}

saveNoteBtn.addEventListener("click", async function () {
    const title = noteTitle.value.trim();
    const content = transcriptionText.value.trim();

    if (!title) { showStatus("Please enter a note title.", "error"); return; }
    if (!content) { showStatus("There is no transcription to save. Record something first.", "error"); return; }

    try {
        const response = await fetch("/api/notes", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: title, content: content }),
        });
        const data = await response.json();
        if (!response.ok) {
            showStatus(data.error || "Failed to save note.", "error");
            return;
        }
        showStatus("Note saved successfully.", "success");
        noteTitle.value = "";
        transcriptionText.value = "";
        loadNotes();
    } catch (err) {
        showStatus("Failed to save note. Check your connection.", "error");
    }
});

document.addEventListener("DOMContentLoaded", loadNotes);
