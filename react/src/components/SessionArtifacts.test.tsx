import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { SessionArtifacts } from './SessionArtifacts';

const mockSessionWithPrLink = {
  task_id: 'TASK-123',
  session_id: 'session-abc',
  name: 'Test Task',
  build_plan: '1. Step one\n2. Step two\n3. Step three',
  posted_to_linear: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T01:00:00Z',
  step: 'completed',
  pr_link: 'https://github.com/owner/repo/pull/42',
};

const mockSessionWithBuildPlanOnly = {
  ...mockSessionWithPrLink,
  pr_link: null,
};

const mockSessionWithoutArtifacts = {
  ...mockSessionWithPrLink,
  pr_link: null,
  build_plan: null,
};

vi.mock('../services/api', () => ({
  getSessions: vi.fn(),
}));

import { getSessions } from '../services/api';

describe('SessionArtifacts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when taskId is null', () => {
    const { container } = render(<SessionArtifacts taskId={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when session has no artifacts', async () => {
    vi.mocked(getSessions).mockResolvedValue([mockSessionWithoutArtifacts]);

    const { container } = render(<SessionArtifacts taskId="TASK-123" />);
    await vi.waitFor(() => {
      expect(getSessions).toHaveBeenCalled();
    });
    // Wait for state update
    await vi.waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it('renders PR link when session has pr_link', async () => {
    vi.mocked(getSessions).mockResolvedValue([mockSessionWithPrLink]);

    render(<SessionArtifacts taskId="TASK-123" />);

    const link = await screen.findByText('View Pull Request');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42');
    expect(link.closest('a')).toHaveAttribute('target', '_blank');
    expect(link.closest('a')).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders build plan button when session has build_plan', async () => {
    vi.mocked(getSessions).mockResolvedValue([mockSessionWithBuildPlanOnly]);

    render(<SessionArtifacts taskId="TASK-123" />);

    const button = await screen.findByText('View Build Plan');
    expect(button).toBeInTheDocument();
  });

  it('does not render PR link when pr_link is null', async () => {
    vi.mocked(getSessions).mockResolvedValue([mockSessionWithBuildPlanOnly]);

    render(<SessionArtifacts taskId="TASK-123" />);

    await vi.waitFor(() => {
      expect(screen.queryByText('View Pull Request')).not.toBeInTheDocument();
    });
  });

  it('opens build plan modal on button click and closes it', async () => {
    const user = userEvent.setup();
    vi.mocked(getSessions).mockResolvedValue([mockSessionWithPrLink]);

    render(<SessionArtifacts taskId="TASK-123" />);

    const button = await screen.findByText('View Build Plan');
    await user.click(button);

    expect(screen.getByText('Build Plan')).toBeInTheDocument();
    expect(screen.getByText(mockSessionWithPrLink.build_plan)).toBeInTheDocument();

    const closeButton = screen.getByLabelText('Close');
    await user.click(closeButton);

    expect(screen.queryByText('Build Plan')).not.toBeInTheDocument();
  });
});
