import type { Session } from "../services/api";
import { SessionList } from "./SessionList";

interface SessionSidebarProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  refreshTrigger?: number;
  sessions: Session[];
  setSessions: (sessions: Session[] | ((prev: Session[]) => Session[])) => void;
}

export function SessionSidebar({
  onSelectSession,
  selectedTaskId,
  refreshTrigger,
  sessions,
  setSessions,
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
      />
    </aside>
  );
}

export default SessionSidebar;
