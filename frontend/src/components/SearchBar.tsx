import { useEffect, useState } from "react";
import { api } from "../api";
import type { SearchHit } from "../types";

export function SearchBar({ onSelect }: { onSelect: (meetingId: string) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 2) {
      setHits([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        setHits(await api.search(query));
      } catch {
        setHits([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="search">
      <input
        type="text"
        placeholder="Search across meetings… (தமிழ் / English / Tanglish)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {hits.length > 0 && (
        <ul className="search-results">
          {hits.map((h, i) => (
            <li
              key={`${h.meeting_id}-${h.segment_id ?? i}`}
              onClick={() => {
                onSelect(h.meeting_id);
                setQ("");
              }}
            >
              <span className="search-meeting">{h.meeting_title}</span>
              <span className="search-snippet">{h.snippet}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
