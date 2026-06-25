import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { LogConsole } from './LogConsole';

function createMockWebSocket() {
  let onmessage: ((event: MessageEvent) => void) | null = null;
  let onopen: (() => void) | null = null;

  const ws = {
    onopen: null as (() => void) | null,
    onmessage: null as ((event: MessageEvent) => void) | null,
    onclose: null as (() => void) | null,
    onerror: null as (() => void) | null,
    close: vi.fn(),
    send: vi.fn(),
  };

  const mockWebSocket = new Proxy(ws, {
    set(target, prop, value) {
      if (prop === 'onmessage') {
        onmessage = value;
      } else if (prop === 'onopen') {
        onopen = value;
      }
      (target as any)[prop] = value;
      return true;
    },
    get(target, prop) {
      return (target as any)[prop];
    },
  });

  return {
    mockWebSocket,
    triggerOpen: () => {
      onopen?.();
    },
    triggerMessage: (data: string) => {
      onmessage?.(new MessageEvent('message', { data }));
    },
  };
}

vi.mock('../services/api', () => ({
  getSessions: vi.fn().mockResolvedValue([]),
  deleteSession: vi.fn(),
}));

describe('LogConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('auth_token', 'test-token');
  });

  it('renders select session prompt when no taskId', () => {
    render(
      <LogConsole
        taskId={null}
        onDeleteSession={vi.fn()}
        onSessionStatus={vi.fn()}
      />,
    );
    expect(screen.getByText('Select a session')).toBeInTheDocument();
  });

  it('parses log envelope and appends to console', async () => {
    const wsMock = createMockWebSocket();

    vi.stubGlobal('WebSocket', vi.fn(() => wsMock.mockWebSocket));

    const onSessionStatus = vi.fn();

    render(
      <LogConsole
        taskId="task-123"
        onDeleteSession={vi.fn()}
        onSessionStatus={onSessionStatus}
      />,
    );

    // Simulate auth token
    localStorage.setItem('auth_token', 'test-token');

    // Re-render after storage change
    act(() => {
      wsMock.triggerOpen();
    });

    act(() => {
      wsMock.triggerMessage(
        JSON.stringify({ type: 'log', data: { text: 'hello world' } }),
      );
    });

    expect(screen.getByText('hello world')).toBeInTheDocument();
    expect(onSessionStatus).not.toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it('parses status envelope and calls onSessionStatus', () => {
    const wsMock = createMockWebSocket();

    vi.stubGlobal('WebSocket', vi.fn(() => wsMock.mockWebSocket));

    const onSessionStatus = vi.fn();

    render(
      <LogConsole
        taskId="task-123"
        onDeleteSession={vi.fn()}
        onSessionStatus={onSessionStatus}
      />,
    );

    localStorage.setItem('auth_token', 'test-token');

    act(() => {
      wsMock.triggerOpen();
    });

    act(() => {
      wsMock.triggerMessage(
        JSON.stringify({ type: 'status', data: { step: 'build', name: 'Test' } }),
      );
    });

    expect(onSessionStatus).toHaveBeenCalledWith('task-123', {
      step: 'build',
      name: 'Test',
    });

    vi.unstubAllGlobals();
  });

  it('clears logs when status step is deleted', () => {
    const wsMock = createMockWebSocket();

    vi.stubGlobal('WebSocket', vi.fn(() => wsMock.mockWebSocket));

    const onSessionStatus = vi.fn();

    render(
      <LogConsole
        taskId="task-123"
        onDeleteSession={vi.fn()}
        onSessionStatus={onSessionStatus}
      />,
    );

    localStorage.setItem('auth_token', 'test-token');

    act(() => {
      wsMock.triggerOpen();
    });

    // Add a log line first
    act(() => {
      wsMock.triggerMessage(
        JSON.stringify({ type: 'log', data: { text: 'some log' } }),
      );
    });

    expect(screen.getByText('some log')).toBeInTheDocument();

    // Send deleted status
    act(() => {
      wsMock.triggerMessage(
        JSON.stringify({ type: 'status', data: { step: 'deleted' } }),
      );
    });

    // Log should be cleared, showing empty state
    expect(screen.getByText('Waiting for log events...')).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
