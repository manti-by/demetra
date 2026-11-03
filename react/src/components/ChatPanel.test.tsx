import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ChatPanel } from './ChatPanel';
import { getChat, type ChatDetail } from '../services/api';

vi.mock('../services/api', () => ({
  getChat: vi.fn(),
  postChatMessage: vi.fn(),
  updateChat: vi.fn(),
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

describe('ChatPanel', () => {
  it('renders the chat title, task id and messages', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());

    render(<ChatPanel taskId="CH-1" />);

    await waitFor(() => {
      expect(screen.getByText('Add authentication')).toBeInTheDocument();
    });
    expect(screen.getByText('CH-1')).toBeInTheDocument();
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
      expect(screen.getByText('Add authentication')).toBeInTheDocument();
    });
    expect(screen.queryByText('Show logs')).not.toBeInTheDocument();

    rerender(<ChatPanel taskId="CH-1" onShowLogsToggle={vi.fn()} />);
    expect(screen.getByText('Show logs')).toBeInTheDocument();
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

  it('offers re-run once the workflow has settled', async () => {
    vi.mocked(getChat).mockResolvedValue(
      makeDetail({
        session: { step: 'completed', name: 'Add authentication', is_research: false, is_chat: true },
      }),
    );

    render(<ChatPanel taskId="CH-1" />);

    await waitFor(() => {
      expect(screen.getByText('Re-run')).toBeInTheDocument();
    });
  });
});
