import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Header } from "../components/Header";
import { Loader } from "../components/Loader";
import { LogConsole } from "../components/LogConsole";
import { SessionStateFlow } from "../components/SessionStateFlow";
import { useAuth } from "../contexts/AuthContext";
import {
  getChat,
  postChatMessage,
  updateChat,
  type ChatDetail,
  type ChatMessage,
} from "../services/api";

const POLL_INTERVAL = 5000;

const MESSAGE_LABELS: Record<string, string> = {
  question: "Question",
  plan: "Build plan",
  failure: "Failure",
  research: "Research report",
  status: "Status",
};

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

const MessageBubble = ({ message }: { message: ChatMessage }) => {
  const label = MESSAGE_LABELS[message.kind];
  return (
    <div className={`chat-message ${message.is_system ? "system" : "user"} kind-${message.kind}`}>
      <div className="chat-message-meta">
        <span className="chat-message-author">{message.is_system ? "Demetra" : "You"}</span>
        {label && <span className="chat-message-kind">{label}</span>}
        <span className="chat-message-time">{formatTime(message.created_at)}</span>
      </div>
      <div className="chat-message-body">{message.body}</div>
    </div>
  );
};

export function ChatPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { user, loading, logout } = useAuth();
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [savingDescription, setSavingDescription] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!taskId) return;
      try {
        const data = await getChat(taskId, signal);
        setDetail(data);
        setDescription(data.chat.description);
        setError(null);
      } catch (e) {
        if (signal?.aborted) return;
        setError(e instanceof Error ? e.message : "Failed to load chat");
      }
    },
    [taskId],
  );

  useEffect(() => {
    load();
    const interval = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (threadEndRef.current && typeof threadEndRef.current.scrollIntoView === "function") {
      threadEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [detail?.messages.length]);

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  const handleSaveDescription = useCallback(async () => {
    if (!taskId) return;
    setSavingDescription(true);
    try {
      await updateChat(taskId, { description });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save description");
    } finally {
      setSavingDescription(false);
    }
  }, [taskId, description, load]);

  const handleSend = useCallback(async () => {
    if (!taskId || !draft.trim()) return;
    setSending(true);
    try {
      await postChatMessage(taskId, draft);
      setDraft("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }, [taskId, draft, load]);

  const handleRerun = useCallback(async () => {
    if (!taskId) return;
    try {
      await updateChat(taskId, { status: "initial" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to re-run chat");
    }
  }, [taskId, load]);

  if (loading) {
    return <Loader fullScreen size={56} />;
  }

  if (!user) {
    return (
      <div className="chat-page">
        <Header user={null} onLogout={handleLogout} />
        <div className="chat-empty">
          Please <Link to="/">sign in</Link> to view this chat.
        </div>
      </div>
    );
  }

  const step = detail?.session?.step ?? "initial";
  const canRerun = ["awaiting_input", "failed", "completed", "researched"].includes(step);

  return (
    <div className="chat-page">
      <Header user={user} onLogout={handleLogout} />
      <main className="chat-main">
        <div className="chat-topbar">
          <button className="btn-secondary" onClick={() => navigate("/")}>
            Back to sessions
          </button>
          <div className="chat-topbar-actions">
            <button className="btn-secondary" onClick={() => setShowLogs((value) => !value)}>
              {showLogs ? "Hide logs" : "Show logs"}
            </button>
            {canRerun && (
              <button className="btn-primary" onClick={handleRerun}>
                Re-run
              </button>
            )}
          </div>
        </div>

        {error && <div className="chat-error">{error}</div>}

        {!detail ? (
          <Loader size={48} />
        ) : (
          <>
            <div className="chat-header">
              <h1 className="chat-title">{detail.chat.title}</h1>
              <div className="chat-meta">
                <span className={`session-step ${step}`}>{step}</span>
                <span className="chat-task-id">{detail.chat.session_task_id}</span>
                {detail.chat.tags.map((tag) => (
                  <span key={tag} className="chat-tag">
                    {tag}
                  </span>
                ))}
              </div>
              <SessionStateFlow step={step} isResearch={detail.session?.is_research ?? false} />
            </div>

            <div className="chat-description">
              <label className="chat-description-label" htmlFor="chat-description">
                Description
              </label>
              <textarea
                id="chat-description"
                className="form-input chat-description-input"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
              />
              <div className="form-actions">
                <button
                  className="btn-secondary"
                  onClick={handleSaveDescription}
                  disabled={savingDescription || description === detail.chat.description}
                >
                  {savingDescription ? "Saving..." : "Save description"}
                </button>
              </div>
            </div>

            <div className="chat-thread">
              {detail.messages.length === 0 ? (
                <div className="chat-empty">No messages yet.</div>
              ) : (
                detail.messages.map((message) => <MessageBubble key={message.id} message={message} />)
              )}
              <div ref={threadEndRef} />
            </div>

            <div className="chat-composer">
              <textarea
                className="form-input chat-composer-input"
                placeholder="Reply to the workflow..."
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
              />
              <button className="btn-primary" onClick={handleSend} disabled={sending || !draft.trim()}>
                {sending ? "Sending..." : "Send"}
              </button>
            </div>

            {showLogs && (
              <div className="chat-logs">
                <LogConsole
                  taskId={detail.chat.session_task_id}
                  sessionName={detail.chat.title}
                  step={step}
                  isResearch={detail.session?.is_research ?? false}
                  onDeleteSession={() => navigate("/")}
                />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default ChatPage;
