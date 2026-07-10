import { useState } from "react";
import { api } from "../api";

export function InviteBotBar({
  workspaceId,
  onInvited,
  onOpenCalendar,
}: {
  workspaceId?: string;
  onInvited: () => void;
  onOpenCalendar: () => void;
}) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function invite() {
    const meetingUrl = url.trim();
    if (!meetingUrl) return;
    setBusy(true);
    setError(null);
    try {
      await api.inviteBot(meetingUrl, "", workspaceId);
      setUrl("");
      onInvited();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="invite-bot">
      <div className="invite-bot-row">
        <input
          type="text"
          placeholder="Paste a Meet / Zoom / Teams link — Neu joins &amp; takes notes"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={busy}
          onKeyDown={(e) => e.key === "Enter" && invite()}
        />
        <button className="btn primary" onClick={invite} disabled={busy || !url.trim()}>
          Send Neu
        </button>
      </div>
      <button className="link-btn" onClick={onOpenCalendar}>
        📅 Upcoming meetings &amp; auto-join
      </button>
      {error && <p className="error small">{error}</p>}
    </div>
  );
}
