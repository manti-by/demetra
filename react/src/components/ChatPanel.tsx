import { useCallback, useEffect, useRef, useState } from "react";
import { Loader } from "./Loader";
import { LogConsole, type SessionStatusData } from "./LogConsole";
import { MarkdownContent } from "./MarkdownContent";
import { SessionStateFlow } from "./SessionStateFlow";
import {
  getChat,
  postChatMessage,
  postQuestionAnswer,
  rerunChat,
  type ChatDetail,
  type ChatMessage,
  type ChatMessageKind,
} from "../services/api";

const POLL_INTERVAL = 5000;

const MESSAGE_LABELS: Record<string, string> = {
  question: "Question",
  answer: "Answer",
  plan: "Build plan",
  failure: "Failure",
  research: "Research report",
  status: "Status",
};

const MARKDOWN_MESSAGE_KINDS: ChatMessageKind[] = [
  "message",
  "plan",
  "question",
  "research",
];

function shouldRenderMarkdown(message: ChatMessage): boolean {
  return MARKDOWN_MESSAGE_KINDS.includes(message.kind);
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}

const FAILURE_TITLE_FALLBACK = "Failure";

export function splitFailureBody(body: string): {
  title: string;
  detail: string;
} {
  const trimmed = body.trim();
  const breakIndex = trimmed.indexOf("\n");
  const firstLine = breakIndex === -1 ? trimmed : trimmed.slice(0, breakIndex);
  const title = firstLine.replace(/^#+\s*/, "").trim();
  const detail = breakIndex === -1 ? "" : trimmed.slice(breakIndex + 1).trim();
  return { title: title || FAILURE_TITLE_FALLBACK, detail };
}

export const MessageBubble = ({ message }: { message: ChatMessage }) => {
  const label = MESSAGE_LABELS[message.kind];
  const failure =
    message.kind === "failure" ? splitFailureBody(message.body) : null;
  const collapsible = failure !== null && failure.detail.length > 0;
  const markdown = shouldRenderMarkdown(message);
  return (
    <div
      className={`chat-message ${message.is_system ? "system" : "user"} kind-${message.kind}`}
    >
      <div className="chat-message-meta">
        <span className="chat-message-author">
          {message.is_system ? "Demetra" : "You"}
        </span>
        {label && <span className="chat-message-kind">{label}</span>}
        <span className="chat-message-time">
          {formatTime(message.created_at)}
        </span>
      </div>
      {collapsible ? (
        <details className="chat-message-details">
          <summary className="chat-message-summary">{failure.title}</summary>
          <div className="chat-message-body">{failure.detail}</div>
        </details>
      ) : markdown ? (
        <MarkdownContent
          content={message.body}
          className="chat-message-body chat-markdown"
        />
      ) : (
        <div className="chat-message-body">
          {failure ? failure.title : message.body}
        </div>
      )}
    </div>
  );
};

const RERUN_STEPS = ["awaiting_input", "failed"];

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
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const [answering, setAnswering] = useState<Record<string, boolean>>({});
  const requestIdRef = useRef(0);
  const deletingTaskIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    requestIdRef.current += 1;
    setDraft("");
    setAnswerDrafts({});
    setAnswering({});
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

  const handleAnswer = useCallback(
    async (questionId: string) => {
      const body = answerDrafts[questionId]?.trim();
      if (!body) return;
      setActionError(null);
      setAnswering((previous) => ({ ...previous, [questionId]: true }));
      try {
        await postQuestionAnswer(taskId, questionId, body);
        setAnswerDrafts((previous) => ({ ...previous, [questionId]: "" }));
        await load();
      } catch (e) {
        setActionError(e instanceof Error ? e.message : "Failed to send answer");
      } finally {
        setAnswering((previous) => ({ ...previous, [questionId]: false }));
      }
    },
    [answerDrafts, load, taskId],
  );

  const handleRerun = useCallback(async () => {
    setActionError(null);
    try {
      await rerunChat(taskId);
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to rerun chat");
    }
  }, [taskId, load]);

  const handleDeleteSession = useCallback(
    async (id: string) => {
      if (!onDeleteSession || deletingTaskIdsRef.current.has(id)) return;
      deletingTaskIdsRef.current.add(id);
      try {
        await onDeleteSession(id);
      } finally {
        deletingTaskIdsRef.current.delete(id);
      }
    },
    [onDeleteSession],
  );

  const step = detail?.session?.step ?? "initial";
  const isResearch = detail?.session?.is_research ?? false;
  const feedbackLoops = detail?.session?.feedback_loops ?? null;
  const canRerun = RERUN_STEPS.includes(step);
  const questionIds = new Set(
    (detail?.messages ?? [])
      .filter((message) => message.kind === "question")
      .map((message) => message.id),
  );

  return (
    <div className="chat-panel">
      {actionError && <div className="chat-error">{actionError}</div>}
      {loadError && <div className="chat-error">{loadError}</div>}

      <div className="chat-panel-body">
        {(onShowLogsToggle || canRerun || onDeleteSession) && (
          <div className="chat-topbar-actions">
            {onShowLogsToggle && (
              <button type="button" className="btn-secondary" onClick={onShowLogsToggle}>
                {showLogs ? "Hide logs" : "Show logs"}
              </button>
            )}
            {canRerun && (
              <button type="button" className="btn-primary" onClick={handleRerun}>
                Re-run
              </button>
            )}
            {onDeleteSession && (
              <button
                type="button"
                className="btn-secondary chat-delete-btn"
                onClick={() => handleDeleteSession(taskId)}
              >
                Delete
              </button>
            )}
          </div>
        )}

        {!detail ? (
          <Loader size={48} />
        ) : (
          <>
            <div className="chat-header">
              <h1 className="chat-title">
                {detail.chat.id}: {detail.chat.title}
              </h1>
              <div className="chat-meta">
                <span className={`session-step ${step}`}>{step}</span>
                {detail.chat.project_name && (
                  <span className="session-project">
                    {detail.chat.project_name}
                  </span>
                )}
                {detail.chat.tags.map((tag) => (
                  <span key={tag} className="chat-tag">
                    {tag}
                  </span>
                ))}
              </div>
              <SessionStateFlow
                step={step}
                isResearch={isResearch}
                feedbackLoops={feedbackLoops}
              />
            </div>

            <div className="chat-description">
              <span className="chat-description-label">Description</span>
              <MarkdownContent
                content={detail.chat.description}
                className="chat-description-text chat-markdown"
              />
            </div>

            <div className="chat-thread">
              {detail.messages.length === 0 ? (
                <div className="chat-empty">No messages yet.</div>
              ) : (
                detail.messages.map((message) => {
                  if (
                    message.kind === "answer" &&
                    message.related_id &&
                    questionIds.has(message.related_id)
                  ) {
                    return null;
                  }
                  if (message.kind !== "question") {
                    return <MessageBubble key={message.id} message={message} />;
                  }
                  const answers = detail.messages.filter(
                    (candidate) =>
                      candidate.kind === "answer" && candidate.related_id === message.id,
                  );
                  const draftValue = answerDrafts[message.id] ?? "";
                  const pending = answering[message.id] ?? false;
                  return (
                    <div className="chat-question-row" key={message.id}>
                      <div className="chat-question-content">
                        <MessageBubble message={message} />
                      </div>
                      <div className="chat-answer-form">
                        <input
                          className="form-input chat-answer-input"
                          placeholder="Your answer..."
                          value={draftValue}
                          onChange={(e) =>
                            setAnswerDrafts((previous) => ({
                              ...previous,
                              [message.id]: e.target.value,
                            }))
                          }
                        />
                        <button
                          type="button"
                          className="btn-primary chat-answer-submit"
                          onClick={() => handleAnswer(message.id)}
                          disabled={pending || !draftValue.trim()}
                        >
                          {pending ? "Sending..." : "Answer"}
                        </button>
                      </div>
                      {answers.length > 0 && (
                        <div className="chat-answer-list">
                          {answers.map((answer) => (
                            <MessageBubble key={answer.id} message={answer} />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            <div className="chat-composer">
              <textarea
                className="form-input chat-composer-input"
                placeholder="Reply to the workflow..."
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={3}
              />
              <button
                  type="button"
                className="btn-primary"
                onClick={handleSend}
                disabled={sending || !draft.trim()}
              >
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
            feedbackLoops={feedbackLoops}
            onDeleteSession={onDeleteSession ? handleDeleteSession : undefined}
            onSessionStatus={onSessionStatus}
            showFlow={false}
          />
        </div>
      )}
    </div>
  );
}

export default ChatPanel;
