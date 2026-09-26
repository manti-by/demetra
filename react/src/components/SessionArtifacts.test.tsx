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
  linear_link: 'https://linear.app/manti-by/issue/MNT-123',
  research_report: null,
};

const mockSessionWithBuildPlanOnly = {
  ...mockSessionWithPrLink,
  pr_link: null,
};

const mockSessionWithResearchReportOnly = {
  ...mockSessionWithPrLink,
  pr_link: null,
  build_plan: null,
  linear_link: null,
  session_id: '',
  research_report: '## Research Report\n\nFindings body.',
};

const mockSessionWithAllArtifacts = {
  ...mockSessionWithPrLink,
  research_report: '## Research Report\n\nFindings body.',
};

const mockSessionWithoutArtifacts = {
  ...mockSessionWithPrLink,
  pr_link: null,
  build_plan: null,
  research_report: null,
  linear_link: null,
  session_id: '',
};

const mockSessionWithHistoryOnly = {
  ...mockSessionWithPrLink,
  pr_link: null,
  build_plan: null,
  research_report: null,
  linear_link: null,
  session_id: 'session-abc',
};

vi.mock('../services/api', () => ({
  getSessionHistory: vi.fn(),
}));

import { getSessionHistory } from '../services/api';

describe('SessionArtifacts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty container when taskId is null', () => {
    const { container } = render(<SessionArtifacts taskId={null} sessions={[]} />);
    expect(container.firstChild).toBeInTheDocument();
    expect(container.firstChild).toHaveClass('session-artifacts');
  });

  it('renders empty container when session has no artifacts', () => {
    const { container } = render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithoutArtifacts]} />,
    );
    expect(container.firstChild).toBeInTheDocument();
    expect(container.firstChild).toHaveClass('session-artifacts');
  });

  it('renders PR link when session has pr_link', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithPrLink]} />,
    );

    const link = screen.getByText('View Pull Request');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42');
    expect(link.closest('a')).toHaveAttribute('target', '_blank');
    expect(link.closest('a')).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders Linear issue link when session has linear_link', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithPrLink]} />,
    );

    const link = screen.getByText('View Linear Issue');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', 'https://linear.app/manti-by/issue/MNT-123');
    expect(link.closest('a')).toHaveAttribute('target', '_blank');
    expect(link.closest('a')).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders build plan link when session has build_plan', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithBuildPlanOnly]} />,
    );

    const link = screen.getByText('View Build Plan');
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe('A');
  });

  it('renders research plan link when session has research_report', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithResearchReportOnly]} />,
    );

    const link = screen.getByText('View Research Report');
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe('A');
  });

  it('does not render research plan link when research_report is null', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithBuildPlanOnly]} />,
    );

    expect(screen.queryByText('View Research Report')).not.toBeInTheDocument();
  });

  it('renders research plan link alongside other artifact links', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithAllArtifacts]} />,
    );

    expect(screen.getByText('View Research Report')).toBeInTheDocument();
    expect(screen.getByText('View Build Plan')).toBeInTheDocument();
    expect(screen.getByText('View History')).toBeInTheDocument();
  });

  it('does not render PR link when pr_link is null', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithBuildPlanOnly]} />,
    );

    expect(screen.queryByText('View Pull Request')).not.toBeInTheDocument();
  });

  it('renders history link when session has session_id', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithPrLink]} />,
    );

    const link = screen.getByText('View History');
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe('A');
  });

  it('opens history modal on link click', async () => {
    const user = userEvent.setup();
    vi.mocked(getSessionHistory).mockResolvedValue({
      total: {
        length: 500,
        input_tokens: 200,
        output_tokens: 200,
        reasoning_tokens: 50,
        cache_read_tokens: 25,
        cache_write_tokens: 25,
      },
      history: [
        {
          id: 'h1',
          session_id: 'session-abc',
          step: 'plan',
          created_at: new Date().toISOString(),
          length: 500,
          input_tokens: 200,
          output_tokens: 200,
          reasoning_tokens: 50,
          cache_read_tokens: 25,
          cache_write_tokens: 25,
          context_tokens: null,
          model: null,
        },
      ],
    });

    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithPrLink]} />,
    );

    const link = screen.getByText('View History');
    await user.click(link);

    expect(screen.getByText('Session History [BETA]')).toBeInTheDocument();
    expect(screen.getByText('plan')).toBeInTheDocument();
    expect(screen.getByText('Total Tokens')).toBeInTheDocument();
  });

  it('does not render history link when session_id is empty', () => {
    const noSessionId = { ...mockSessionWithPrLink, session_id: '' };
    render(<SessionArtifacts taskId="TASK-123" sessions={[noSessionId]} />);

    expect(screen.queryByText('View History')).not.toBeInTheDocument();
  });

  it('renders history link when session has only session_id and no other artifacts', () => {
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithHistoryOnly]} />,
    );

    const link = screen.getByText('View History');
    expect(link).toBeInTheDocument();
    expect(screen.queryByText('View Build Plan')).not.toBeInTheDocument();
    expect(screen.queryByText('View Pull Request')).not.toBeInTheDocument();
    expect(screen.queryByText('View Linear Issue')).not.toBeInTheDocument();
  });

  it('opens build plan modal on link click and closes it', async () => {
    const user = userEvent.setup();
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithPrLink]} />,
    );

    const link = screen.getByText('View Build Plan');
    await user.click(link);

    expect(screen.getByText('Build Plan')).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes('Step one'))).toBeInTheDocument();

    const closeButton = screen.getByLabelText('Close');
    await user.click(closeButton);

    expect(screen.queryByText('Build Plan')).not.toBeInTheDocument();
  });

  it('opens research plan modal on link click and closes it', async () => {
    const user = userEvent.setup();
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithResearchReportOnly]} />,
    );

    const link = screen.getByText('View Research Report');
    await user.click(link);

    const headings = screen.getAllByRole('heading', { name: 'Research Report' });
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(headings[0]).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes('Findings body'))).toBeInTheDocument();

    const closeButton = screen.getByLabelText('Close');
    await user.click(closeButton);

    expect(screen.queryByRole('heading', { name: 'Research Report' })).not.toBeInTheDocument();
  });

  it('toggles the research plan modal between rendered and markdown', async () => {
    const user = userEvent.setup();
    render(
      <SessionArtifacts taskId="TASK-123" sessions={[mockSessionWithResearchReportOnly]} />,
    );

    await user.click(screen.getByText('View Research Report'));

    await user.click(screen.getByText('Show Markdown'));

    expect(screen.getByText('Show Rendered')).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes('## Research Report'))).toBeInTheDocument();
  });

  it('reflects PR link when sessions prop updates after initial render', () => {
    const sessionWithoutPr = { ...mockSessionWithPrLink, pr_link: null };
    const sessionWithPr = { ...mockSessionWithPrLink, pr_link: 'https://github.com/owner/repo/pull/99' };

    const { rerender } = render(
      <SessionArtifacts taskId="TASK-123" sessions={[sessionWithoutPr]} />,
    );

    expect(screen.queryByText('View Pull Request')).not.toBeInTheDocument();

    rerender(
      <SessionArtifacts taskId="TASK-123" sessions={[sessionWithPr]} />,
    );

    const link = screen.getByText('View Pull Request');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', 'https://github.com/owner/repo/pull/99');
  });
});
