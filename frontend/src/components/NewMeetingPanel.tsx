import { useRef, useState } from "react";
import { api } from "../api";

export function NewMeetingPanel({
  onCreated,
  workspaceId,
}: {
  onCreated: () => void;
  workspaceId?: string;
}) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function upload(file: File | Blob, filename: string) {
    setBusy(true);
    setError(null);
    try {
      await api.uploadMeeting(title || "Untitled meeting", file, filename, workspaceId);
      setTitle("");
      if (fileInput.current) fileInput.current.value = "";
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        upload(blob, "recording.webm");
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (e) {
      setError("Microphone access denied or unavailable.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setRecording(false);
  }

  return (
    <div className="new-meeting">
      <input
        type="text"
        placeholder="Meeting title (e.g. Sprint stand-up)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        disabled={busy}
      />
      <div className="new-meeting-actions">
        <label className={`btn ${busy ? "disabled" : ""}`}>
          Upload audio
          <input
            ref={fileInput}
            type="file"
            accept=".wav,.mp3,.m4a,.mp4,.webm,.ogg,.flac,.aac,audio/*,video/mp4"
            hidden
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f, f.name);
            }}
          />
        </label>
        {recording ? (
          <button className="btn recording" onClick={stopRecording}>
            ■ Stop &amp; save
          </button>
        ) : (
          <button className="btn" onClick={startRecording} disabled={busy}>
            ● Record
          </button>
        )}
      </div>
      {busy && <p className="muted small">Uploading…</p>}
      {error && <p className="error small">{error}</p>}
    </div>
  );
}
