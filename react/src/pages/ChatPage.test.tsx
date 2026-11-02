import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { MessageBubble, splitFailureBody } from './ChatPage';
import type { ChatMessage } from '../services/api';

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
