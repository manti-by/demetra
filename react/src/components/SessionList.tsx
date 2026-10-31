import { useEffect, useState, useCallback, useMemo, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { getSessions, type Session } from '../services/api';
import { Loader } from './Loader';

const POLL_INTERVAL = 60000;

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

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
};

const SessionItem = memo(({ session, isSelected, onClick }: { session: Session; isSelected: boolean; onClick: (e: React.MouseEvent) => void }) => (
  <div className={`session-item ${isSelected ? 'selected' : ''}`} onClick={onClick}>
    <div className="session-item-header">
      <span className={`session-dot step-${session.step || 'initial'}`} />
      <span className="session-title">
        {session.name || session.session_id?.slice(0, 8)}
      </span>
      {Boolean(session.chat_id) && <span className="session-chat-badge">chat</span>}
      <span className={`session-step ${session.step || 'initial'}`}>
        {session.step || 'initial'}
      </span>
    </div>
    <div className="session-item-meta">
      <span className="session-time">{formatDate(session.created_at)}</span>
      {(session.tags ?? []).map((tag) => (
        <span key={tag} className="session-tag">{tag}</span>
      ))}
      {session.build_plan && <span className="session-plan">{session.build_plan}</span>}
    </div>
  </div>
));

export function SessionList({ onSelectSession, selectedTaskId, refreshTrigger, sessions, setSessions }: SessionListProps) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch sessions');
    } finally {
      setLoading(false);
    }
  }, [setSessions]);

  useEffect(() => {
    setLoading(true);
    fetchSessions();
    const interval = setInterval(fetchSessions, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchSessions, refreshTrigger]);

  useEffect(() => {
    if (sessions.length > 0 && !selectedTaskId) {
      const firstLinear = sessions.find((session) => !session.chat_id);
      if (firstLinear) onSelectSession(firstLinear.task_id);
    }
  }, [sessions, selectedTaskId, onSelectSession]);

  const handleSelectSession = useCallback((e: React.MouseEvent, session: Session) => {
    e.preventDefault();
    if (session.chat_id) {
      navigate(`/chats/${session.task_id}`);
      return;
    }
    onSelectSession(session.task_id);
  }, [navigate, onSelectSession]);

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
      return [session.name, session.task_id, session.session_id, session.step, session.build_plan].some(
        (value) => (value ?? '').toLowerCase().includes(q),
      );
    });
  }, [sessions, query, activeTag]);

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
            className={`session-tag-filter-btn${activeTag === null ? ' active' : ''}`}
            onClick={() => setActiveTag(null)}
          >
            All
          </button>
          {tags.map((tag) => (
            <button
              key={tag}
              className={`session-tag-filter-btn${activeTag === tag ? ' active' : ''}`}
              onClick={() => setActiveTag((current) => (current === tag ? null : tag))}
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
          filteredSessions.map((session) => (
            <SessionItem
              key={session.task_id}
              session={session}
              isSelected={selectedTaskId === session.task_id}
              onClick={(e) => handleSelectSession(e, session)}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default SessionList;
