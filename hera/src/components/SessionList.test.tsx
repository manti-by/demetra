import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { SessionList } from './SessionList';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getSessions: vi.fn(),
}));

const mockSessions: api.Session[] = [
  {
    task_id: 'task-001-abc123',
    session_id: 'session-001-xyz789',
    build_plan: 'Add user authentication',
    posted_to_linear: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    status: 'processed',
  },
  {
    task_id: 'task-002-def456',
    session_id: 'session-002-uvw123',
    build_plan: null,
    posted_to_linear: false,
    created_at: new Date(Date.now() - 3600000).toISOString(),
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    status: 'pending',
  },
  {
    task_id: 'task-003-ghi789',
    session_id: 'session-003-rst456',
    build_plan: 'Fix login bug',
    posted_to_linear: true,
    created_at: new Date(Date.now() - 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    status: 'failed',
  },
];

describe('SessionList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(api.getSessions).mockImplementation(
      () => new Promise(() => {})
    );
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    expect(screen.getByText('Loading sessions...')).toBeInTheDocument();
  });

  it('renders sessions when loaded', async () => {
    vi.mocked(api.getSessions).mockResolvedValue(mockSessions);
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getAllByText('session-')).toHaveLength(3);
    });
  });

  it('renders empty state when no sessions', async () => {
    vi.mocked(api.getSessions).mockResolvedValue([]);
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getByText('No sessions found')).toBeInTheDocument();
    });
  });

  it('renders error state when fetch fails', async () => {
    vi.mocked(api.getSessions).mockRejectedValue(new Error('Network error'));
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('calls onSelectSession when session is clicked', async () => {
    vi.mocked(api.getSessions).mockResolvedValue(mockSessions);
    const onSelectSession = vi.fn();
    const user = userEvent.setup();
    
    render(<SessionList onSelectSession={onSelectSession} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getAllByText('session-')).toHaveLength(3);
    });
    
    const sessionItems = screen.getAllByText('session-');
    await user.click(sessionItems[0]);
    
    expect(onSelectSession).toHaveBeenCalledWith('task-001-abc123');
  });

  it('highlights selected session', async () => {
    vi.mocked(api.getSessions).mockResolvedValue(mockSessions);
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId="task-001-abc123" />);
    
    await waitFor(() => {
      const sessionItems = screen.getAllByText('session-');
      expect(sessionItems[0].closest('.session-item')).toHaveClass('selected');
    });
  });

  it('displays status badges correctly', async () => {
    vi.mocked(api.getSessions).mockResolvedValue(mockSessions);
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getByText('processed')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
      expect(screen.getByText('failed')).toBeInTheDocument();
    });
  });

  it('displays relative time correctly', async () => {
    vi.mocked(api.getSessions).mockResolvedValue(mockSessions);
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    
    await waitFor(() => {
      expect(screen.getByText('Just now')).toBeInTheDocument();
      expect(screen.getByText('1h ago')).toBeInTheDocument();
      expect(screen.getByText('1d ago')).toBeInTheDocument();
    });
  });
});
