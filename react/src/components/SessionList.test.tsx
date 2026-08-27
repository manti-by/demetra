import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SessionList } from './SessionList';
import { getSessions } from '../services/api';

vi.mock('../services/api', () => ({
  getSessions: vi.fn().mockResolvedValue([]),
  deleteSession: vi.fn(),
}));

describe('SessionList', () => {
  it('renders without crashing', () => {
    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={[]}
        setSessions={vi.fn()}
      />,
    );
    expect(screen.getByAltText('Loading...')).toBeInTheDocument();
  });

  it('displays sessions with step styling', () => {
    const sessions = [
      {
        task_id: 'task-1',
        session_id: 'sess-1',
        name: 'Test Session',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'build',
        pr_link: null,
        linear_link: null,
      },
    ];

    vi.mocked(getSessions).mockResolvedValue(sessions);

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('Test Session')).toBeInTheDocument();
    expect(screen.getByText('build')).toBeInTheDocument();
  });

  it('updates session step when sessions prop changes', () => {
    const sessions = [
      {
        task_id: 'task-1',
        session_id: 'sess-1',
        name: 'Test Session',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'initial',
        pr_link: null,
        linear_link: null,
      },
    ];

    vi.mocked(getSessions).mockResolvedValue(sessions);

    const { rerender } = render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('initial')).toBeInTheDocument();

    // Simulate status update via prop change
    const updatedSessions = [
      {
        ...sessions[0],
        step: 'completed',
      },
    ];

    rerender(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={updatedSessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('completed')).toBeInTheDocument();
  });
});
