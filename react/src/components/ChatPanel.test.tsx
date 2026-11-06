import { describe, it, expect, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ChatPanel } from './ChatPanel';
import {
  getChat,
  postChatMessage,
  rerunChat,
  type ChatDetail,
  type ChatMessage,
  type ChatMessageKind,
} from '../services/api';

vi.mock(new URL('../services/api.ts', import.meta.url).pathname, () => ({
  getChat: vi.fn(),
  postChatMessage: vi.fn(),
  rerunChat: vi.fn(),
}));

function makeDetail(overrides: Partial<ChatDetail> = {}): ChatDetail {
  return {
    chat: {
      id: 1,
      session_task_id: 'CH-1',
      title: 'Add authentication',
      description: 'Wire up login',
      user_id: 'u1',
      project_id: 'p1',
      project_name: 'demetra',
      tags: ['Backend'],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    messages: [
      {
        id: 'm1',
        chat_id: 1,
        session_task_id: 'CH-1',
        body: 'Started working on it',
        created_at: '2026-01-01T00:00:00Z',
        author_id: null,
        is_system: true,
        kind: 'status',
      },
    ],
    session: { step: 'build', name: 'Add authentication', is_research: false, is_chat: true },
    ...overrides,
  };
}

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'm-md',
    chat_id: 1,
    session_task_id: 'CH-1',
    body: '## Heading\n\nSome **bold** text',
    created_at: '2026-01-01T00:00:00Z',
    author_id: null,
    is_system: true,
    kind: 'message',
    ...overrides,
  };
}

