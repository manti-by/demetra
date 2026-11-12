import { useEffect, useState, useCallback, useMemo, memo } from "react";
import { getLiveSessionIds, getSessions, type Session } from "../services/api";
import { Loader } from "./Loader";

const POLL_INTERVAL = 60000;
const LIVE_POLL_INTERVAL = 5000;

const TERMINAL_STEPS = new Set(["completed", "researched"]);

const isTerminalStep = (step: string | null | undefined): boolean =>
  TERMINAL_STEPS.has(step ?? "");

interface SessionListProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  refreshTrigger?: number;
  sessions: Session[];
  setSessions: (sessions: Session[] | ((prev: Session[]) => Session[])) => void;
}

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
};

const SessionItem = memo(
  ({
    session,
    isSelected,
    isLive,
    onClick,
  }: {
    session: Session;
    isSelected: boolean;
    isLive: boolean;
    onClick: (e: React.MouseEvent) => void;
  }) => {
    const step = session.step || "initial";
    const isChat = session.kind === "chat";

    return (
      <div
        className={`session-item${isSelected ? " selected" : ""}${isLive ? " live" : ""}`}
        onClick={onClick}
      >
        <div className="session-item-header">
          <div className="session-item-badges">
            <span
              className={`session-type ${isChat ? "chat" : "linear"}`}
              title={isChat ? "Chat" : "Linear"}
            >
              {isChat ? "C" : "L"}
            </span>
            <span
              className={`session-step ${step}`}
              title={isLive ? "Live — running" : undefined}
            >
              {step}
            </span>
          </div>
          <span className="session-time">{formatDate(session.created_at)}</span>
        </div>
        <div className="session-title">
          {session.name || session.session_id?.slice(0, 8)}
        </div>
        <div className="session-item-meta">
          {session.project_name && (
            <span className="session-project">{session.project_name}</span>
          )}
          {(session.tags ?? []).map((tag) => (
            <span key={tag} className="session-tag">
              {tag}
            </span>
          ))}
        </div>
      </div>
    );
  },
);

export function SessionList({
  onSelectSession,
  selectedTaskId,
  refreshTrigger,
  sessions,
  setSessions,
}: SessionListProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [liveTaskIds, setLiveTaskIds] = useState<Set<string>>(new Set());

  const fetchSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch sessions");
    } finally {
      setLoading(false);
    }
  }, [setSessions]);

  const fetchLiveSessions = useCallback(async () => {
    try {
      const taskIds = await getLiveSessionIds();
      setLiveTaskIds(new Set(taskIds));
    } catch {
      // A failed live poll must not break the list; drop the flag instead of
      // showing a stale "live" badge.
      setLiveTaskIds(new Set());
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchSessions();
    const interval = setInterval(fetchSessions, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchSessions, refreshTrigger]);

  useEffect(() => {
    fetchLiveSessions();
    const interval = setInterval(fetchLiveSessions, LIVE_POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchLiveSessions]);

  useEffect(() => {
    if (sessions.length > 0 && !selectedTaskId) {
      const linearSessions = sessions.filter((session) => !session.chat_id);
      const firstLinear =
        linearSessions.find((session) => !isTerminalStep(session.step)) ??
        linearSessions[0];
      if (firstLinear) onSelectSession(firstLinear.task_id);
    }
  }, [sessions, selectedTaskId, onSelectSession]);

  const handleSelectSession = useCallback(
    (e: React.MouseEvent, session: Session) => {
      e.preventDefault();
      onSelectSession(session.task_id);
    },
    [onSelectSession],
  );

  const tags = useMemo(() => {
    const found = new Set<string>();
    for (const session of sessions) {
      for (const tag of session.tags ?? []) found.add(tag);
    }
    return Array.from(found).sort((left, right) => left.localeCompare(right));
  }, [sessions]);

  const filteredSessions = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sessions.filter((session) => {
      if (activeTag && !(session.tags ?? []).includes(activeTag)) return false;
      if (!q) return true;
      return [
        session.name,
        session.task_id,
        session.session_id,
        session.step,
        session.build_plan,
        session.project_name,
        ...(session.tags ?? []),
      ].some((value) => (value ?? "").toLowerCase().includes(q));
    });
  }, [sessions, query, activeTag]);

  const { activeSessions, completedSessions } = useMemo(() => {
    const active: Session[] = [];
    const completed: Session[] = [];
    for (const session of filteredSessions) {
      if (isTerminalStep(session.step)) completed.push(session);
      else active.push(session);
    }
    return { activeSessions: active, completedSessions: completed };
  }, [filteredSessions]);

  const renderSession = (session: Session) => (
    <SessionItem
      key={session.task_id}
      session={session}
      isSelected={selectedTaskId === session.task_id}
      isLive={liveTaskIds.has(session.task_id)}
      onClick={(e) => handleSelectSession(e, session)}
    />
  );

  return (
    <div className="session-list-root">
      <div className="session-search">
        <input
          className="form-input session-search-input"
          type="search"
          placeholder="Search sessions..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      {tags.length > 0 && (
        <div className="session-tag-filter">
          <button
            className={`session-tag-filter-btn${activeTag === null ? " active" : ""}`}
            onClick={() => setActiveTag(null)}
          >
            All
          </button>
          {tags.map((tag) => (
            <button
              key={tag}
              className={`session-tag-filter-btn${activeTag === tag ? " active" : ""}`}
              onClick={() =>
                setActiveTag((current) => (current === tag ? null : tag))
              }
            >
              {tag}
            </button>
          ))}
        </div>
      )}
      <div className="session-list">
        {loading && sessions.length === 0 ? (
          <Loader size={36} />
        ) : error ? (
          <div className="session-list-error">{error}</div>
        ) : sessions.length === 0 ? (
          <div className="session-list-empty">No sessions found</div>
        ) : filteredSessions.length === 0 ? (
          <div className="session-list-empty">No matching sessions</div>
        ) : (
          <>
            {activeSessions.map(renderSession)}
            {activeSessions.length > 0 && completedSessions.length > 0 && (
              <hr className="session-list-divider" />
            )}
            {completedSessions.map(renderSession)}
          </>
        )}
      </div>
    </div>
  );
}

export default SessionList;
