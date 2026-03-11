import { SessionList } from "./SessionList";

interface SessionSidebarProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
}

export function SessionSidebar({
  onSelectSession,
  selectedTaskId,
}: SessionSidebarProps) {
  return (
    <aside className="session-sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Sessions</span>
      </div>
      <SessionList
        onSelectSession={onSelectSession}
        selectedTaskId={selectedTaskId}
      />
    </aside>
  );
}

export default SessionSidebar;
