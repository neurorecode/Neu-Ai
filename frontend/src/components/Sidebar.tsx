import type { User, Workspace } from "../types";
import {
  CalendarIcon,
  CheckSquareIcon,
  ChevronDown,
  HomeIcon,
  ListIcon,
  LogoutIcon,
  SettingsIcon,
  SparkIcon,
} from "./icons";

export type NavKey = "home" | "meetings" | "tasks" | "ask" | "calendar" | "settings";

const NAV: { key: NavKey; label: string; Icon: (p: { size?: number }) => JSX.Element }[] = [
  { key: "home", label: "Home", Icon: HomeIcon },
  { key: "meetings", label: "Meetings", Icon: ListIcon },
  { key: "tasks", label: "Tasks", Icon: CheckSquareIcon },
  { key: "ask", label: "Ask Neu", Icon: SparkIcon },
  { key: "calendar", label: "Calendar", Icon: CalendarIcon },
];

export function Sidebar({
  user,
  workspaces,
  currentId,
  active,
  onNavigate,
  onSwitch,
  onCreate,
  onLogout,
}: {
  user: User;
  workspaces: Workspace[];
  currentId: string | null;
  active: NavKey;
  onNavigate: (key: NavKey) => void;
  onSwitch: (id: string) => void;
  onCreate: (name: string) => void;
  onLogout: () => void;
}) {
  const current = workspaces.find((w) => w.id === currentId);

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-logo">நீ</span>
        <div>
          <h1>Neu AI</h1>
          <p>தமிழ் · English · Tanglish</p>
        </div>
      </div>

      <label className="ws-switch">
        <span className="ws-avatar">{(current?.name ?? "W").charAt(0).toUpperCase()}</span>
        <span className="ws-name">{current?.name ?? "Workspace"}</span>
        <ChevronDown size={16} />
        <select
          value={currentId ?? ""}
          onChange={(e) => {
            if (e.target.value === "__new__") {
              const name = prompt("New workspace name:");
              if (name?.trim()) onCreate(name.trim());
            } else {
              onSwitch(e.target.value);
            }
          }}
        >
          {workspaces.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
          <option value="__new__">＋ New workspace…</option>
        </select>
      </label>

      <nav className="nav">
        {NAV.map(({ key, label, Icon }) => (
          <button
            key={key}
            className={`nav-item ${active === key ? "active" : ""}`}
            onClick={() => onNavigate(key)}
          >
            <Icon size={19} />
            {label}
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />

      <div className="sidebar-footer">
        <button
          className={`nav-item ${active === "settings" ? "active" : ""}`}
          onClick={() => onNavigate("settings")}
        >
          <SettingsIcon size={19} />
          Settings
        </button>
        <div className="user-row">
          {user.picture ? (
            <img className="avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />
          ) : (
            <span className="avatar avatar-fallback">{user.name.charAt(0).toUpperCase()}</span>
          )}
          <span className="user-name" title={user.email}>
            {user.name}
          </span>
          <button className="icon-btn" title="Sign out" onClick={onLogout}>
            <LogoutIcon size={17} />
          </button>
        </div>
      </div>
    </aside>
  );
}
