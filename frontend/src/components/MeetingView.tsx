import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { MeetingDetail } from "../types";
import { LanguageBadge, StatusBadge } from "./badges";
import { AudioPlayer } from "./AudioPlayer";
import { SummaryPanel } from "./SummaryPanel";
import { TranscriptPanel } from "./TranscriptPanel";
import { ChatPanel } from "./ChatPanel";

type Tab = "summary" | "transcript" | "chat";

export function MeetingView({
  meetingId,
  canEdit = true,
}: {
  meetingId: string;
  canEdit?: boolean;
}) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState<string | null>(null);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [shareMsg, setShareMsg] = useState<string | null>(null);
  const [playTime, setPlayTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function load() {
      try {
        const m = await api.getMeeting(meetingId);
        if (cancelled) return;
        setMeeting(m);
        setError(null);
        if (m.status !== "completed" && m.status !== "failed") {
          timer = setTimeout(load, 2500);
        }
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    }
    load();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [meetingId]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!meeting) return <div className="muted">Loading…</div>;

  const processing = meeting.status !== "completed" && meeting.status !== "failed";

  function seek(seconds: number) {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = seconds;
    audio.play().catch(() => {});
  }

  async function toggleShare() {
    try {
      if (shareToken) {
        await api.disableShare(meeting!.id);
        setShareToken(null);
        setShareMsg("Share link revoked");
      } else {
        const { share_token } = await api.enableShare(meeting!.id);
        setShareToken(share_token);
        if (share_token) {
          const url = `${window.location.origin}/share/${share_token}`;
          await navigator.clipboard.writeText(url).catch(() => {});
          setShareMsg("Share link copied to clipboard");
        }
      }
      setTimeout(() => setShareMsg(null), 3000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="meeting-view">
      <header className="meeting-header">
        <div>
          <h2>{meeting.title}</h2>
          <div className="meeting-meta">
            <StatusBadge status={meeting.status} />
            {meeting.language && <LanguageBadge language={meeting.language} />}
            {meeting.duration_seconds != null && (
              <span className="muted small">
                {Math.round(meeting.duration_seconds / 60)} min{" "}
                {Math.round(meeting.duration_seconds % 60)} s
              </span>
            )}
          </div>
          {shareMsg && <p className="muted small">{shareMsg}</p>}
        </div>
        {canEdit && meeting.status === "completed" && (
          <button className="btn" onClick={toggleShare}>
            {shareToken ? "Revoke share link" : "🔗 Share"}
          </button>
        )}
      </header>

      {meeting.status === "failed" && (
        <div className="error-banner">
          Processing failed: {meeting.error ?? "unknown error"}
        </div>
      )}
      {meeting.status === "completed" && meeting.error && (
        <div className="notice-banner">{meeting.error}</div>
      )}

      {processing && (
        <div className="processing-banner">
          <div className="processing-row">
            <div className="spinner" />
            <span>
              {meeting.stage ?? "Processing"} — {meeting.progress}%
            </span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${meeting.progress}%` }} />
          </div>
        </div>
      )}

      {meeting.status === "completed" && meeting.has_audio && (
        <AudioPlayer ref={audioRef} src={api.audioUrl(meeting.id)} onTimeUpdate={setPlayTime} />
      )}
      {meeting.status === "completed" && !meeting.has_audio && (
        <p className="muted small">
          Recording removed by the retention policy — transcript and summary are kept.
        </p>
      )}

      <nav className="tabs">
        {(["summary", "transcript", "chat"] as Tab[]).map((t) => (
          <button
            key={t}
            className={tab === t ? "tab active" : "tab"}
            onClick={() => setTab(t)}
          >
            {t === "summary" ? "Summary" : t === "transcript" ? "Transcript" : "Ask Neu"}
          </button>
        ))}
      </nav>

      {tab === "summary" && (
        <SummaryPanel
          meeting={meeting}
          canEdit={canEdit}
          onResummarize={async () => {
            await api.resummarize(meeting.id);
            setMeeting({ ...meeting, status: "summarizing", progress: 85, stage: "Queued for summary" });
          }}
        />
      )}
      {tab === "transcript" && (
        <TranscriptPanel
          key={meeting.segments.length}
          meetingId={meeting.id}
          segments={meeting.segments}
          readOnly={!canEdit}
          activeTime={playTime}
          onSeek={seek}
        />
      )}
      {tab === "chat" && (
        <ChatPanel meetingId={meeting.id} ready={meeting.status === "completed"} />
      )}
    </div>
  );
}
