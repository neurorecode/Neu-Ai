import { useState } from "react";
import { api } from "../api";
import type { Segment } from "../types";
import { LanguageBadge } from "./badges";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function TranscriptPanel({
  meetingId,
  segments: initialSegments,
}: {
  meetingId: string;
  segments: Segment[];
}) {
  const [segments, setSegments] = useState(initialSegments);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function saveEdit(segmentId: string) {
    const text = draft.trim();
    if (!text) return;
    try {
      const updated = await api.editSegment(meetingId, segmentId, text);
      setSegments((prev) => prev.map((s) => (s.id === segmentId ? updated : s)));
      setEditingId(null);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function renameSpeaker(fromName: string) {
    const toName = prompt(`Rename speaker "${fromName}" to:`, fromName);
    if (!toName || toName.trim() === fromName) return;
    try {
      const updated = await api.renameSpeaker(meetingId, fromName, toName.trim());
      setSegments(updated);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (segments.length === 0) {
    return <p className="muted">Transcript will appear here once transcription completes.</p>;
  }
  return (
    <div className="transcript">
      <p className="muted small">
        Tip: click a speaker name to rename them everywhere; use ✎ to fix a
        mis-transcribed line (language is re-detected automatically).
      </p>
      {error && <p className="error small">{error}</p>}
      {segments.map((seg) => (
        <div key={seg.id} className="segment">
          <div className="segment-meta">
            <span className="timestamp">{formatTime(seg.start)}</span>
            {seg.speaker && (
              <button
                className="speaker speaker-btn"
                title="Rename this speaker across the meeting"
                onClick={() => renameSpeaker(seg.speaker!)}
              >
                {seg.speaker}
              </button>
            )}
            {seg.language && <LanguageBadge language={seg.language} />}
            {editingId !== seg.id && (
              <button
                className="icon-btn"
                title="Edit this segment"
                onClick={() => {
                  setEditingId(seg.id);
                  setDraft(seg.text);
                }}
              >
                ✎
              </button>
            )}
          </div>
          {editingId === seg.id ? (
            <div className="segment-edit">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
                autoFocus
              />
              <div className="segment-edit-actions">
                <button className="btn" onClick={() => saveEdit(seg.id)}>
                  Save
                </button>
                <button className="btn" onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p className="segment-text">{seg.text}</p>
          )}
        </div>
      ))}
    </div>
  );
}
