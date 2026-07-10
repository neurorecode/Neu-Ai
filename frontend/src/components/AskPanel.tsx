import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { AskSource } from "../types";
import { Markdown } from "./Markdown";

const SUGGESTIONS = [
  "What are all my open action items?",
  "Indha week enna decisions eduthom?",
  "Summarize everything about the payment gateway",
  "எல்லா மீட்டிங்கிலும் என்ன முக்கிய முடிவுகள்?",
];

type Msg = {
  role: "user" | "assistant";
  content: string;
  sources?: AskSource[];
};

export function AskPanel({
  workspaceId,
  onOpenMeeting,
  onClose,
}: {
  workspaceId?: string;
  onOpenMeeting: (id: string) => void;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    setInput("");
    const history = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    try {
      const res = await api.ask(q, history, workspaceId);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
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
          <h2>Ask Neu</h2>
          <p className="muted small">
            A conversation across every meeting in this workspace — with citations.
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {messages.length > 0 && (
            <button className="btn" onClick={() => setMessages([])}>
              New chat
            </button>
          )}
          <button className="btn" onClick={onClose}>
            ← Back
          </button>
        </div>
      </header>

      <div className="chat">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-suggestions">
              <p className="muted">Ask anything across your meetings — in any of the three languages:</p>
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
              {m.sources && m.sources.length > 0 && (
                <div className="ask-sources">
                  <span className="muted small">Sources:</span>
                  {m.sources.map((s) => (
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
            </div>
          ))}

          {busy && <div className="chat-bubble assistant thinking">Neu is reading your meetings…</div>}
          {error && <p className="error small">{error}</p>}
          <div ref={bottomRef} />
        </div>

        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            type="text"
            placeholder="Ask a question or a follow-up…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={busy}
          />
          <button className="btn primary" type="submit" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
