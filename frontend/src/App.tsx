import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Meeting, User, Workspace } from "./types";
import { AskPanel } from "./components/AskPanel";
import { CalendarPanel } from "./components/CalendarPanel";
import { InviteBotBar } from "./components/InviteBotBar";
import { LoginScreen } from "./components/LoginScreen";
import { MeetingList } from "./components/MeetingList";
import { MeetingView } from "./components/MeetingView";
import { NewMeetingPanel } from "./components/NewMeetingPanel";
import { SearchBar } from "./components/SearchBar";
import { SettingsPanel } from "./components/SettingsPanel";
import { SharedMeetingView } from "./components/SharedMeetingView";
import { WorkspaceBar } from "./components/WorkspaceBar";

type View =
  | { kind: "meeting"; id: string }
  | { kind: "settings" }
  | { kind: "calendar" }
  | { kind: "ask" }
  | { kind: "home" };

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

        // Accept a pending invite passed as /?invite=TOKEN
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
    setView({ kind: "home" });
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

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-logo">நீ</span>
          <div>
            <h1>Neu AI</h1>
            <p>தமிழ் · English · Tanglish</p>
          </div>
        </div>

        <WorkspaceBar
          user={user!}
          workspaces={workspaces}
          currentId={workspaceId}
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
          onOpenSettings={() => setView({ kind: "settings" })}
          onLogout={async () => {
            await api.logout();
            window.location.reload();
          }}
        />

        {workspace?.role !== "viewer" && (
          <>
            <NewMeetingPanel workspaceId={workspaceId ?? undefined} onCreated={refreshMeetings} />
            <InviteBotBar
              workspaceId={workspaceId ?? undefined}
              onInvited={refreshMeetings}
              onOpenCalendar={() => setView({ kind: "calendar" })}
            />
          </>
        )}
        <SearchBar onSelect={(id) => setView({ kind: "meeting", id })} />

        <button
          className="ask-link"
          onClick={() => setView({ kind: "ask" })}
        >
          ✨ Ask across all meetings
        </button>

        {error && <div className="error-banner">{error}</div>}

        <MeetingList
          meetings={meetings}
          selectedId={view.kind === "meeting" ? view.id : null}
          onSelect={(id) => setView({ kind: "meeting", id })}
          onDelete={async (id) => {
            await api.deleteMeeting(id);
            if (view.kind === "meeting" && view.id === id) setView({ kind: "home" });
            refreshMeetings();
          }}
        />
      </aside>

      <main className="main">
        {view.kind === "meeting" && (
          <MeetingView
            meetingId={view.id}
            key={view.id}
            canEdit={workspace?.role !== "viewer"}
          />
        )}
        {view.kind === "calendar" && (
          <CalendarPanel
            workspaceId={workspaceId ?? undefined}
            onJoined={refreshMeetings}
            onClose={() => setView({ kind: "home" })}
          />
        )}
        {view.kind === "ask" && (
          <AskPanel
            workspaceId={workspaceId ?? undefined}
            onOpenMeeting={(id) => setView({ kind: "meeting", id })}
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
        {view.kind === "home" && (
          <div className="empty-state">
            <h2>Your AI meeting assistant for Tamil, English &amp; Tanglish</h2>
            <p>
              Upload a recording or record live. Neu transcribes it, tags each
              utterance as தமிழ், English, or Tanglish, and writes a bilingual
              summary with action items &amp; decisions. Then chat with the
              meeting in whichever language you like.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
