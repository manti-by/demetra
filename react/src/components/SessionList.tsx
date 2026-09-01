import { useEffect, useState, useCallback, useMemo, memo } from 'react';
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
      <span className={`session-step ${session.step || 'initial'}`}>
        {session.step || 'initial'}
      </span>
    </div>
    <div className="session-item-meta">
      <span className="session-time">{formatDate(session.created_at)}</span>
      {session.build_plan && <span className="session-plan">{session.build_plan}</span>}
    </div>
  </div>
));

export function SessionList({ onSelectSession, selectedTaskId, refreshTrigger, sessions, setSessions }: SessionListProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

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
      onSelectSession(sessions[0].task_id);
    }
  }, [sessions, selectedTaskId, onSelectSession]);

  const handleSelectSession = useCallback((e: React.MouseEvent, taskId: string) => {
    e.preventDefault();
    onSelectSession(taskId);
  }, [onSelectSession]);

  const filteredSessions = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((session) =>
      [session.name, session.task_id, session.session_id, session.step, session.build_plan].some(
        (value) => (value ?? '').toLowerCase().includes(q),
      ),
    );
  }, [sessions, query]);

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
              onClick={(e) => handleSelectSession(e, session.task_id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default SessionList;
