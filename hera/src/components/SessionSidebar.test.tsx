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
  it('renders SessionList by default', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
      />
    );
    
    expect(screen.getByTestId('session-list')).toBeInTheDocument();
  });

  it('shows Sessions title', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
      />
    );
    
    expect(screen.getByText('Sessions')).toBeInTheDocument();
  });

  it('passes selectedTaskId to SessionList', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId="test-task-123"
      />
    );
    
    expect(screen.getByTestId('selected-task')).toHaveTextContent('test-task-123');
  });

  it('calls onSelectSession when SessionList triggers it', () => {
    const onSelectSession = vi.fn();
    render(
      <SessionSidebar
        onSelectSession={onSelectSession}
        selectedTaskId={null}
      />
    );
    
    screen.getByText('Select Test Task').click();
    expect(onSelectSession).toHaveBeenCalledWith('test-task-id');
  });

  it('has toggle button with Sessions label', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
      />
    );
    
    expect(screen.getByLabelText('Sessions')).toBeInTheDocument();
  });
});