describe('ChatPanel', () => {
  it('renders the chat title with its task id and messages', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    render(<ChatPanel taskId="CH-1" />);

    await waitFor(() => {
      expect(screen.getByText('CH-1: Add authentication')).toBeInTheDocument();
    });
    expect(screen.getByText('Started working on it')).toBeInTheDocument();
  });

  it('renders a single session state flow inside the panel', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    const { container } = render(<ChatPanel taskId="CH-1" showLogs={false} />);

    await waitFor(() => {
      expect(container.querySelector('.session-flow')).not.toBeNull();
    });
    expect(container.querySelectorAll('.session-flow')).toHaveLength(1);
  });

  it('shows the logs toggle only when a handler is provided', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    const { rerender } = render(<ChatPanel taskId="CH-1" />);
    await waitFor(() => {
      expect(screen.getByText('CH-1: Add authentication')).toBeInTheDocument();
    });
    expect(screen.queryByText('Show logs')).not.toBeInTheDocument();

    rerender(<ChatPanel taskId="CH-1" onShowLogsToggle={vi.fn()} />);
    expect(screen.getByText('Show logs')).toBeInTheDocument();
  });

  it('shows the delete button only when a handler is provided', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    const { rerender } = render(<ChatPanel taskId="CH-1" />);
    await waitFor(() => {
      expect(screen.getByText('CH-1: Add authentication')).toBeInTheDocument();
    });
    expect(screen.queryByText('Delete')).not.toBeInTheDocument();

    rerender(<ChatPanel taskId="CH-1" onDeleteSession={vi.fn()} />);
    expect(screen.getByText('Delete')).toBeInTheDocument();
  });

  it('deletes the session with its task id', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    const onDeleteSession = vi.fn();

    render(<ChatPanel taskId="CH-1" onDeleteSession={onDeleteSession} />);

    fireEvent.click(await screen.findByText('Delete'));

    expect(onDeleteSession).toHaveBeenCalledWith('CH-1');
  });

  it('ignores repeated delete clicks for the same task while a request is in flight', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const onDeleteSession = vi.fn().mockReturnValue(gate);

    render(<ChatPanel taskId="CH-1" onDeleteSession={onDeleteSession} />);

    fireEvent.click(await screen.findByText('Delete'));
    fireEvent.click(screen.getByText('Delete'));

    expect(onDeleteSession).toHaveBeenCalledTimes(1);

    await act(async () => {
      release();
      await gate;
    });
  });

  it('allows a new delete request after the previous one settles', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    const onDeleteSession = vi.fn().mockResolvedValue(undefined);

    render(<ChatPanel taskId="CH-1" onDeleteSession={onDeleteSession} />);

    fireEvent.click(await screen.findByText('Delete'));
    await act(async () => {
      await Promise.resolve();
    });
    fireEvent.click(screen.getByText('Delete'));
    await act(async () => {
      await Promise.resolve();
    });

    expect(onDeleteSession).toHaveBeenCalledTimes(2);
  });

  it('clears the composer draft when the session changes', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    const { rerender } = render(<ChatPanel taskId="CH-1" />);

    const composer = await screen.findByPlaceholderText('Reply to the workflow...');
    fireEvent.change(composer, { target: { value: 'draft for CH-1' } });
    expect(composer).toHaveValue('draft for CH-1');

    const next = makeDetail();
    next.chat = { ...next.chat, session_task_id: 'CH-2', title: 'Second chat' };
    vi.mocked(getChat).mockResolvedValue(next);

    rerender(<ChatPanel taskId="CH-2" />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Reply to the workflow...')).toHaveValue('');
    });
  });

  it('shows the description as read-only text', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    render(<ChatPanel taskId="CH-1" />);

    expect(await screen.findByText('Wire up login')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Wire up login')).not.toBeInTheDocument();
  });

  it('renders the description as markdown', async () => {
    const detail = makeDetail();
    detail.chat = { ...detail.chat, description: 'Wire up **login**' };
    vi.mocked(getChat).mockResolvedValue(detail);

    const { container } = render(<ChatPanel taskId="CH-1" />);

    await screen.findByText('CH-1: Add authentication');
    expect(container.querySelector('.chat-description-text strong')).toHaveTextContent('login');
    expect(screen.queryByText('Wire up **login**')).not.toBeInTheDocument();
  });

  it.each<ChatMessageKind>(['plan', 'question', 'research', 'message'])(
    'renders %s messages as markdown',
    async (kind) => {
      vi.mocked(getChat).mockResolvedValue(
        makeDetail({ messages: [makeMessage({ kind })] }),
      );

      const { container } = render(<ChatPanel taskId="CH-1" />);

      await screen.findByText('CH-1: Add authentication');
      expect(container.querySelector('.chat-message-body h2')).toHaveTextContent('Heading');
      expect(container.querySelector('.chat-message-body strong')).toHaveTextContent('bold');
    },
  );

  it('keeps failure messages as plain text', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({
        messages: [
          makeMessage({
            kind: 'failure',
            body: '## Build failed\n\nSome **bold** detail',
          }),
        ],
      }),
    );

    const { container } = render(<ChatPanel taskId="CH-1" />);

    await screen.findByText('CH-1: Add authentication');
    expect(screen.getByText('Some **bold** detail')).toBeInTheDocument();
    expect(container.querySelector('.chat-message-body strong')).toBeNull();
    expect(container.querySelector('.chat-message-body h2')).toBeNull();
  });

  it('keeps status messages as plain text', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({ messages: [makeMessage({ kind: 'status', body: 'Working on **it**' })] }),
    );

    render(<ChatPanel taskId="CH-1" />);

    expect(await screen.findByText('Working on **it**')).toBeInTheDocument();
  });

  it('offers re-run for a failed session', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({
        session: { step: 'failed', name: 'Add authentication', is_research: false, is_chat: true },
      }),
    );

    render(<ChatPanel taskId="CH-1" />);

    await waitFor(() => {
      expect(screen.getByText('Re-run')).toBeInTheDocument();
    });
  });

  it('does not offer re-run for a completed session', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({
        session: { step: 'completed', name: 'Add authentication', is_research: false, is_chat: true },
      }),
    );

    render(<ChatPanel taskId="CH-1" />);

    await screen.findByText('CH-1: Add authentication');
    expect(screen.queryByText('Re-run')).not.toBeInTheDocument();
  });

  it('requests a rerun without touching the session status', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({
        session: { step: 'awaiting_input', name: 'Add authentication', is_research: false, is_chat: true },
      }),
    );
    vi.mocked(rerunChat).mockResolvedValue({ resumed: true });

    render(<ChatPanel taskId="CH-1" />);

    fireEvent.click(await screen.findByText('Re-run'));
    await waitFor(() => {
      expect(rerunChat).toHaveBeenCalledWith('CH-1');
    });
  });

  it('renders load errors from polling', async () => {
    vi.mocked(getChat).mockRejectedValue(new Error('getChat boom'));

    render(<ChatPanel taskId="CH-1" />);

    expect(await screen.findByText('getChat boom')).toBeInTheDocument();
  });

  it('keeps an action error when a later poll succeeds', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    const intervalSpy = vi.spyOn(globalThis, 'setInterval');

    render(<ChatPanel taskId="CH-1" />);
    await screen.findByText('CH-1: Add authentication');
    const poll = intervalSpy.mock.calls.find(([, delay]) => delay === 5000)?.[0] as () => Promise<void>;

    vi.mocked(postChatMessage).mockRejectedValue(new Error('send failed'));
    fireEvent.change(screen.getByPlaceholderText('Reply to the workflow...'), {
      target: { value: 'hello' },
    });
    fireEvent.click(screen.getByText('Send'));
    expect(await screen.findByText('send failed')).toBeInTheDocument();

    await act(async () => {
      await poll();
    });

    expect(screen.getByText('send failed')).toBeInTheDocument();
    expect(screen.queryByText('Failed to load chat')).not.toBeInTheDocument();
    intervalSpy.mockRestore();
  });

  it('clears the action error when a new action starts', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    render(<ChatPanel taskId="CH-1" />);
    await screen.findByText('CH-1: Add authentication');

    vi.mocked(postChatMessage).mockRejectedValueOnce(new Error('send failed'));
    fireEvent.change(screen.getByPlaceholderText('Reply to the workflow...'), {
      target: { value: 'hello' },
    });
    fireEvent.click(screen.getByText('Send'));
    expect(await screen.findByText('send failed')).toBeInTheDocument();

    vi.mocked(postChatMessage).mockImplementationOnce(() => new Promise<never>(() => {}));
    fireEvent.click(screen.getByText('Send'));

    await waitFor(() => {
      expect(screen.queryByText('send failed')).not.toBeInTheDocument();
    });
  });

  it('clears the action error when the task changes', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    const { rerender } = render(<ChatPanel taskId="CH-1" />);
    await screen.findByText('CH-1: Add authentication');

    vi.mocked(postChatMessage).mockRejectedValue(new Error('send failed'));
    fireEvent.change(screen.getByPlaceholderText('Reply to the workflow...'), {
      target: { value: 'hello' },
    });
    fireEvent.click(screen.getByText('Send'));
    expect(await screen.findByText('send failed')).toBeInTheDocument();

    const next = makeDetail();
    next.chat = { ...next.chat, session_task_id: 'CH-2', title: 'Second chat' };
    vi.mocked(getChat).mockResolvedValue(next);

    rerender(<ChatPanel taskId="CH-2" />);

    await waitFor(() => {
      expect(screen.queryByText('send failed')).not.toBeInTheDocument();
    });
  });
});
