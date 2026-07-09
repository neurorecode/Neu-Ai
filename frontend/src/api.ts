import type {
  CalendarEvent,
  CalendarStatus,
  ChatMessage,
  Invite,
  Meeting,
  MeetingDetail,
  Member,
  SearchHit,
  Segment,
  User,
  Workspace,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // --- auth ---
  authConfig: () => request<{ auth_enabled: boolean }>("/api/auth/config"),
  me: () => request<User>("/api/auth/me"),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),

  // --- workspaces ---
  listWorkspaces: () => request<Workspace[]>("/api/workspaces"),
  createWorkspace: (name: string) =>
    request<Workspace>("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  updateWorkspace: (id: string, patch: Partial<Workspace>) =>
    request<Workspace>(`/api/workspaces/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  listMembers: (workspaceId: string) =>
    request<Member[]>(`/api/workspaces/${workspaceId}/members`),
  removeMember: (workspaceId: string, memberId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/members/${memberId}`, { method: "DELETE" }),
  listInvites: (workspaceId: string) =>
    request<Invite[]>(`/api/workspaces/${workspaceId}/invites`),
  createInvite: (workspaceId: string, email: string, role: string) =>
    request<Invite>(`/api/workspaces/${workspaceId}/invites`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, role }),
    }),
  revokeInvite: (workspaceId: string, inviteId: string) =>
    request<void>(`/api/workspaces/${workspaceId}/invites/${inviteId}`, { method: "DELETE" }),
  acceptInvite: (token: string) =>
    request<Workspace>(`/api/invites/${token}/accept`, { method: "POST" }),

  // --- meeting bot & calendar ---
  inviteBot: (meetingUrl: string, title: string, workspaceId?: string) =>
    request<Meeting>("/api/meetings/invite-bot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ meeting_url: meetingUrl, title, workspace_id: workspaceId }),
    }),
  calendarStatus: () => request<CalendarStatus>("/api/calendar/status"),
  calendarEvents: () => request<CalendarEvent[]>("/api/calendar/events"),
  setAutoJoin: (autoJoin: "none" | "video") =>
    request<CalendarStatus>("/api/calendar/auto-join", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ auto_join: autoJoin }),
    }),

  // --- meetings ---
  listMeetings: (workspaceId?: string) =>
    request<Meeting[]>(
      workspaceId ? `/api/meetings?workspace_id=${workspaceId}` : "/api/meetings",
    ),

  getMeeting: (id: string) => request<MeetingDetail>(`/api/meetings/${id}`),

  deleteMeeting: (id: string) =>
    request<void>(`/api/meetings/${id}`, { method: "DELETE" }),

  uploadMeeting: (
    title: string,
    file: File | Blob,
    filename: string,
    workspaceId?: string,
  ) => {
    const form = new FormData();
    form.append("title", title);
    form.append("file", file, filename);
    if (workspaceId) form.append("workspace_id", workspaceId);
    return request<Meeting>("/api/meetings", { method: "POST", body: form });
  },

  enableShare: (meetingId: string) =>
    request<{ share_token: string | null }>(`/api/meetings/${meetingId}/share`, {
      method: "POST",
    }),
  disableShare: (meetingId: string) =>
    request<{ share_token: string | null }>(`/api/meetings/${meetingId}/share`, {
      method: "DELETE",
    }),
  getShared: (token: string) => request<MeetingDetail>(`/api/shared/${token}`),
  audioUrl: (meetingId: string) => `/api/meetings/${meetingId}/audio`,
  sharedAudioUrl: (token: string) => `/api/shared/${token}/audio`,

  editSegment: (meetingId: string, segmentId: string, text: string) =>
    request<Segment>(`/api/meetings/${meetingId}/segments/${segmentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  renameSpeaker: (meetingId: string, fromName: string, toName: string) =>
    request<Segment[]>(`/api/meetings/${meetingId}/speakers/rename`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ from_name: fromName, to_name: toName }),
    }),

  resummarize: (meetingId: string) =>
    request<Meeting>(`/api/meetings/${meetingId}/resummarize`, { method: "POST" }),

  search: (q: string) =>
    request<SearchHit[]>(`/api/meetings/search?q=${encodeURIComponent(q)}`),

  getChat: (meetingId: string) =>
    request<ChatMessage[]>(`/api/meetings/${meetingId}/chat`),

  sendChat: (meetingId: string, message: string) =>
    request<ChatMessage>(`/api/meetings/${meetingId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }),
};
