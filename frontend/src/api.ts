import type { ChatMessage, Meeting, MeetingDetail, SearchHit, Segment } from "./types";

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
  listMeetings: () => request<Meeting[]>("/api/meetings"),

  getMeeting: (id: string) => request<MeetingDetail>(`/api/meetings/${id}`),

  deleteMeeting: (id: string) =>
    request<void>(`/api/meetings/${id}`, { method: "DELETE" }),

  uploadMeeting: (title: string, file: File | Blob, filename: string) => {
    const form = new FormData();
    form.append("title", title);
    form.append("file", file, filename);
    return request<Meeting>("/api/meetings", { method: "POST", body: form });
  },

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
