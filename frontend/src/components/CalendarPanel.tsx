import { useEffect, useState } from "react";
import { api } from "../api";
import type { CalendarEvent, CalendarStatus } from "../types";

export function CalendarPanel({
  workspaceId,
  onJoined,
  onClose,
}: {
  workspaceId?: string;
  onJoined: () => void;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.calendarStatus().then(setStatus).catch(() => {});
    api
      .calendarEvents()
      .then(setEvents)
      .catch((e) => setError((e as Error).message));
  }, []);

  async function join(ev: CalendarEvent) {
    if (!ev.meeting_url) return;
    setBusy(true);
    try {
      await api.inviteBot(ev.meeting_url, ev.title, workspaceId);
      onJoined();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleAutoJoin() {
    if (!status) return;
    const next = status.auto_join === "video" ? "none" : "video";
    try {
      setStatus(await api.setAutoJoin(next));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="settings">
      <header className="meeting-header">
        <h2>Upcoming meetings</h2>
        <button className="btn" onClick={onClose}>
          ← Back
        </button>
      </header>

      {status && !status.bots_enabled && (
        <div className="processing-banner">
          Auto-join needs a meeting-bot provider. Set <code>BOT_PROVIDER=recall</code> and
          <code> RECALL_API_KEY</code> on the server to let Neu join calls (see DEPLOY.md).
        </div>
      )}

      {status && (
        <label className="autojoin-row">
          <input
            type="checkbox"
            checked={status.auto_join === "video"}
            onChange={toggleAutoJoin}
            disabled={!status.bots_enabled}
          />
          Automatically send Neu to all my calendar meetings that have a video link
        </label>
      )}

      {error && <div className="error-banner">{error}</div>}

      {events.length === 0 && !error && (
        <p className="muted">No upcoming meetings in the next 24 hours.</p>
      )}

      <div className="cal-events">
        {events.map((ev) => (
          <div key={ev.id ?? ev.title} className="cal-event">
            <div>
              <div className="cal-title">{ev.title}</div>
              <div className="muted small">
                {ev.start ? new Date(ev.start).toLocaleString() : ""} · {ev.attendees} attendee
                {ev.attendees === 1 ? "" : "s"}
              </div>
            </div>
            {ev.meeting_url ? (
              <button className="btn" disabled={busy} onClick={() => join(ev)}>
                Send Neu
              </button>
            ) : (
              <span className="muted small">no video link</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
