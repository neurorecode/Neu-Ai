import { useEffect, useState } from "react";
import { api } from "../api";
import type { MeetingDetail } from "../types";
import { LanguageBadge, StatusBadge } from "./badges";
import { SummaryPanel } from "./SummaryPanel";
import { TranscriptPanel } from "./TranscriptPanel";
import { ChatPanel } from "./ChatPanel";

type Tab = "summary" | "transcript" | "chat";

export function MeetingView({ meetingId }: { meetingId: string }) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="meeting-view">
      <header className="meeting-header">
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
      </header>

      {meeting.status === "failed" && (
        <div className="error-banner">
          Processing failed: {meeting.error ?? "unknown error"}
        </div>
      )}

      {processing && (
        <div className="processing-banner">
          <div className="spinner" /> Neu is working on this meeting — transcribing
          and summarizing. This page refreshes automatically.
        </div>
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

      {tab === "summary" && <SummaryPanel meeting={meeting} />}
      {tab === "transcript" && <TranscriptPanel segments={meeting.segments} />}
      {tab === "chat" && (
        <ChatPanel meetingId={meeting.id} ready={meeting.status === "completed"} />
      )}
    </div>
  );
}
