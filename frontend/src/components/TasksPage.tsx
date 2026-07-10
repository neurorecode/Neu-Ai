import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { TaskItem } from "../types";
import { CheckIcon } from "./icons";

export function TasksPage({
  workspaceId,
  onOpenMeeting,
}: {
  workspaceId?: string;
  onOpenMeeting: (id: string) => void;
}) {
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDone, setShowDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getTasks(workspaceId)
      .then((t) => !cancelled && setTasks(t))
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const key = (t: TaskItem) => `${t.meeting_id}:${t.index}`;

  async function toggle(t: TaskItem) {
    // optimistic
    setTasks((prev) => prev.map((x) => (key(x) === key(t) ? { ...x, done: !x.done } : x)));
    try {
      await api.toggleTask(t.meeting_id, t.index, !t.done);
    } catch (e) {
      setError((e as Error).message);
      setTasks((prev) => prev.map((x) => (key(x) === key(t) ? { ...x, done: t.done } : x)));
    }
  }

  const open = useMemo(() => tasks.filter((t) => !t.done), [tasks]);
  const done = useMemo(() => tasks.filter((t) => t.done), [tasks]);
  const visible = showDone ? done : open;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Tasks</h2>
          <p className="page-sub">
            {open.length} open · {done.length} done — action items from every meeting
          </p>
        </div>
        <div className="seg-toggle">
          <button className={!showDone ? "active" : ""} onClick={() => setShowDone(false)}>
            Open ({open.length})
          </button>
          <button className={showDone ? "active" : ""} onClick={() => setShowDone(true)}>
            Done ({done.length})
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="table-empty">
          {showDone
            ? "Nothing completed yet."
            : "No open action items. They'll appear here automatically after meetings with action items."}
        </div>
      ) : (
        <ul className="task-list">
          {visible.map((t) => (
            <li key={key(t)} className={`task-row ${t.done ? "done" : ""}`}>
              <button
                className={`task-check ${t.done ? "checked" : ""}`}
                onClick={() => toggle(t)}
                title={t.done ? "Mark not done" : "Mark done"}
              >
                {t.done && <CheckIcon size={14} />}
              </button>
              <div className="task-body">
                <div className="task-text">{t.task}</div>
                <div className="task-meta">
                  {t.owner && <span className="task-owner">{t.owner}</span>}
                  {t.due && <span className="task-due">📅 {t.due}</span>}
                  <button className="task-source" onClick={() => onOpenMeeting(t.meeting_id)}>
                    {t.meeting_title}
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
