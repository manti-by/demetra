import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { SessionHistory } from './SessionHistory';

const mockEntries = [
  {
    id: '1',
    session_id: 'session-abc',
    step: 'plan',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    length: 1000,
    input_tokens: 500,
    output_tokens: 300,
    reasoning_tokens: 100,
    cache_read_tokens: 50,
    cache_write_tokens: 50,
    context_tokens: null,
    model: null,
  },
  {
    id: '2',
    session_id: 'session-abc',
    step: 'build',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    length: 2500,
    input_tokens: 1200,
    output_tokens: 800,
    reasoning_tokens: 300,
    cache_read_tokens: 100,
    cache_write_tokens: 100,
    context_tokens: null,
    model: null,
  },
  {
    id: '3',
    session_id: 'session-abc',
    step: 'review',
    created_at: '2026-01-01T00:00:00Z',
    length: null,
    input_tokens: null,
    output_tokens: null,
    reasoning_tokens: null,
    cache_read_tokens: null,
    cache_write_tokens: null,
    context_tokens: null,
    model: null,
  },
];

describe('SessionHistory', () => {
  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <SessionHistory entries={[]} isOpen={false} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders loading spinner when isLoading is true', () => {
    render(
      <SessionHistory entries={[]} isOpen={true} onClose={vi.fn()} isLoading={true} error={null} />
    );
    expect(document.querySelector('.loading-spinner')).toBeInTheDocument();
  });

  it('renders empty state when entries is empty', () => {
    render(
      <SessionHistory entries={[]} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(screen.getByText('No history yet')).toBeInTheDocument();
  });

  it('renders error state when error is set', () => {
    render(
      <SessionHistory entries={[]} isOpen={true} onClose={vi.fn()} isLoading={false} error="Failed to load" />
    );
    expect(screen.getByText('Failed to load')).toBeInTheDocument();
  });

  it('renders one card per entry with step names', () => {
    render(
      <SessionHistory entries={mockEntries} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(screen.getByText('plan')).toBeInTheDocument();
    expect(screen.getByText('build')).toBeInTheDocument();
    expect(screen.getByText('review')).toBeInTheDocument();
  });

  it('renders token dl only for entries with token data', () => {
    render(
      <SessionHistory entries={mockEntries} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    const tokenDls = document.querySelectorAll('.session-history-tokens');
    expect(tokenDls.length).toBe(2);
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getAllByText('Total').length).toBe(2);
  });

  it('hides token dl when all token fields are null', () => {
    const nullEntry = {
      id: '4',
      session_id: 'session-abc',
      step: 'initial',
      created_at: new Date().toISOString(),
      length: null,
      input_tokens: null,
      output_tokens: null,
      reasoning_tokens: null,
      cache_read_tokens: null,
      cache_write_tokens: null,
      context_tokens: null,
      model: null,
    };

    render(
      <SessionHistory entries={[nullEntry]} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('initial')).toBeInTheDocument();
    expect(document.querySelector('.session-history-tokens')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <SessionHistory entries={mockEntries} isOpen={true} onClose={onClose} isLoading={false} error={null} />
    );

    const closeButton = screen.getByLabelText('Close');
    await user.click(closeButton);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when overlay is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <SessionHistory entries={mockEntries} isOpen={true} onClose={onClose} isLoading={false} error={null} />
    );

    const overlay = document.querySelector('.modal-overlay')!;
    await user.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
