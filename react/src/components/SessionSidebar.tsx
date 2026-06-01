import { SessionList } from "./SessionList";

interface SessionSidebarProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  refreshTrigger?: number;
}

export function SessionSidebar({
  onSelectSession,
  selectedTaskId,
  refreshTrigger,
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
      />
    </aside>
  );
}

export default SessionSidebar;
