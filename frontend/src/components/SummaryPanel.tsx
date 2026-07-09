import { useState } from "react";
import type { MeetingDetail } from "../types";

export function SummaryPanel({
  meeting,
  onResummarize,
}: {
  meeting: MeetingDetail;
  onResummarize: () => void;
}) {
  const [overviewLang, setOverviewLang] = useState<"en" | "ta">("en");
  const s = meeting.summary;

  if (!s) {
    return <p className="muted">Summary will appear here once processing completes.</p>;
  }

  const overview = overviewLang === "en" ? s.overview_en : s.overview_ta;

  return (
    <div className="summary">
      <section>
        <div className="section-header">
          <h3>Overview</h3>
          <div className="lang-toggle">
            <button
              className={overviewLang === "en" ? "active" : ""}
              onClick={() => setOverviewLang("en")}
            >
              English
            </button>
            <button
              className={overviewLang === "ta" ? "active" : ""}
              onClick={() => setOverviewLang("ta")}
            >
              தமிழ்
            </button>
          </div>
        </div>
        <p className="overview-text">{overview || "—"}</p>
      </section>

      {s.topics && s.topics.length > 0 && (
        <section>
          <div className="topic-tags">
            {s.topics.map((t, i) => (
              <span key={i} className="topic-tag">
                {t}
              </span>
            ))}
          </div>
        </section>
      )}

      {s.action_items && s.action_items.length > 0 && (
        <section>
          <h3>Action items</h3>
          <table className="action-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Owner</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {s.action_items.map((a, i) => (
                <tr key={i}>
                  <td>{a.task}</td>
                  <td>{a.owner}</td>
                  <td>{a.due}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {s.decisions && s.decisions.length > 0 && (
        <section>
          <h3>Decisions</h3>
          <ul className="bullet-list">
            {s.decisions.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </section>
      )}

      {s.key_points && s.key_points.length > 0 && (
        <section>
          <h3>Key points</h3>
          <ul className="bullet-list">
            {s.key_points.map((k, i) => (
              <li key={i}>{k}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="summary-footer">
        {meeting.status === "completed" && (
          <button
            className="btn"
            title="Regenerate the summary from the current (edited) transcript"
            onClick={onResummarize}
          >
            ↻ Re-summarize
          </button>
        )}
        {s.language_breakdown && Object.keys(s.language_breakdown).length > 0 && (
          <span className="muted small">
            Language mix:{" "}
            {Object.entries(s.language_breakdown)
              .map(([lang, pct]) => `${lang} ${pct}%`)
              .join(" · ")}
          </span>
        )}
        {s.sentiment && <span className="muted small">Tone: {s.sentiment}</span>}
      </div>
    </div>
  );
}
