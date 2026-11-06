import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ChatPage, MessageBubble, splitFailureBody } from './ChatPage';
import { AuthProvider } from '../contexts/AuthContext';
import { deleteSession, getChat, type ChatDetail, type ChatMessage } from '../services/api';

vi.mock('../services/api', () => ({
  getCurrentUser: vi.fn().mockResolvedValue({ id: 'u1', email: 'user@example.com' }),
  logout: vi.fn(),
  getChat: vi.fn(),
  postChatMessage: vi.fn(),
  rerunChat: vi.fn(),
  deleteSession: vi.fn(),
}));

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: '1',
    chat_id: 1,
    session_task_id: 'CH-1',
    body: '',
    created_at: '2026-01-01T00:00:00Z',
    author_id: null,
    is_system: true,
    kind: 'message',
    ...overrides,
  };
}

const buildFailureBody = `## Build agent failed

The build agent exited with an error before producing any changes.

### Error

\`\`\`
exit status 1
\`\`\``;

describe('TestSplitFailureBody', () => {
  it('splits the leading markdown heading into a title', () => {
    expect(splitFailureBody(buildFailureBody)).toEqual({
      title: 'Build agent failed',
      detail: 'The build agent exited with an error before producing any changes.\n\n### Error\n\n```\nexit status 1\n```',
    });
  });

  it('leaves a one-line failure as the title', () => {
    expect(splitFailureBody('Max run attempts reached')).toEqual({
      title: 'Max run attempts reached',
      detail: '',
    });
  });
});

describe('TestMessageBubbleFailure', () => {
  it('collapses failure messages by default', () => {
    render(<MessageBubble message={makeMessage({ kind: 'failure', body: buildFailureBody })} />);

    const details = document.querySelector('details');
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    expect(screen.getByText('Build agent failed')).toBeInTheDocument();
    expect(screen.queryByText(/exit status 1/)).toBeInTheDocument();
  });

  it('reveals the failure detail when expanded', async () => {
    render(<MessageBubble message={makeMessage({ kind: 'failure', body: buildFailureBody })} />);

    await userEvent.click(screen.getByText('Build agent failed'));

    expect(screen.getByText(/exit status 1/)).toBeVisible();
  });

  it('renders a one-line failure without a disclosure control', () => {
    render(<MessageBubble message={makeMessage({ kind: 'failure', body: 'Max run attempts reached' })} />);

    expect(document.querySelector('details')).toBeNull();
    expect(screen.getByText('Max run attempts reached')).toBeVisible();
  });

  it('keeps non-failure messages fully visible', () => {
    render(<MessageBubble message={makeMessage({ kind: 'status', body: 'Working on it' })} />);

    expect(document.querySelector('details')).toBeNull();
    expect(screen.getByText('Working on it')).toBeVisible();
  });
});

describe('TestMessageBubbleMarkdown', () => {
  it('renders question messages as markdown', () => {
    render(
      <MessageBubble message={makeMessage({ kind: 'question', body: '## Question\n\nWhich **database**?' })} />,
    );

    expect(screen.getByRole('heading', { name: 'Question' })).toBeInTheDocument();
    expect(screen.getByText('database').tagName).toBe('STRONG');
  });

  it('keeps failure messages as plain text', () => {
    render(
      <MessageBubble message={makeMessage({ kind: 'failure', body: '## Build failed\n\nSome **bold** detail' })} />,
    );

    expect(screen.getByText('Some **bold** detail')).toBeInTheDocument();
    expect(document.querySelector('strong')).toBeNull();
  });
});

function makeDetail(): ChatDetail {
  return {
    chat: {
      id: 1,
      session_task_id: 'CH-1',
      title: 'Add authentication',
      description: 'Wire up login',
      user_id: 'u1',
      project_id: 'p1',
      project_name: 'demetra',
      tags: [],
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    messages: [],
    session: { step: 'build', name: 'Add authentication', is_research: false, is_chat: true },
  };
}

function renderChatPage() {
  localStorage.setItem('user', JSON.stringify({ id: 'u1', email: 'user@example.com' }));
  return render(
    <MemoryRouter initialEntries={['/chats/CH-1']}>
      <AuthProvider>
        <Routes>
          <Route path="/chats/:taskId" element={<ChatPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('TestChatPageDeletion', () => {
  it('deletes the chat and returns to the session list', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    vi.mocked(deleteSession).mockResolvedValue();

    renderChatPage();

    await userEvent.click(await screen.findByText('Delete'));

    expect(deleteSession).toHaveBeenCalledWith('CH-1');
  });

  it('shows an error when deleting the chat fails', async () => {
    vi.mocked(getChat).mockResolvedValue(makeDetail());
    vi.mocked(deleteSession).mockRejectedValue(new Error('Failed to delete session'));

    renderChatPage();

    await userEvent.click(await screen.findByText('Delete'));

    expect(await screen.findByText('Failed to delete session')).toBeInTheDocument();
  });
});
