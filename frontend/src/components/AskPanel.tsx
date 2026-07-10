import { useRef, useState } from "react";
import { api } from "../api";
import type { AskResponse } from "../types";

const SUGGESTIONS = [
  "What are all my open action items?",
  "Indha week enna decisions eduthom?",
  "Summarize everything about the payment gateway",
  "எல்லா மீட்டிங்கிலும் என்ன முக்கிய முடிவுகள்?",
];

export function AskPanel({
  workspaceId,
  onOpenMeeting,
  onClose,
}: {
  workspaceId?: string;
  onOpenMeeting: (id: string) => void;
  onClose: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    setAsked(q);
    try {
      setResult(await api.ask(q, workspaceId));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ask-panel">
      <header className="meeting-header">
        <div>
          <h2>Ask across all meetings</h2>
          <p className="muted small">
            One question, answered from every meeting in this workspace — with citations.
          </p>
        </div>
        <button className="btn" onClick={onClose}>
          ← Back
        </button>
      </header>

      <form
        className="ask-input"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <input
          ref={inputRef}
          type="text"
          placeholder="Ask in Tamil, English, or Tanglish…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <button className="btn primary" type="submit" disabled={busy || !question.trim()}>
          Ask
        </button>
      </form>

      {!asked && !busy && (
        <div className="chat-suggestions">
          <p className="muted">Try one of these:</p>
          {SUGGESTIONS.map((s) => (
            <button key={s} className="suggestion" onClick={() => ask(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      {asked && (
        <div className="ask-result">
          <div className="ask-question">{asked}</div>
          {busy && <div className="chat-bubble assistant thinking">Neu is reading your meetings…</div>}
          {error && <div className="error-banner">{error}</div>}
          {result && (
            <>
              <div className="chat-bubble assistant ask-answer">{result.answer}</div>
              {result.sources.length > 0 && (
                <div className="ask-sources">
                  <span className="muted small">Sources:</span>
                  {result.sources.map((s) => (
                    <button
                      key={s.meeting_id}
                      className="source-chip"
                      onClick={() => onOpenMeeting(s.meeting_id)}
                    >
                      {s.title} · {s.date}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
