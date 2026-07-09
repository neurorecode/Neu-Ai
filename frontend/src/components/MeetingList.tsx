import type { Meeting } from "../types";
import { LanguageBadge, StatusBadge } from "./badges";

export function MeetingList({
  meetings,
  selectedId,
  onSelect,
  onDelete,
}: {
  meetings: Meeting[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (meetings.length === 0) {
    return <p className="muted small">No meetings yet — upload or record one above.</p>;
  }
  return (
    <ul className="meeting-list">
      {meetings.map((m) => (
        <li
          key={m.id}
          className={m.id === selectedId ? "selected" : ""}
          onClick={() => onSelect(m.id)}
        >
          <div className="meeting-row-top">
            <span className="meeting-title">{m.title}</span>
            <button
              className="icon-btn"
              title="Delete meeting"
              onClick={(e) => {
                e.stopPropagation();
                if (confirm(`Delete "${m.title}"?`)) onDelete(m.id);
              }}
            >
              ✕
            </button>
          </div>
          <div className="meeting-row-bottom">
            <StatusBadge status={m.status} />
            {m.language && <LanguageBadge language={m.language} />}
            <span className="muted small">
              {new Date(m.created_at).toLocaleString()}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
