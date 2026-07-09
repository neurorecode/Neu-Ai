import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Meeting } from "./types";
import { MeetingList } from "./components/MeetingList";
import { MeetingView } from "./components/MeetingView";
import { NewMeetingPanel } from "./components/NewMeetingPanel";
import { SearchBar } from "./components/SearchBar";

export default function App() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMeetings(await api.listMeetings());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while any meeting is still processing
  useEffect(() => {
    const processing = meetings.some(
      (m) => m.status !== "completed" && m.status !== "failed",
    );
    if (!processing) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [meetings, refresh]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-logo">நீ</span>
          <div>
            <h1>Neu AI</h1>
            <p>தமிழ் · English · Tanglish</p>
          </div>
        </div>

        <NewMeetingPanel onCreated={refresh} />
        <SearchBar onSelect={(id) => setSelectedId(id)} />

        {error && <div className="error-banner">{error}</div>}

        <MeetingList
          meetings={meetings}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onDelete={async (id) => {
            await api.deleteMeeting(id);
            if (selectedId === id) setSelectedId(null);
            refresh();
          }}
        />
      </aside>

      <main className="main">
        {selectedId ? (
          <MeetingView meetingId={selectedId} key={selectedId} />
        ) : (
          <div className="empty-state">
            <h2>Your AI meeting assistant for Tamil, English &amp; Tanglish</h2>
            <p>
              Upload a recording or record live. Neu transcribes it, tags each
              utterance as தமிழ், English, or Tanglish, and writes a bilingual
              summary with action items &amp; decisions. Then chat with the
              meeting in whichever language you like.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
