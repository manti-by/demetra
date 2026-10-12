import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  SessionStateFlow,
  BUILD_FLOW,
  RESEARCH_FLOW,
  activeFeedback,
  resolveNodeStates,
} from './SessionStateFlow';

interface NodeView {
  label: string | null;
  state: string | null;
}

function nodeStates(container: HTMLElement): NodeView[] {
  return Array.from(container.querySelectorAll('.session-flow-node')).map((el) => ({
    label: el.textContent,
    state: el.getAttribute('data-state'),
  }));
}

describe('resolveNodeStates', () => {
  it('marks earlier nodes done, the matching node active and later nodes upcoming', () => {
    expect(resolveNodeStates(BUILD_FLOW, 'validate')).toEqual([
      'done',
      'done',
      'done',
      'active',
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
    ]);
  });

  it('leaves every node upcoming when the step is unknown', () => {
    expect(resolveNodeStates(BUILD_FLOW, 'failed')).toEqual([
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
      'upcoming',
    ]);
  });

  it('leaves every node upcoming when no step is set', () => {
    expect(resolveNodeStates(RESEARCH_FLOW, null)).toEqual([
      'upcoming',
      'upcoming',
      'upcoming',
    ]);
  });

  it('marks the whole research flow done on the terminal awaiting_input step', () => {
    expect(resolveNodeStates(RESEARCH_FLOW, 'awaiting_input')).toEqual(['done', 'done', 'done']);
  });
});

describe('activeFeedback', () => {
  it('activates the review loop when build follows review', () => {
    expect(activeFeedback('build', 'review')).toBe('review');
  });

  it('activates the lint loop when build follows lint or test', () => {
    expect(activeFeedback('build', 'lint')).toBe('lint');
    expect(activeFeedback('build', 'test')).toBe('lint');
  });

  it('is inactive outside a build step and for any other previous step', () => {
    expect(activeFeedback('review', 'validate')).toBeNull();
    expect(activeFeedback('validate', 'build')).toBeNull();
    expect(activeFeedback('build', 'validate')).toBeNull();
    expect(activeFeedback('build', null)).toBeNull();
  });
});

describe('SessionStateFlow', () => {
  it('renders the research chain with the research node active and no feedback loops', () => {
    const { container } = render(<SessionStateFlow step="research" isResearch />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Research', state: 'active' },
      { label: 'Awaiting Input', state: 'upcoming' },
    ]);
    expect(container.querySelector('.session-flow-loops')).toBeNull();
    expect(screen.queryByLabelText('Feedback from review')).not.toBeInTheDocument();
  });

  it('completes the research chain when the research report reaches awaiting_input', () => {
    const { container } = render(<SessionStateFlow step="awaiting_input" isResearch />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Research', state: 'done' },
      { label: 'Awaiting Input', state: 'done' },
    ]);
  });

  it('renders the build chain with the active step and later steps greyed', () => {
    const { container } = render(<SessionStateFlow step="validate" />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Plan', state: 'done' },
      { label: 'Build', state: 'done' },
      { label: 'Validate', state: 'active' },
      { label: 'Review', state: 'upcoming' },
      { label: 'Lint', state: 'upcoming' },
      { label: 'Test', state: 'upcoming' },
      { label: 'GitHub', state: 'upcoming' },
    ]);
  });

  it('maps awaiting_input to the plan node in the build chain', () => {
    const { container } = render(<SessionStateFlow step="awaiting_input" />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Plan', state: 'active' },
      { label: 'Build', state: 'upcoming' },
      { label: 'Validate', state: 'upcoming' },
      { label: 'Review', state: 'upcoming' },
      { label: 'Lint', state: 'upcoming' },
      { label: 'Test', state: 'upcoming' },
      { label: 'GitHub', state: 'upcoming' },
    ]);
  });

  it('activates the github node for the wiki, push and completed steps', () => {
    const { container } = render(<SessionStateFlow step="wiki" />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Plan', state: 'done' },
      { label: 'Build', state: 'done' },
      { label: 'Validate', state: 'done' },
      { label: 'Review', state: 'done' },
      { label: 'Lint', state: 'done' },
      { label: 'Test', state: 'done' },
      { label: 'GitHub', state: 'active' },
    ]);
  });

  it('leaves every node greyed when the step is failed', () => {
    const { container } = render(<SessionStateFlow step="failed" />);

    expect(nodeStates(container).every((node) => node.state === 'upcoming')).toBe(true);
  });

  it('announces the active step in a polite status region', () => {
    const { rerender } = render(<SessionStateFlow step="research" isResearch />);
    const status = screen.getByRole('status');

    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent('Current step: Research');

    rerender(<SessionStateFlow step="validate" />);
    expect(status).toHaveTextContent('Current step: Validate');
  });

  it('announces nothing while the step matches no node', () => {
    render(<SessionStateFlow step="failed" />);

    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('blinks the review feedback arrow only while the build step follows review', () => {
    const { rerender } = render(<SessionStateFlow step="review" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'false');

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'true');
    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-active', 'false');

    rerender(<SessionStateFlow step="validate" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'false');

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'false');
  });

  it('blinks the lint and test feedback arrow while the build step follows test', () => {
    const { rerender } = render(<SessionStateFlow step="test" />);

    rerender(<SessionStateFlow step="build" />);

    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-active', 'true');
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'false');
  });

  it('keeps the feedback arrow lit across re-renders with an unchanged step', () => {
    const { rerender } = render(<SessionStateFlow step="review" />);

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'true');

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'true');

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-active', 'true');
  });
});
