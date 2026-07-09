export type MeetingStatus =
  | "uploaded"
  | "transcribing"
  | "summarizing"
  | "completed"
  | "failed";

export type Language = "tamil" | "english" | "tanglish" | "mixed";

export interface Meeting {
  id: string;
  title: string;
  status: MeetingStatus;
  error: string | null;
  language: Language | null;
  duration_seconds: number | null;
  progress: number;
  stage: string | null;
  created_at: string;
}

export interface Segment {
  id: string;
  start: number;
  end: number;
  speaker: string | null;
  text: string;
  language: Language | null;
}

export interface ActionItem {
  task: string;
  owner: string;
  due: string;
}

export interface Summary {
  overview_en: string | null;
  overview_ta: string | null;
  key_points: string[] | null;
  action_items: ActionItem[] | null;
  decisions: string[] | null;
  topics: string[] | null;
  sentiment: string | null;
  language_breakdown: Record<string, number> | null;
}

export interface MeetingDetail extends Meeting {
  segments: Segment[];
  summary: Summary | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SearchHit {
  meeting_id: string;
  meeting_title: string;
  segment_id: string | null;
  snippet: string;
  start: number | null;
}
