import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { SessionHistory } from './SessionHistory';
import type { SessionHistoryEntry, SessionToolUsage } from '../services/api';

const mockEntries: SessionHistoryEntry[] = [
  {
    id: '1',
    session_id: 'session-abc',
    task_id: 'TASK-1',
    agent_session_id: 'agent-session-1',
    kind: 'invocation',
    step: 'plan',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    length: 1000,
    input_tokens: 500,
    output_tokens: 300,
    reasoning_tokens: 100,
    cache_read_tokens: 50,
    cache_write_tokens: 50,
    context_tokens: null,
    cost: null,
    model: null,
    agent: 'opencode',
    tool_usage: [
      { name: 'bash', calls: 3, succeeded: 3, failed: 0, duration_ms: 90 },
      { name: 'read', calls: 1, succeeded: 1, failed: 0, duration_ms: 5 },
    ],
    message: null,
  },
  {
    id: '2',
    session_id: 'session-abc',
    task_id: 'TASK-1',
    agent_session_id: 'agent-session-1',
    kind: 'invocation',
    step: 'build',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    length: 2500,
    input_tokens: 1200,
    output_tokens: 800,
    reasoning_tokens: 300,
    cache_read_tokens: 100,
    cache_write_tokens: 100,
    context_tokens: null,
    cost: null,
    model: null,
    agent: 'opencode',
    tool_usage: [{ name: 'bash', calls: 2, succeeded: 2, failed: 0, duration_ms: 30 }],
    message: null,
  },
  {
    id: '3',
    session_id: null,
    task_id: 'TASK-1',
    agent_session_id: null,
    kind: 'step',
    step: 'review',
    created_at: '2026-01-01T00:00:00Z',
    length: null,
    input_tokens: null,
    output_tokens: null,
    reasoning_tokens: null,
    cache_read_tokens: null,
    cache_write_tokens: null,
    context_tokens: null,
    cost: null,
    model: null,
    agent: null,
    message: null,
  },
];

const mockTotal = {
  length: 3500,
  input_tokens: 1700,
  output_tokens: 1100,
  reasoning_tokens: 400,
  cache_read_tokens: 150,
  cache_write_tokens: 150,
  cost: 0.15,
};

const zeroTotal = {
  length: 0,
  input_tokens: 0,
  output_tokens: 0,
  reasoning_tokens: 0,
  cache_read_tokens: 0,
  cache_write_tokens: 0,
  cost: 0,
};

const emptyToolUsage: SessionToolUsage[] = [];

const mockToolUsage: SessionToolUsage[] = [
  { name: 'bash', calls: 5, succeeded: 5, failed: 0, duration_ms: 120 },
  { name: 'read', calls: 3, succeeded: 3, failed: 0, duration_ms: 45 },
];

