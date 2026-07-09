import type { User, Workspace } from "../types";

export function WorkspaceBar({
  user,
  workspaces,
  currentId,
  onSwitch,
  onCreate,
  onOpenSettings,
  onLogout,
}: {
  user: User;
  workspaces: Workspace[];
  currentId: string | null;
  onSwitch: (id: string) => void;
  onCreate: (name: string) => void;
  onOpenSettings: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="workspace-bar">
      <div className="workspace-row">
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
        <button className="icon-btn" title="Workspace settings" onClick={onOpenSettings}>
          ⚙
        </button>
      </div>
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
          ⎋
        </button>
      </div>
    </div>
  );
}
