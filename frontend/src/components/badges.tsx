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

// Group the pipeline states into three visual buckets like Leap's pills.
const STATUS_META: Record<MeetingStatus, { label: string; tone: string }> = {
  uploaded: { label: "Queued", tone: "pending" },
  transcribing: { label: "Transcribing", tone: "running" },
  summarizing: { label: "Summarizing", tone: "running" },
  completed: { label: "Complete", tone: "done" },
  failed: { label: "Failed", tone: "failed" },
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "pending" };
  return (
    <span className={`pill pill-${meta.tone}`}>
      <span className="pill-dot" />
      {meta.label}
    </span>
  );
}