describe('SessionHistory', () => {
  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <SessionHistory entries={[]} total={zeroTotal} toolUsage={emptyToolUsage} isOpen={false} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders loading spinner when isLoading is true', () => {
    render(
      <SessionHistory entries={[]} total={zeroTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={true} error={null} />
    );
    expect(screen.getByAltText('Loading...')).toBeInTheDocument();
  });

  it('renders empty state when entries is empty', () => {
    render(
      <SessionHistory entries={[]} total={zeroTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(screen.getByText('No history yet')).toBeInTheDocument();
  });

  it('renders error state when error is set', () => {
    render(
      <SessionHistory entries={[]} total={zeroTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error="Failed to load" />
    );
    expect(screen.getByText('Failed to load')).toBeInTheDocument();
  });

  it('renders one card per entry with step names', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    expect(screen.getByText('plan')).toBeInTheDocument();
    expect(screen.getByText('build')).toBeInTheDocument();
    expect(screen.getByText('review')).toBeInTheDocument();
  });

  it('displays clock time with the full date in the title tooltip', () => {
    const iso = '2026-01-01T12:34:56Z';
    const entry = { ...mockEntries[2], created_at: iso };

    render(
      <SessionHistory entries={[entry]} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    const expectedTime = new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    const timeEl = document.querySelector('time.session-history-time')!;
    expect(timeEl.textContent).toBe(expectedTime);
    expect(timeEl.getAttribute('title')).toBe(new Date(iso).toLocaleString());
    expect(timeEl.getAttribute('datetime')).toBe(iso);
  });

  it('renders token dl only for entries with token data', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );
    const tokenDls = document.querySelectorAll('.session-history-tokens');
    expect(tokenDls.length).toBe(2);
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getAllByText('Total').length).toBe(3);
  });

  it('hides token dl when all token fields are null', () => {
    const nullEntry: SessionHistoryEntry = {
      id: '4',
      session_id: null,
      task_id: 'TASK-1',
      agent_session_id: null,
      kind: 'step',
      step: 'initial',
      created_at: new Date().toISOString(),
      length: null,
      input_tokens: null,
      output_tokens: null,
      reasoning_tokens: null,
      cache_read_tokens: null,
      cache_write_tokens: null,
      context_tokens: null,
      cost: null,
      model: null,
      agent: null,
      message: null,
    };

    render(
      <SessionHistory entries={[nullEntry]} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('initial')).toBeInTheDocument();
    expect(document.querySelector('.session-history-tokens')).not.toBeInTheDocument();
  });

  it('renders tokens and attribution for an llm call entry', () => {
    const entry: SessionHistoryEntry = {
      ...mockEntries[2],
      id: 'llm-1',
      kind: 'llm_call',
      step: 'summarize_plan',
      length: 400,
      input_tokens: 300,
      output_tokens: 100,
      model: 'openai/gpt-oss-120b',
      agent: 'openrouter',
    };

    render(
      <SessionHistory entries={[entry]} total={mockTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(document.querySelector('.session-history-tokens')).toBeInTheDocument();
    expect(screen.getByText('summarize_plan')).toBeInTheDocument();
    expect(screen.getByText('openai/gpt-oss-120b')).toBeInTheDocument();
    expect(screen.getByText('openrouter')).toBeInTheDocument();
    expect(screen.getByText('300')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('renders agent and cost for an invocation entry', () => {
    const entry = { ...mockEntries[0], agent: 'build', cost: 0.1234, model: 'provider/model' };

    render(
      <SessionHistory entries={[entry]} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('build')).toBeInTheDocument();
    expect(screen.getByText('Cost')).toBeInTheDocument();
    expect(screen.getByText('$0.1234')).toBeInTheDocument();
    expect(screen.getByText('provider/model')).toBeInTheDocument();
  });

  it('renders failure reason context for a failed step entry', () => {
    const failedEntry: SessionHistoryEntry = {
      ...mockEntries[2],
      step: 'failed',
      message: 'Plan agent failed (exit 1): quota exceeded',
    };

    render(
      <SessionHistory entries={[failedEntry]} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    const failure = document.querySelector('.session-history-failure');
    expect(failure).not.toBeNull();
    expect(failure!.textContent).toBe('Plan agent failed (exit 1): quota exceeded');
  });

  it('does not render failure context without a message', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(document.querySelector('.session-history-failure')).not.toBeInTheDocument();
  });

  it('does not render tokens for a step entry even with a length', () => {
    const stepEntry = { ...mockEntries[2], length: 999 };

    render(
      <SessionHistory entries={[stepEntry]} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(document.querySelector('.session-history-tokens')).not.toBeInTheDocument();
  });

  it('renders total tokens block with breakdown and grand total', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('Total Tokens')).toBeInTheDocument();
    expect(document.querySelector('.session-history-totals')).toBeInTheDocument();
    expect(screen.getByText('1,700')).toBeInTheDocument();
    expect(screen.getByText('1,100')).toBeInTheDocument();
    expect(screen.getByText('400')).toBeInTheDocument();
    expect(screen.getAllByText('150')).toHaveLength(2);
    expect(screen.getByText('3,500')).toBeInTheDocument();
    expect(screen.getByText('Total Cost')).toBeInTheDocument();
    expect(screen.getByText('$0.1500')).toBeInTheDocument();
  });

  it('renders the tool usage block beside the token totals', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('Tool Usage')).toBeInTheDocument();
    expect(document.querySelector('.session-history-tool-grid')).toBeInTheDocument();
    expect(document.querySelectorAll('.session-history-totals')).toHaveLength(2);
  });

  it('renders MCP tools invoked through the code-mode execute tool', () => {
    const usage: SessionToolUsage[] = [
      { name: 'execute', calls: 1, succeeded: 1, failed: 0, duration_ms: 20 },
      { name: 'WI.wiki_search', calls: 2, succeeded: 2, failed: 0, duration_ms: 0 },
      { name: 'WI.wiki_list_pages', calls: 1, succeeded: 1, failed: 0, duration_ms: 0 },
    ];

    render(
      <SessionHistory entries={[mockEntries[0]]} total={mockTotal} toolUsage={usage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    const grid = document.querySelector('.session-history-tool-grid');
    expect(grid?.textContent).toContain('WI.wiki_search');
    expect(grid?.textContent).toContain('WI.wiki_list_pages');
    expect(grid?.textContent).toContain('execute');
  });

  it('does not render the tool usage block without tool totals', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.queryByText('Tool Usage')).not.toBeInTheDocument();
  });

  it('renders per-card tools for invocation entries only', () => {
    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    const toolLists = document.querySelectorAll('.session-history-tools-list');
    expect(toolLists).toHaveLength(2);
    expect(toolLists[0].textContent).toContain('×3');
    expect(toolLists[1].textContent).toContain('×2');
  });

  it('shows failed call counts in the tool usage block', () => {
    const usage: SessionToolUsage[] = [{ name: 'bash', calls: 4, succeeded: 3, failed: 1, duration_ms: 10 }];

    render(
      <SessionHistory entries={[mockEntries[0]]} total={mockTotal} toolUsage={usage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('(1 failed)')).toBeInTheDocument();
  });

  it('does not render total tokens block when history is empty', () => {
    render(
      <SessionHistory entries={[]} total={zeroTotal} toolUsage={emptyToolUsage} isOpen={true} onClose={vi.fn()} isLoading={false} error={null} />
    );

    expect(screen.getByText('No history yet')).toBeInTheDocument();
    expect(document.querySelector('.session-history-totals')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={onClose} isLoading={false} error={null} />
    );

    const closeButton = screen.getByLabelText('Close');
    await user.click(closeButton);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when overlay is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(
      <SessionHistory entries={mockEntries} total={mockTotal} toolUsage={mockToolUsage} isOpen={true} onClose={onClose} isLoading={false} error={null} />
    );

    const overlay = document.querySelector('.modal-overlay')!;
    await user.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
