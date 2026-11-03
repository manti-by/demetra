import { useCallback, useEffect, useRef, useState } from "react";
import { Loader } from "./Loader";
import { LogConsole, type SessionStatusData } from "./LogConsole";
import { SessionStateFlow } from "./SessionStateFlow";
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

const FAILURE_TITLE_FALLBACK = "Failure";

export function splitFailureBody(body: string): { title: string; detail: string } {
  const trimmed = body.trim();
  const breakIndex = trimmed.indexOf("\n");
  const firstLine = breakIndex === -1 ? trimmed : trimmed.slice(0, breakIndex);
  const title = firstLine.replace(/^#+\s*/, "").trim();
  const detail = breakIndex === -1 ? "" : trimmed.slice(breakIndex + 1).trim();
  return { title: title || FAILURE_TITLE_FALLBACK, detail };
}

export const MessageBubble = ({ message }: { message: ChatMessage }) => {
  const label = MESSAGE_LABELS[message.kind];
  const failure = message.kind === "failure" ? splitFailureBody(message.body) : null;
  const collapsible = failure !== null && failure.detail.length > 0;
  return (
    <div className={`chat-message ${message.is_system ? "system" : "user"} kind-${message.kind}`}>
      <div className="chat-message-meta">
        <span className="chat-message-author">{message.is_system ? "Demetra" : "You"}</span>
        {label && <span className="chat-message-kind">{label}</span>}
        <span className="chat-message-time">{formatTime(message.created_at)}</span>
      </div>
      {collapsible ? (
        <details className="chat-message-details">
          <summary className="chat-message-summary">{failure.title}</summary>
          <div className="chat-message-body">{failure.detail}</div>
        </details>
      ) : (
        <div className="chat-message-body">{failure ? failure.title : message.body}</div>
      )}
    </div>
  );
};

const RERUN_STEPS = ["awaiting_input", "failed", "completed", "researched"];

interface ChatPanelProps {
  taskId: string;
  showLogs?: boolean;
  onShowLogsToggle?: () => void;
  onDeleteSession?: (taskId: string) => void;
  onSessionStatus?: (taskId: string, data: SessionStatusData) => void;
}

export function ChatPanel({
  taskId,
  showLogs = false,
  onShowLogsToggle,
  onDeleteSession,
  onSessionStatus,
}: ChatPanelProps) {
  const [detail, setDetail] = useState<ChatDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const [savingDescription, setSavingDescription] = useState(false);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement>(null);
  const serverDescriptionRef = useRef<string | null>(null);
  const requestIdRef = useRef(0);

  useEffect(() => {
    serverDescriptionRef.current = null;
    requestIdRef.current += 1;
    setDraft("");
    setLoadError(null);
    setActionError(null);
  }, [taskId]);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const requestId = ++requestIdRef.current;
      try {
        const data = await getChat(taskId, signal);
        if (requestId !== requestIdRef.current) return;
        setDetail(data);
        const previous = serverDescriptionRef.current;
        serverDescriptionRef.current = data.chat.description;
        setDescription((current) =>
          previous === null || current === previous ? data.chat.description : current,
        );
        setLoadError(null);
      } catch (e) {
        if (signal?.aborted || requestId !== requestIdRef.current) return;
        setLoadError(e instanceof Error ? e.message : "Failed to load chat");
      }
    },
    [taskId],
  );

  useEffect(() => {
    setDetail(null);
    load();
    const interval = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    if (threadEndRef.current && typeof threadEndRef.current.scrollIntoView === "function") {
      threadEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [detail?.messages.length]);

  const handleSaveDescription = useCallback(async () => {
    setActionError(null);
    setSavingDescription(true);
    try {
      await updateChat(taskId, { description });
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to save description");
    } finally {
      setSavingDescription(false);
    }
  }, [taskId, description, load]);

  const handleSend = useCallback(async () => {
    if (!draft.trim()) return;
    setActionError(null);
    setSending(true);
    try {
      await postChatMessage(taskId, draft);
      setDraft("");
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }, [taskId, draft, load]);

  const handleRerun = useCallback(async () => {
    setActionError(null);
    try {
      await updateChat(taskId, { status: "initial" });
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to re-run chat");
    }
  }, [taskId, load]);

  const step = detail?.session?.step ?? "initial";
  const isResearch = detail?.session?.is_research ?? false;
  const canRerun = RERUN_STEPS.includes(step);

  return (
    <div className="chat-panel">
      {actionError && <div className="chat-error">{actionError}</div>}
      {loadError && <div className="chat-error">{loadError}</div>}

      <div className="chat-panel-body">
        {(onShowLogsToggle || canRerun) && (
          <div className="chat-topbar-actions">
            {onShowLogsToggle && (
              <button className="btn-secondary" onClick={onShowLogsToggle}>
                {showLogs ? "Hide logs" : "Show logs"}
              </button>
            )}
            {canRerun && (
              <button className="btn-primary" onClick={handleRerun}>
                Re-run
              </button>
            )}
          </div>
        )}

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
              <SessionStateFlow step={step} isResearch={isResearch} />
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
          </>
        )}
      </div>

      {showLogs && (
        <div className="chat-logs">
          <LogConsole
            taskId={taskId}
            sessionName={detail?.chat.title ?? null}
            step={detail?.session?.step ?? null}
            isResearch={isResearch}
            onDeleteSession={onDeleteSession}
            onSessionStatus={onSessionStatus}
            showFlow={false}
          />
        </div>
      )}
    </div>
  );
}

export default ChatPanel;
