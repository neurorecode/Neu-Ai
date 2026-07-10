import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Task, TaskStatus } from "../types";
import { BotIcon, DotsIcon, PlusIcon, SearchIcon } from "./icons";

const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: "todo", label: "To do" },
  { key: "doing", label: "In progress" },
  { key: "done", label: "Done" },
];

export function TasksPage({
  workspaceId,
  onOpenMeeting,
}: {
  workspaceId?: string;
  onOpenMeeting: (id: string) => void;
}) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"board" | "list">("board");
  const [query, setQuery] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<TaskStatus | null>(null);
  const [adding, setAdding] = useState(false);

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

  const owners = useMemo(() => {
    const set = new Set<string>();
    tasks.forEach((t) => set.add(t.owner || "Unassigned"));
    return ["all", ...Array.from(set).sort()];
  }, [tasks]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks.filter((t) => {
      if (!q && t.archived) return false; // archived hidden unless searching
      if (q && !`${t.title} ${t.owner ?? ""}`.toLowerCase().includes(q)) return false;
      if (ownerFilter !== "all" && (t.owner || "Unassigned") !== ownerFilter) return false;
      return true;
    });
  }, [tasks, query, ownerFilter]);

  async function move(id: string, status: TaskStatus) {
    const prev = tasks.find((t) => t.id === id);
    if (!prev || prev.status === status) return;
    setTasks((ts) => ts.map((t) => (t.id === id ? { ...t, status } : t)));
    try {
      const updated = await api.updateTask(id, { status });
      setTasks((ts) => ts.map((t) => (t.id === id ? updated : t)));
    } catch (e) {
      setError((e as Error).message);
      setTasks((ts) => ts.map((t) => (t.id === id ? prev : t)));
    }
  }

  async function saveEdit(id: string, patch: Partial<Task>) {
    const updated = await api.updateTask(id, {
      title: patch.title,
      owner: patch.owner ?? null,
      due: patch.due ?? null,
    });
    setTasks((ts) => ts.map((t) => (t.id === id ? updated : t)));
  }

  async function remove(id: string) {
    setTasks((ts) => ts.filter((t) => t.id !== id));
    try {
      await api.deleteTask(id);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function addTask(title: string, owner: string, due: string) {
    const created = await api.createTask({
      title,
      owner: owner || null,
      due: due || null,
      workspace_id: workspaceId,
    });
    setTasks((ts) => [created, ...ts]);
    setAdding(false);
  }

  const counts = {
    todo: visible.filter((t) => t.status === "todo").length,
    doing: visible.filter((t) => t.status === "doing").length,
    done: visible.filter((t) => t.status === "done").length,
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">Tasks</h2>
          <p className="page-sub">
            {counts.todo + counts.doing} open · action items from meetings + your own
          </p>
        </div>
        <div className="head-actions">
          <div className="seg-toggle">
            <button className={view === "board" ? "active" : ""} onClick={() => setView("board")}>
              Board
            </button>
            <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>
              List
            </button>
          </div>
          <button className="btn primary" onClick={() => setAdding(true)}>
            <PlusIcon size={17} /> New task
          </button>
        </div>
      </div>

      <div className="table-toolbar">
        <div className="search-box">
          <SearchIcon size={16} />
          <input
            type="text"
            placeholder="Search tasks…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select className="filter-select" value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)}>
          {owners.map((o) => (
            <option key={o} value={o}>
              {o === "all" ? "All owners" : o}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {adding && <AddTaskForm onAdd={addTask} onCancel={() => setAdding(false)} />}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : view === "board" ? (
        <div className="kanban">
          {COLUMNS.map((col) => (
            <div
              key={col.key}
              className={`kanban-col ${dragOver === col.key ? "drag-over" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(col.key);
              }}
              onDragLeave={() => setDragOver((c) => (c === col.key ? null : c))}
              onDrop={() => {
                if (dragId) move(dragId, col.key);
                setDragId(null);
                setDragOver(null);
              }}
            >
              <div className="kanban-col-head">
                <span>{col.label}</span>
                <span className="col-count">{counts[col.key]}</span>
              </div>
              <div className="kanban-col-body">
                {visible
                  .filter((t) => t.status === col.key)
                  .map((t) => (
                    <TaskCard
                      key={t.id}
                      task={t}
                      onDragStart={() => setDragId(t.id)}
                      onMove={(s) => move(t.id, s)}
                      onSave={(p) => saveEdit(t.id, p)}
                      onDelete={() => remove(t.id)}
                      onOpenMeeting={onOpenMeeting}
                    />
                  ))}
                {counts[col.key] === 0 && <div className="col-empty">—</div>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <ul className="task-list">
          {visible.length === 0 && <li className="col-empty">No tasks match.</li>}
          {visible.map((t) => (
            <TaskCard
              key={t.id}
              task={t}
              listMode
              onDragStart={() => {}}
              onMove={(s) => move(t.id, s)}
              onSave={(p) => saveEdit(t.id, p)}
              onDelete={() => remove(t.id)}
              onOpenMeeting={onOpenMeeting}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function TaskCard({
  task,
  listMode,
  onDragStart,
  onMove,
  onSave,
  onDelete,
  onOpenMeeting,
}: {
  task: Task;
  listMode?: boolean;
  onDragStart: () => void;
  onMove: (s: TaskStatus) => void;
  onSave: (p: Partial<Task>) => void;
  onDelete: () => void;
  onOpenMeeting: (id: string) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [owner, setOwner] = useState(task.owner ?? "");
  const [due, setDue] = useState(task.due ?? "");

  if (editing) {
    return (
      <div className={`kanban-card ${listMode ? "list-card" : ""}`}>
        <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
        <div className="card-edit-row">
          <input type="text" placeholder="Owner" value={owner} onChange={(e) => setOwner(e.target.value)} />
          <input type="text" placeholder="Due" value={due} onChange={(e) => setDue(e.target.value)} />
        </div>
        <div className="card-edit-actions">
          <button
            className="btn primary"
            onClick={() => {
              if (title.trim()) onSave({ title: title.trim(), owner, due });
              setEditing(false);
            }}
          >
            Save
          </button>
          <button className="btn" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`kanban-card ${listMode ? "list-card" : ""}`}
      draggable={!listMode}
      onDragStart={onDragStart}
    >
      <div className="card-top">
        <span className="card-title">{task.title}</span>
        <div className="row-actions" onClick={(e) => e.stopPropagation()}>
          <button className="icon-btn" onClick={() => setMenu(!menu)} title="Actions">
            <DotsIcon size={17} />
          </button>
          {menu && (
            <div className="row-menu" onMouseLeave={() => setMenu(false)}>
              {COLUMNS.filter((c) => c.key !== task.status).map((c) => (
                <button key={c.key} className="row-menu-item" onClick={() => { setMenu(false); onMove(c.key); }}>
                  Move to {c.label}
                </button>
              ))}
              <button className="row-menu-item" onClick={() => { setMenu(false); setEditing(true); }}>
                Edit
              </button>
              <button className="row-menu-item danger" onClick={() => { setMenu(false); if (confirm("Delete this task?")) onDelete(); }}>
                Delete
              </button>
            </div>
          )}
        </div>
      </div>
      <div className="card-meta">
        <span className={`task-owner ${task.owner ? "" : "unassigned"}`}>{task.owner || "Unassigned"}</span>
        {task.due && <span className="task-due">📅 {task.due}</span>}
        {task.source === "meeting" && task.meeting_id && (
          <button className="task-source" onClick={() => onOpenMeeting(task.meeting_id!)}>
            <BotIcon size={13} /> meeting
          </button>
        )}
      </div>
    </div>
  );
}

function AddTaskForm({
  onAdd,
  onCancel,
}: {
  onAdd: (title: string, owner: string, due: string) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");
  return (
    <form
      className="add-task-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (title.trim()) onAdd(title.trim(), owner.trim(), due.trim());
      }}
    >
      <input type="text" placeholder="What needs doing?" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
      <input type="text" placeholder="Owner (optional)" value={owner} onChange={(e) => setOwner(e.target.value)} />
      <input type="text" placeholder="Due (optional)" value={due} onChange={(e) => setDue(e.target.value)} />
      <button className="btn primary" type="submit" disabled={!title.trim()}>
        Add
      </button>
      <button className="btn" type="button" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
