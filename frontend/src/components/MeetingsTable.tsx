import { useMemo, useState } from "react";
import type { Meeting } from "../types";
import { LanguageBadge, StatusBadge } from "./badges";
import { BotIcon, DotsIcon, PlusIcon, SearchIcon } from "./icons";

const PAGE_SIZE = 12;

// Backend timestamps are UTC. If an offset is ever missing, treat as UTC
// (a bare "…T..:..:.." would otherwise be parsed as browser-local time).
function parseUTC(iso: string): Date {
  const hasTz = /[zZ]|[+-]\d\d:?\d\d$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
}

function relDate(iso: string): string {
  const d = parseUTC(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function duration(sec: number | null): string {
  if (!sec) return "—";
  const m = Math.round(sec / 60);
  if (m < 1) return `${Math.round(sec)}s`;
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function MeetingsTable({
  meetings,
  onSelect,
  onDelete,
  onNew,
}: {
  meetings: Meeting[];
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNew: () => void;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [menuId, setMenuId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return meetings;
    return meetings.filter((m) => m.title.toLowerCase().includes(q));
  }, [meetings, query]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const rows = filtered.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Meetings</h2>
          <p className="page-sub">{meetings.length} total in this workspace</p>
        </div>
        <button className="btn primary" onClick={onNew}>
          <PlusIcon size={17} /> New meeting
        </button>
      </div>

      <div className="table-toolbar">
        <div className="search-box">
          <SearchIcon size={16} />
          <input
            type="text"
            placeholder="Search meetings…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
          />
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="table-empty">
          {meetings.length === 0
            ? "No meetings yet. Create one from Home, or send Neu to a call."
            : "No meetings match your search."}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Meeting</th>
                <th>Status</th>
                <th>Language</th>
                <th>Created</th>
                <th>Duration</th>
                <th aria-label="actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id} onClick={() => onSelect(m.id)}>
                  <td>
                    <div className="cell-title">{m.title}</div>
                    <div className="cell-sub">
                      {m.source === "bot" ? (
                        <>
                          <BotIcon size={13} /> Auto-joined
                        </>
                      ) : (
                        "Uploaded"
                      )}
                    </div>
                  </td>
                  <td>
                    <StatusBadge status={m.status} />
                  </td>
                  <td>{m.language ? <LanguageBadge language={m.language} /> : <span className="muted">—</span>}</td>
                  <td className="muted">{relDate(m.created_at)}</td>
                  <td className="muted">{duration(m.duration_seconds)}</td>
                  <td>
                    <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="icon-btn"
                        onClick={() => setMenuId(menuId === m.id ? null : m.id)}
                        title="Actions"
                      >
                        <DotsIcon size={18} />
                      </button>
                      {menuId === m.id && (
                        <div className="row-menu" onMouseLeave={() => setMenuId(null)}>
                          <button
                            className="row-menu-item danger"
                            onClick={() => {
                              setMenuId(null);
                              if (confirm(`Delete "${m.title}"?`)) onDelete(m.id);
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <div className="pagination">
          <button className="btn" disabled={current === 0} onClick={() => setPage(current - 1)}>
            ←
          </button>
          <span className="muted small">
            Page {current + 1} of {pages}
          </span>
          <button className="btn" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            →
          </button>
        </div>
      )}
    </div>
  );
}
