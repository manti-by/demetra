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

const daysAgo = (days: number): string =>
  new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

const makeSession = (overrides: Partial<Session>): Session => ({
  task_id: 'task-1',
  session_id: 'sess-1',
  name: 'Session',
  build_plan: null,
  posted_to_linear: false,
  created_at: daysAgo(1),
  updated_at: daysAgo(1),
  step: 'build',
  pr_link: null,
  linear_link: null,
  research_report: null,
  ...overrides,
});

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

  describe('active and backlog blocks', () => {
    const makeBlockSession = (
      taskId: string,
      name: string,
      step: string,
      overrides: Partial<Session> = {},
    ): Session =>
      makeSession({
        task_id: taskId,
        session_id: `sess-${taskId}`,
        name,
        step,
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

    it('lists recent in-progress sessions above the backlog section', () => {
      const { container } = renderList([
        makeBlockSession('task-done', 'completed session', 'completed'),
        makeBlockSession('task-failed', 'failed session', 'failed'),
        makeBlockSession('task-research', 'research session', 'researched', {
          created_at: daysAgo(30),
        }),
        makeBlockSession('task-build', 'active session', 'build', {
          created_at: daysAgo(2),
        }),
        makeBlockSession('task-stale', 'stale session', 'awaiting_input', {
          created_at: daysAgo(20),
        }),
      ]);

      const list = container.querySelector('.session-list') as HTMLElement;
      expect(Array.from(list.children).map((node) => node.className)).toEqual([
        'session-item',
        'session-section-header',
        'session-item',
        'session-item',
        'session-item',
        'session-item',
      ]);
      expect(
        Array.from(list.querySelectorAll('.session-title')).map(
          (node) => node.textContent,
        ),
      ).toEqual([
        'active session',
        'completed session',
        'failed session',
        'research session',
        'stale session',
      ]);
      expect(screen.getByText('Backlog')).toBeInTheDocument();
      expect(container.querySelector('.session-section-count')?.textContent).toBe('4');
    });

    it('omits the backlog section when only the active block has sessions', () => {
      const { container } = renderList([
        makeBlockSession('task-1', 'odin', 'build'),
      ]);

      expect(container.querySelector('.session-section-header')).toBeNull();
      expect(screen.getByText('odin')).toBeInTheDocument();
    });

    it('keeps a recent failed session out of the active block', () => {
      const { container } = renderList([
        makeBlockSession('task-failed', 'failed session', 'failed'),
      ]);

      expect(screen.getByText('Backlog')).toBeInTheDocument();
      expect(container.querySelector('.session-section-count')?.textContent).toBe('1');
      expect(screen.getByText('failed session')).toBeInTheDocument();
    });

    it('splits the filtered sessions, so a search that hides every backlog session drops the header', () => {
      const { container } = renderList([
        makeBlockSession('task-active', 'odin', 'build'),
        makeBlockSession('task-done', 'amon-ra', 'completed'),
      ]);

      expect(container.querySelector('.session-section-header')).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText('Search sessions...'), {
        target: { value: 'odin' },
      });

      expect(container.querySelector('.session-section-header')).toBeNull();
      expect(screen.getByText('odin')).toBeInTheDocument();
      expect(screen.queryByText('amon-ra')).not.toBeInTheDocument();
    });

    it('re-polls the live status on the 5s interval', async () => {
      const intervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderList([makeBlockSession('task-1', 'odin', 'build')]);
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
        makeBlockSession('task-live', 'live session', 'build'),
        makeBlockSession('task-idle', 'idle session', 'review'),
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

      const { container } = renderList([makeBlockSession('task-1', 'odin', 'build')]);

      await waitFor(() => expect(getLiveSessionIds).toHaveBeenCalled());
      expect(container.querySelector('.session-item.live')).toBeNull();
      expect(screen.getByText('odin')).toBeInTheDocument();
    });

    it('ignores a stale live poll that resolves after a newer one', async () => {
      const intervalSpy = vi.spyOn(globalThis, 'setInterval');
      vi.mocked(getLiveSessionIds).mockResolvedValue(['task-live']);

      const { container } = renderList([
        makeBlockSession('task-live', 'odin', 'build'),
      ]);
      await waitFor(() =>
        expect(
          container.querySelector('.session-item.live'),
        ).toBeInTheDocument(),
      );

      const poll = intervalSpy.mock.calls.find(
        ([, delay]) => delay === 5000,
      )?.[0] as () => Promise<void>;
      let resolveStale: (taskIds: string[]) => void = () => {};
      const stale = new Promise<string[]>((resolve) => {
        resolveStale = resolve;
      });
      vi.mocked(getLiveSessionIds).mockReset();
      vi.mocked(getLiveSessionIds)
        .mockReturnValueOnce(stale)
        .mockResolvedValueOnce([]);

      await act(async () => {
        const stalePoll = poll();
        const newerPoll = poll();
        await newerPoll;
        resolveStale(['task-live']);
        await stalePoll;
      });

      expect(container.querySelector('.session-item.live')).toBeNull();
      intervalSpy.mockRestore();
    });

    it('keeps the newest live result when a stale poll fails', async () => {
      const intervalSpy = vi.spyOn(globalThis, 'setInterval');

      const { container } = renderList([
        makeBlockSession('task-live', 'odin', 'build'),
      ]);
      await waitFor(() => expect(getLiveSessionIds).toHaveBeenCalled());

      const poll = intervalSpy.mock.calls.find(
        ([, delay]) => delay === 5000,
      )?.[0] as () => Promise<void>;
      let rejectStale: (error: Error) => void = () => {};
      const stale = new Promise<string[]>((_, reject) => {
        rejectStale = reject;
      });
      vi.mocked(getLiveSessionIds).mockReset();
      vi.mocked(getLiveSessionIds)
        .mockReturnValueOnce(stale)
        .mockResolvedValueOnce(['task-live']);

      await act(async () => {
        const stalePoll = poll();
        const newerPoll = poll();
        await newerPoll;
        rejectStale(new Error('broker down'));
        await stalePoll;
      });

      expect(
        container.querySelector('.session-item.live'),
      ).toBeInTheDocument();
      intervalSpy.mockRestore();
    });
  });
});
