import { useEffect, useState } from "react";
import { api } from "../api";
import type { Invite, Member, User, Workspace } from "../types";

export function SettingsPanel({
  workspace,
  currentUser,
  onUpdated,
  onClose,
}: {
  workspace: Workspace;
  currentUser: User;
  onUpdated: (ws: Workspace) => void;
  onClose: () => void;
}) {
  const isOwner = workspace.role === "owner";
  const [name, setName] = useState(workspace.name);
  const [summaryLanguage, setSummaryLanguage] = useState(workspace.summary_language);
  const [vocabulary, setVocabulary] = useState(
    (workspace.custom_vocabulary ?? []).join(", "),
  );
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listMembers(workspace.id).then(setMembers).catch(() => {});
    api.listInvites(workspace.id).then(setInvites).catch(() => {});
  }, [workspace.id]);

  async function save() {
    try {
      const updated = await api.updateWorkspace(workspace.id, {
        name,
        summary_language: summaryLanguage,
        custom_vocabulary: vocabulary
          .split(",")
          .map((w) => w.trim())
          .filter(Boolean),
      } as Partial<Workspace>);
      onUpdated({ ...updated, role: workspace.role });
      setMessage("Saved");
      setError(null);
      setTimeout(() => setMessage(null), 2000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function invite() {
    const email = inviteEmail.trim();
    if (!email) return;
    try {
      const inv = await api.createInvite(workspace.id, email, inviteRole);
      setInvites((prev) => [inv, ...prev]);
      setInviteEmail("");
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function inviteLink(token: string) {
    return `${window.location.origin}/?invite=${token}`;
  }

  return (
    <div className="settings">
      <header className="meeting-header">
        <h2>Workspace settings</h2>
        <button className="btn" onClick={onClose}>
          ← Back
        </button>
      </header>
      {error && <div className="error-banner">{error}</div>}
      {message && <div className="processing-banner">{message}</div>}

      <section>
        <h3>General</h3>
        <div className="settings-grid">
          <label>
            Workspace name
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={!isOwner}
            />
          </label>
          <label>
            Summary detail language
            <select
              value={summaryLanguage}
              onChange={(e) => setSummaryLanguage(e.target.value as Workspace["summary_language"])}
              disabled={!isOwner}
            >
              <option value="both">Bilingual (English + தமிழ்)</option>
              <option value="en">English</option>
              <option value="ta">தமிழ்</option>
            </select>
          </label>
          <label>
            Custom vocabulary (comma-separated names &amp; terms)
            <textarea
              rows={2}
              placeholder="e.g. Neu AI, Karthik, saarika, நியூரோ"
              value={vocabulary}
              onChange={(e) => setVocabulary(e.target.value)}
              disabled={!isOwner}
            />
          </label>
          {isOwner && (
            <button className="btn" onClick={save}>
              Save settings
            </button>
          )}
        </div>
      </section>

      <section>
        <h3>Members</h3>
        <table className="action-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id}>
                <td>{m.user.name}</td>
                <td>{m.user.email}</td>
                <td>{m.role}</td>
                <td>
                  {(isOwner || m.user.id === currentUser.id) && members.length > 1 && (
                    <button
                      className="icon-btn"
                      title={m.user.id === currentUser.id ? "Leave workspace" : "Remove member"}
                      onClick={async () => {
                        if (!confirm(`Remove ${m.user.name} from this workspace?`)) return;
                        await api.removeMember(workspace.id, m.id);
                        setMembers((prev) => prev.filter((x) => x.id !== m.id));
                      }}
                    >
                      ✕
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {workspace.role !== "viewer" && (
        <section>
          <h3>Invite teammates</h3>
          <div className="invite-row">
            <input
              type="text"
              placeholder="colleague@company.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
              <option value="member">Member</option>
              <option value="viewer">Viewer</option>
            </select>
            <button className="btn" onClick={invite}>
              Invite
            </button>
          </div>
          {invites.length > 0 && (
            <table className="action-table">
              <thead>
                <tr>
                  <th>Pending invite</th>
                  <th>Role</th>
                  <th>Link</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invites.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.email}</td>
                    <td>{inv.role}</td>
                    <td>
                      <button
                        className="btn"
                        onClick={() => {
                          navigator.clipboard.writeText(inviteLink(inv.token));
                          setMessage("Invite link copied — send it to your teammate");
                          setTimeout(() => setMessage(null), 2500);
                        }}
                      >
                        Copy link
                      </button>
                    </td>
                    <td>
                      <button
                        className="icon-btn"
                        title="Revoke invite"
                        onClick={async () => {
                          await api.revokeInvite(workspace.id, inv.id);
                          setInvites((prev) => prev.filter((x) => x.id !== inv.id));
                        }}
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted small">
            Invited teammates sign in with Google using the invited email, then
            open the invite link to join this workspace.
          </p>
        </section>
      )}
    </div>
  );
}
