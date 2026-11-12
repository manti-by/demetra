import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SessionList } from './SessionList';
import { getLiveSessionIds, getSessions, type Session } from '../services/api';

vi.mock(new URL('../services/api.ts', import.meta.url).pathname, () => ({
  getSessions: vi.fn().mockResolvedValue([]),
  getLiveSessionIds: vi.fn().mockResolvedValue([]),
  deleteSession: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

describe('SessionList', () => {
  beforeEach(() => {
    vi.mocked(getLiveSessionIds).mockReset();
    vi.mocked(getLiveSessionIds).mockResolvedValue([]);
  });

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
        research_report: null,
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

  it('renders session type, project and labels without the build plan', () => {
    const sessions = [
      {
        task_id: 'task-chat',
        session_id: 'sess-chat',
        name: 'Chat session',
        build_plan: 'hidden build plan',
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'build',
        pr_link: null,
        linear_link: null,
        research_report: null,
        kind: 'chat',
        chat_id: 12,
        tags: ['Backend', 'Research'],
        project_name: 'demetra',
      },
    ];

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('C')).toBeInTheDocument();
    expect(screen.getByText('build')).toBeInTheDocument();
    expect(screen.getByText('Chat session')).toBeInTheDocument();
    const item = screen.getByText('Chat session').closest('.session-item') as HTMLElement;
    expect(within(item).getByText('demetra')).toBeInTheDocument();
    expect(within(item).getByText('Backend')).toBeInTheDocument();
    expect(within(item).getByText('Research')).toBeInTheDocument();
    expect(screen.queryByText('hidden build plan')).not.toBeInTheDocument();
  });

  it('labels sessions without a chat as L', () => {
    const sessions = [
      {
        task_id: 'task-linear',
        session_id: 'sess-linear',
        name: 'Linear session',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'completed',
        pr_link: null,
        linear_link: null,
        research_report: null,
      },
    ];

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('L')).toBeInTheDocument();
    expect(screen.queryByText('C')).not.toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
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
        research_report: null,
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

  it('filters sessions by search query', () => {
    const sessions = [
      {
        task_id: 'task-1',
        session_id: 'sess-1',
        name: 'odin',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'build',
        pr_link: null,
        linear_link: null,
        research_report: null,
      },
      {
        task_id: 'task-2',
        session_id: 'sess-2',
        name: 'amon-ra',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'completed',
        pr_link: null,
        linear_link: null,
        research_report: null,
      },
    ];

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    expect(screen.getByText('odin')).toBeInTheDocument();
    expect(screen.getByText('amon-ra')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
      target: { value: 'amon' },
    });

    expect(screen.getByText('amon-ra')).toBeInTheDocument();
    expect(screen.queryByText('odin')).not.toBeInTheDocument();
  });

  it('matches project names and tags in the search query', () => {
    const sessions = [
      {
        task_id: 'task-1',
        session_id: 'sess-1',
        name: 'odin',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'build',
        pr_link: null,
        linear_link: null,
        research_report: null,
        project_name: 'demetra',
        tags: ['Backend'],
      },
      {
        task_id: 'task-2',
        session_id: 'sess-2',
        name: 'amon-ra',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'completed',
        pr_link: null,
        linear_link: null,
        research_report: null,
        project_name: 'ODIN',
        tags: ['Feature'],
      },
    ];

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
      target: { value: 'demetra' },
    });
    expect(screen.getByText('odin')).toBeInTheDocument();
    expect(screen.queryByText('amon-ra')).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
      target: { value: 'feature' },
    });
    expect(screen.getByText('amon-ra')).toBeInTheDocument();
    expect(screen.queryByText('odin')).not.toBeInTheDocument();
  });

  it('shows empty state when no sessions match the search query', () => {
    const sessions = [
      {
        task_id: 'task-1',
        session_id: 'sess-1',
        name: 'odin',
        build_plan: null,
        posted_to_linear: false,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        step: 'build',
        pr_link: null,
        linear_link: null,
        research_report: null,
      },
    ];

    render(
      <SessionList
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={sessions}
        setSessions={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
      target: { value: 'nomatch' },
    });

    expect(screen.getByText('No matching sessions')).toBeInTheDocument();
  });

  describe('active and completed blocks', () => {
    beforeEach(() => {
      vi.mocked(getLiveSessionIds).mockReset();
      vi.mocked(getLiveSessionIds).mockResolvedValue([]);
    });

    const makeSession = (
      taskId: string,
      name: string,
      step: string,
      overrides: Partial<Session> = {},
    ): Session => ({
      task_id: taskId,
      session_id: `sess-${taskId}`,
      name,
      build_plan: null,
      posted_to_linear: false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      step,
      pr_link: null,
      linear_link: null,
      research_report: null,
      ...overrides,
    });

    const renderList = (sessions: Session[]) =>
      render(
        <SessionList
          onSelectSession={vi.fn()}
          selectedTaskId={null}
          sessions={sessions}
          setSessions={vi.fn()}
        />,
      );

    it('lists active sessions first and separates the completed block with a divider', () => {
      const { container } = renderList([
        makeSession('task-done', 'completed session', 'completed'),
        makeSession('task-research', 'research session', 'researched'),
        makeSession('task-build', 'active session', 'build'),
        makeSession('task-waiting', 'waiting session', 'awaiting_input'),
      ]);

      const list = container.querySelector('.session-list') as HTMLElement;
      expect(Array.from(list.children).map((node) => node.className)).toEqual([
        'session-item',
        'session-item',
        'session-list-divider',
        'session-item',
        'session-item',
      ]);
      expect(
        Array.from(list.querySelectorAll('.session-title')).map(
          (node) => node.textContent,
        ),
      ).toEqual([
        'active session',
        'waiting session',
        'completed session',
        'research session',
      ]);
    });

    it('omits the divider when only the active block has sessions', () => {
      const { container } = renderList([
        makeSession('task-1', 'odin', 'build'),
      ]);

      expect(container.querySelector('.session-list-divider')).toBeNull();
    });

    it('splits the filtered sessions, so a search that hides every active session drops the divider', () => {
      const { container } = renderList([
        makeSession('task-active', 'odin', 'build'),
        makeSession('task-done', 'amon-ra', 'completed'),
      ]);

      expect(container.querySelector('.session-list-divider')).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
        target: { value: 'amon' },
      });

      expect(container.querySelector('.session-list-divider')).toBeNull();
      expect(screen.getByText('amon-ra')).toBeInTheDocument();
      expect(screen.queryByText('odin')).not.toBeInTheDocument();
    });

    it('re-polls the live status on the 5s interval', async () => {
      const intervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderList([makeSession('task-1', 'odin', 'build')]);
      await waitFor(() => expect(getLiveSessionIds).toHaveBeenCalled());

      const poll = intervalSpy.mock.calls.find(([, delay]) => delay === 5000)?.[0] as () => Promise<void>;
      vi.mocked(getLiveSessionIds).mockClear();
      await act(async () => {
        await poll();
      });

      expect(getLiveSessionIds).toHaveBeenCalledTimes(1);
      intervalSpy.mockRestore();
    });

    it('marks the sessions a running job reports as live', async () => {
      vi.mocked(getLiveSessionIds).mockResolvedValue(['task-live']);

      renderList([
        makeSession('task-live', 'live session', 'build'),
        makeSession('task-idle', 'idle session', 'review'),
      ]);

      const liveItem = screen
        .getByText('live session')
        .closest('.session-item') as HTMLElement;
      await waitFor(() => expect(liveItem).toHaveClass('live'));
      expect(screen.getByText('build')).toHaveAttribute(
        'title',
        'Live — running',
      );
      expect(
        screen.getByText('idle session').closest('.session-item') as HTMLElement,
      ).not.toHaveClass('live');
    });

    it('drops the live flag when the live poll fails', async () => {
      vi.mocked(getLiveSessionIds).mockRejectedValue(new Error('broker down'));

      const { container } = renderList([makeSession('task-1', 'odin', 'build')]);

      await waitFor(() => expect(getLiveSessionIds).toHaveBeenCalled());
      expect(container.querySelector('.session-item.live')).toBeNull();
      expect(screen.getByText('odin')).toBeInTheDocument();
    });
  });
});
