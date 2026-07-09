import type { Segment } from "../types";
import { LanguageBadge } from "./badges";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function TranscriptPanel({ segments }: { segments: Segment[] }) {
  if (segments.length === 0) {
    return <p className="muted">Transcript will appear here once transcription completes.</p>;
  }
  return (
    <div className="transcript">
      {segments.map((seg) => (
        <div key={seg.id} className="segment">
          <div className="segment-meta">
            <span className="timestamp">{formatTime(seg.start)}</span>
            {seg.speaker && <span className="speaker">{seg.speaker}</span>}
            {seg.language && <LanguageBadge language={seg.language} />}
          </div>
          <p className="segment-text">{seg.text}</p>
        </div>
      ))}
    </div>
  );
}
