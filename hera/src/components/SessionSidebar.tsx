import { SessionList } from './SessionList';

interface SessionSidebarProps {
  onSelectSession: (taskId: string) => void;
  selectedTaskId: string | null;
  isMinimized: boolean;
  onToggleMinimize: () => void;
}

const MenuIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);

const ChevronIcon = ({ direction }: { direction: 'left' | 'right' }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    style={{ transform: direction === 'left' ? 'rotate(180deg)' : 'none' }}
  >
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

export function SessionSidebar({ onSelectSession, selectedTaskId, isMinimized, onToggleMinimize }: SessionSidebarProps) {
  return (
    <aside className={`session-sidebar ${isMinimized ? 'minimized' : 'expanded'}`}>
      <div className="sidebar-header">
        {!isMinimized && <span className="sidebar-title">Sessions</span>}
        <button className="sidebar-toggle" onClick={onToggleMinimize} aria-label={isMinimized ? 'Expand sidebar' : 'Minimize sidebar'}>
          {isMinimized ? <MenuIcon /> : <ChevronIcon direction="left" />}
        </button>
      </div>
      {!isMinimized && (
        <SessionList onSelectSession={onSelectSession} selectedTaskId={selectedTaskId} />
      )}
    </aside>
  );
}

export default SessionSidebar;
