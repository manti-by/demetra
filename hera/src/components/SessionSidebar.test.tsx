import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SessionSidebar } from './SessionSidebar';

vi.mock('./SessionList', () => ({
  SessionList: ({ onSelectSession, selectedTaskId }: { onSelectSession: (taskId: string) => void; selectedTaskId: string | null }) => (
    <div data-testid="session-list">
      <button onClick={() => onSelectSession('test-task-id')}>Select Test Task</button>
      <span data-testid="selected-task">{selectedTaskId}</span>
    </div>
  ),
}));

describe('SessionSidebar', () => {
  it('renders minimized state correctly', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={true}
        onToggleMinimize={vi.fn()}
      />
    );
    
    const sidebar = screen.getByRole('complementary');
    expect(sidebar).toHaveClass('minimized');
    expect(sidebar).not.toHaveClass('expanded');
  });

  it('renders expanded state correctly', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={false}
        onToggleMinimize={vi.fn()}
      />
    );
    
    const sidebar = screen.getByRole('complementary');
    expect(sidebar).toHaveClass('expanded');
    expect(sidebar).not.toHaveClass('minimized');
  });

  it('hides SessionList when minimized', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={true}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.queryByTestId('session-list')).not.toBeInTheDocument();
  });

  it('shows SessionList when expanded', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={false}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.getByTestId('session-list')).toBeInTheDocument();
  });

  it('calls onToggleMinimize when toggle button is clicked', async () => {
    const onToggleMinimize = vi.fn();
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={false}
        onToggleMinimize={onToggleMinimize}
      />
    );
    
    const toggleButton = screen.getByLabelText('Minimize sidebar');
    toggleButton.click();
    
    expect(onToggleMinimize).toHaveBeenCalled();
  });

  it('shows Sessions title when expanded', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={false}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.getByText('Sessions')).toBeInTheDocument();
  });

  it('passes selectedTaskId to SessionList', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId="test-task-123"
        isMinimized={false}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.getByTestId('selected-task')).toHaveTextContent('test-task-123');
  });

  it('has toggle button with expand label when minimized', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={true}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.getByLabelText('Expand sidebar')).toBeInTheDocument();
  });

  it('has toggle button with minimize label when expanded', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        isMinimized={false}
        onToggleMinimize={vi.fn()}
      />
    );
    
    expect(screen.getByLabelText('Minimize sidebar')).toBeInTheDocument();
  });
});
