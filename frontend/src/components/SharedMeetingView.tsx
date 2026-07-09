import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { MeetingDetail } from "../types";
import { LanguageBadge } from "./badges";
import { AudioPlayer } from "./AudioPlayer";
import { SummaryPanel } from "./SummaryPanel";
import { TranscriptPanel } from "./TranscriptPanel";

type Tab = "summary" | "transcript";

/** Public, read-only meeting page served at /share/{token} — no sign-in. */
export function SharedMeetingView({ token }: { token: string }) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [playTime, setPlayTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    api.getShared(token).then(setMeeting).catch((e) => setError((e as Error).message));
  }, [token]);

  function seek(seconds: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = seconds;
    audio.play().catch(() => {});
  }

  if (error) {
    return (
      <div className="center-screen">
        <div className="login-card">
          <span className="brand-logo big">நீ</span>
          <h1>Neu AI</h1>
          <p className="error">{error}</p>
        </div>
      </div>
    );
  }
  if (!meeting) return <div className="center-screen muted">Loading…</div>;

  return (
    <div className="shared-page">
      <header className="shared-header">
        <div className="brand">
          <span className="brand-logo">நீ</span>
          <div>
            <h1>Neu AI</h1>
            <p>Shared meeting · read-only</p>
          </div>
        </div>
      </header>
      <main className="main shared-main">
        <div className="meeting-view">
          <header className="meeting-header">
            <h2>{meeting.title}</h2>
            <div className="meeting-meta">
              {meeting.language && <LanguageBadge language={meeting.language} />}
              {meeting.duration_seconds != null && (
                <span className="muted small">
                  {Math.round(meeting.duration_seconds / 60)} min{" "}
                  {Math.round(meeting.duration_seconds % 60)} s
                </span>
              )}
            </div>
          </header>

          <AudioPlayer
            ref={audioRef}
            src={api.sharedAudioUrl(token)}
            onTimeUpdate={setPlayTime}
          />

          <nav className="tabs">
            {(["summary", "transcript"] as Tab[]).map((t) => (
              <button
                key={t}
                className={tab === t ? "tab active" : "tab"}
                onClick={() => setTab(t)}
              >
                {t === "summary" ? "Summary" : "Transcript"}
              </button>
            ))}
          </nav>

          {tab === "summary" && (
            <SummaryPanel meeting={meeting} canEdit={false} onResummarize={() => {}} />
          )}
          {tab === "transcript" && (
            <TranscriptPanel
              segments={meeting.segments}
              readOnly
              activeTime={playTime}
              onSeek={seek}
            />
          )}
        </div>
      </main>
    </div>
  );
}
