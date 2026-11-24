import { useEffect, useState, useCallback, useMemo, useRef, memo } from "react";
import { getLiveSessionIds, getSessions, type Session } from "../services/api";
import { Loader } from "./Loader";

const POLL_INTERVAL = 60000;
const LIVE_POLL_INTERVAL = 5000;

const ACTIVE_WINDOW_MS = 14 * 24 * 60 * 60 * 1000;

const COMPLETED_STEPS = new Set(["completed", "researched"]);

const isCompletedStep = (step: string | null | undefined): boolean =>
  COMPLETED_STEPS.has(step ?? "");

type SessionSection = "active" | "completed" | "backlog";

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

const isStaleSession = (session: Session, now: number): boolean => {
  const updatedAt = new Date(session.updated_at).getTime();
  if (Number.isNaN(updatedAt)) return false;
  return now - updatedAt >= ACTIVE_WINDOW_MS;
};

const sectionOf = (
  session: Session,
  now: number,
  liveTaskIds: Set<string>,
): SessionSection => {
  if (isCompletedStep(session.step)) return "completed";
  if (session.step === "failed") return "backlog";
  if (!liveTaskIds.has(session.task_id) && isStaleSession(session, now)) {
    return "backlog";
  }
  return "active";
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
  const livePollSequence = useRef(0);

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
    // Only the most recent poll may update the flag: a slow request that
    // resolves after a newer one would otherwise restore obsolete state.
    const sequence = ++livePollSequence.current;
    const isLatest = () => sequence === livePollSequence.current;
    try {
      const taskIds = await getLiveSessionIds();
      if (!isLatest()) return;
      setLiveTaskIds(new Set(taskIds));
    } catch {
      if (!isLatest()) return;
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
      const now = Date.now();
      const linearSessions = sessions.filter((session) => !session.chat_id);
      const firstActive = linearSessions.find(
        (session) => sectionOf(session, now, liveTaskIds) === "active",
      );
      const firstLinear = firstActive ?? linearSessions[0];
      if (firstLinear) onSelectSession(firstLinear.task_id);
    }
  }, [sessions, selectedTaskId, onSelectSession, liveTaskIds]);

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

  const { activeSessions, completedSessions, backlogSessions } = useMemo(() => {
    const now = Date.now();
    const active: Session[] = [];
    const completed: Session[] = [];
    const backlog: Session[] = [];
    for (const session of filteredSessions) {
      const section = sectionOf(session, now, liveTaskIds);
      if (section === "completed") completed.push(session);
      else if (section === "backlog") backlog.push(session);
      else active.push(session);
    }
    return {
      activeSessions: active,
      completedSessions: completed,
      backlogSessions: backlog,
    };
  }, [filteredSessions, liveTaskIds]);

  const renderSession = (session: Session) => (
    <SessionItem
      key={session.task_id}
      session={session}
      isSelected={selectedTaskId === session.task_id}
      isLive={liveTaskIds.has(session.task_id)}
      onClick={(e) => handleSelectSession(e, session)}
    />
  );

  const renderSection = (
    title: string,
    sectionSessions: Session[],
    emptyMessage?: string,
  ) => (
    <>
      <div className="session-section-header">
        <span>{title}</span>
        <span className="session-section-count">{sectionSessions.length}</span>
      </div>
      {sectionSessions.length === 0 && emptyMessage ? (
        <div className="session-section-empty">{emptyMessage}</div>
      ) : (
        sectionSessions.map(renderSession)
      )}
    </>
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
          <button type="button"
            className={`session-tag-filter-btn${activeTag === null ? " active" : ""}`}
            onClick={() => setActiveTag(null)}
          >
            All
          </button>
          {tags.map((tag) => (
            <button type="button"
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
            {renderSection("Active", activeSessions, "No active sessions")}
            {completedSessions.length > 0 &&
              renderSection("Completed", completedSessions)}
            {backlogSessions.length > 0 &&
              renderSection("Backlog", backlogSessions)}
          </>
        )}
      </div>
    </div>
  );
}

export default SessionList;
