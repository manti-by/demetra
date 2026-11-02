import { useNavigate } from "react-router-dom";
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
  const navigate = useNavigate();

  return (
    <aside className="session-sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">Sessions</span>
        <button className="btn-secondary sidebar-new-chat" onClick={() => navigate("/chats/new")}>
          New chat
        </button>
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
