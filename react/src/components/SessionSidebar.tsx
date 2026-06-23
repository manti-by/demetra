import type { Session } from "../services/api";
import { SessionList } from "./SessionList";

interface SessionStatusData {
  step: string;
  name?: string;
}

interface SessionSidebarProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  refreshTrigger?: number;
  sessions: Session[];
  setSessions: (sessions: Session[] | ((prev: Session[]) => Session[])) => void;
  onSessionStatus?: (taskId: string, data: SessionStatusData) => void;
}

export function SessionSidebar({
  onSelectSession,
  selectedTaskId,
  refreshTrigger,
  sessions,
  setSessions,
  onSessionStatus,
}: SessionSidebarProps) {
  return (
    <aside className="session-sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Sessions</span>
      </div>
      <SessionList
        onSelectSession={onSelectSession}
        selectedTaskId={selectedTaskId}
        refreshTrigger={refreshTrigger}
        sessions={sessions}
        setSessions={setSessions}
        onSessionStatus={onSessionStatus}
      />
    </aside>
  );
}

export default SessionSidebar;
