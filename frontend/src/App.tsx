import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Meeting, User, Workspace } from "./types";
import { AskPanel } from "./components/AskPanel";
import { CalendarPanel } from "./components/CalendarPanel";
import { InviteBotBar } from "./components/InviteBotBar";
import { LoginScreen } from "./components/LoginScreen";
import { MeetingsTable } from "./components/MeetingsTable";
import { MeetingView } from "./components/MeetingView";
import { NewMeetingPanel } from "./components/NewMeetingPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { SharedMeetingView } from "./components/SharedMeetingView";
import { Sidebar, type NavKey } from "./components/Sidebar";
import { BackIcon } from "./components/icons";

type View =
  | { kind: "home" }
  | { kind: "meetings" }
  | { kind: "ask" }
  | { kind: "calendar" }
  | { kind: "settings" }
  | { kind: "meeting"; id: string };

export default function App() {
  // Public share links render without any auth: /share/{token}
  const shareMatch = window.location.pathname.match(/^\/share\/([a-z0-9]+)$/);
  if (shareMatch) {
    return <SharedMeetingView token={shareMatch[1]} />;
  }
  return <AuthedApp />;
}

function AuthedApp() {
  const [user, setUser] = useState<User | null>(null);
  const [authState, setAuthState] = useState<"loading" | "login" | "ready">("loading");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [view, setView] = useState<View>({ kind: "home" });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        setUser(me);

        const inviteToken = new URLSearchParams(window.location.search).get("invite");
        let joined: Workspace | null = null;
        if (inviteToken) {
          try {
            joined = await api.acceptInvite(inviteToken);
          } catch (e) {
            alert(`Could not accept invite: ${(e as Error).message}`);
          }
          window.history.replaceState(null, "", "/");
        }

        const ws = await api.listWorkspaces();
        setWorkspaces(ws);
        const saved = localStorage.getItem("neu_workspace");
        const initial =
          (joined && ws.find((w) => w.id === joined!.id)) ??
          ws.find((w) => w.id === saved) ??
          ws[0];
        setWorkspaceId(initial?.id ?? null);
        setAuthState("ready");
      } catch {
        setAuthState("login");
      }
    })();
  }, []);

  const workspace = workspaces.find((w) => w.id === workspaceId) ?? null;

  const refreshMeetings = useCallback(async () => {
    if (!workspaceId) return;
    try {
      setMeetings(await api.listMeetings(workspaceId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [workspaceId]);

  useEffect(() => {
    refreshMeetings();
  }, [refreshMeetings]);

  useEffect(() => {
    const processing = meetings.some(
      (m) => m.status !== "completed" && m.status !== "failed",
    );
    if (!processing) return;
    const t = setInterval(refreshMeetings, 3000);
    return () => clearInterval(t);
  }, [meetings, refreshMeetings]);

  if (authState === "loading") {
    return <div className="center-screen muted">Loading…</div>;
  }
  if (authState === "login") {
    return <LoginScreen />;
  }

  const activeNav: NavKey = view.kind === "meeting" ? "meetings" : view.kind;
  const canEdit = workspace?.role !== "viewer";

  return (
    <div className="app">
      <Sidebar
        user={user!}
        workspaces={workspaces}
        currentId={workspaceId}
        active={activeNav}
        onNavigate={(key) => setView({ kind: key })}
        onSwitch={(id) => {
          localStorage.setItem("neu_workspace", id);
          setWorkspaceId(id);
        }}
        onCreate={async (name) => {
          const ws = await api.createWorkspace(name);
          setWorkspaces((prev) => [...prev, ws]);
          localStorage.setItem("neu_workspace", ws.id);
          setWorkspaceId(ws.id);
        }}
        onLogout={async () => {
          await api.logout();
          window.location.reload();
        }}
      />

      <main className="main">
        {error && <div className="error-banner">{error}</div>}

        {view.kind === "home" && (
          <div className="page">
            <div className="page-head">
              <div>
                <h2 className="page-title">Home</h2>
                <p className="page-sub">
                  Upload a recording, capture live, or send Neu to a call.
                </p>
              </div>
            </div>
            {canEdit && (
              <div className="home-cards">
                <section className="home-card">
                  <h3>New recording</h3>
                  <p className="muted small">Upload an audio/video file or record from your mic.</p>
                  <NewMeetingPanel
                    workspaceId={workspaceId ?? undefined}
                    onCreated={() => {
                      refreshMeetings();
                      setView({ kind: "meetings" });
                    }}
                  />
                </section>
                <section className="home-card">
                  <h3>Send Neu to a meeting</h3>
                  <p className="muted small">Paste a Meet / Zoom / Teams link and Neu joins to take notes.</p>
                  <InviteBotBar
                    workspaceId={workspaceId ?? undefined}
                    onInvited={() => {
                      refreshMeetings();
                      setView({ kind: "meetings" });
                    }}
                    onOpenCalendar={() => setView({ kind: "calendar" })}
                  />
                </section>
              </div>
            )}
          </div>
        )}

        {view.kind === "meetings" && (
          <MeetingsTable
            meetings={meetings}
            onSelect={(id) => setView({ kind: "meeting", id })}
            onNew={() => setView({ kind: "home" })}
            onDelete={async (id) => {
              await api.deleteMeeting(id);
              refreshMeetings();
            }}
          />
        )}

        {view.kind === "meeting" && (
          <div className="page">
            <button className="back-link" onClick={() => setView({ kind: "meetings" })}>
              <BackIcon size={16} /> Meetings
            </button>
            <MeetingView meetingId={view.id} key={view.id} canEdit={canEdit} />
          </div>
        )}

        {view.kind === "ask" && (
          <AskPanel
            workspaceId={workspaceId ?? undefined}
            onOpenMeeting={(id) => setView({ kind: "meeting", id })}
            onClose={() => setView({ kind: "home" })}
          />
        )}

        {view.kind === "calendar" && (
          <CalendarPanel
            workspaceId={workspaceId ?? undefined}
            onJoined={refreshMeetings}
            onClose={() => setView({ kind: "home" })}
          />
        )}

        {view.kind === "settings" && workspace && (
          <SettingsPanel
            workspace={workspace}
            currentUser={user!}
            onUpdated={(ws) =>
              setWorkspaces((prev) => prev.map((w) => (w.id === ws.id ? { ...w, ...ws } : w)))
            }
            onClose={() => setView({ kind: "home" })}
          />
        )}
      </main>
    </div>
  );
}
