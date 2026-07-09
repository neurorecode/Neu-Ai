import type { Language, MeetingStatus } from "../types";

const LANGUAGE_LABELS: Record<Language, string> = {
  tamil: "தமிழ்",
  english: "English",
  tanglish: "Tanglish",
  mixed: "Mixed",
};

export function LanguageBadge({ language }: { language: Language }) {
  return (
    <span className={`badge lang-${language}`}>{LANGUAGE_LABELS[language] ?? language}</span>
  );
}

const STATUS_LABELS: Record<MeetingStatus, string> = {
  uploaded: "Queued",
  transcribing: "Transcribing…",
  summarizing: "Summarizing…",
  completed: "Ready",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  return <span className={`badge status-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}
