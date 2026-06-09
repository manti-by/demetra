import { useEffect, useState, useCallback, memo } from 'react';
import { getSessions, type Session } from '../services/api';

const POLL_INTERVAL = 60000;

interface SessionListProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  refreshTrigger?: number;
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

export function SessionList({ onSelectSession, selectedTaskId, refreshTrigger }: SessionListProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, []);

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

  return (
    <div className="session-list">
      {loading && sessions.length === 0 ? (
        <div className="session-list-loading">Loading sessions...</div>
      ) : error ? (
        <div className="session-list-error">{error}</div>
      ) : sessions.length === 0 ? (
        <div className="session-list-empty">No sessions found</div>
      ) : (
        sessions.map((session) => (
          <SessionItem
            key={session.task_id}
            session={session}
            isSelected={selectedTaskId === session.task_id}
            onClick={(e) => handleSelectSession(e, session.task_id)}
          />
        ))
      )}
    </div>
  );
}

export default SessionList;
