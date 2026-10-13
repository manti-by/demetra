import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  SessionStateFlow,
  BUILD_FLOW,
  BUILD_FEEDBACK,
  RESEARCH_FLOW,
  loopPath,
  loopTrigger,
  resolveLoopState,
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

  it('marks the whole research flow done on the terminal researched step', () => {
    expect(resolveNodeStates(RESEARCH_FLOW, 'researched')).toEqual(['done', 'done', 'done']);
  });

  it('leaves the research ticket awaiting its report when the step matches no research stage', () => {
    expect(resolveNodeStates(RESEARCH_FLOW, 'awaiting_input')).toEqual([
      'upcoming',
      'upcoming',
      'upcoming',
    ]);
  });

  it('marks the whole build flow done once the session is completed', () => {
    expect(resolveNodeStates(BUILD_FLOW, 'completed')).toEqual([
      'done',
      'done',
      'done',
      'done',
      'done',
      'done',
      'done',
      'done',
    ]);
  });
});

describe('loopTrigger', () => {
  it('detects the review loop when build follows review', () => {
    expect(loopTrigger('review', 'build')).toBe('review');
  });

  it('detects the lint loop when build follows lint or test', () => {
    expect(loopTrigger('lint', 'build')).toBe('lint');
    expect(loopTrigger('test', 'build')).toBe('lint');
  });

  it('stays inactive outside a build step and for any other previous step', () => {
    expect(loopTrigger('validate', 'review')).toBeNull();
    expect(loopTrigger('build', 'validate')).toBeNull();
    expect(loopTrigger('plan', 'build')).toBeNull();
    expect(loopTrigger(null, 'build')).toBeNull();
  });
});

describe('resolveLoopState', () => {
  const lintLoop = BUILD_FEEDBACK.find((feedback) => feedback.key === 'lint')!;
  const reviewLoop = BUILD_FEEDBACK.find((feedback) => feedback.key === 'review')!;

  it('stays pending until the loop has been taken', () => {
    expect(resolveLoopState(BUILD_FLOW, reviewLoop, false, 'build')).toBe('pending');
    expect(resolveLoopState(BUILD_FLOW, lintLoop, false, 'test')).toBe('pending');
  });

  it('is active while the flow sits between the loop target and its source', () => {
    expect(resolveLoopState(BUILD_FLOW, reviewLoop, true, 'build')).toBe('active');
    expect(resolveLoopState(BUILD_FLOW, reviewLoop, true, 'review')).toBe('active');
    expect(resolveLoopState(BUILD_FLOW, lintLoop, true, 'lint')).toBe('active');
  });

  it('is passed once the flow moved past the loop source', () => {
    expect(resolveLoopState(BUILD_FLOW, reviewLoop, true, 'lint')).toBe('passed');
    expect(resolveLoopState(BUILD_FLOW, lintLoop, true, 'github')).toBe('passed');
  });
});

describe('BUILD_FEEDBACK', () => {
  it('returns both loops to the build node', () => {
    expect(BUILD_FEEDBACK.map((feedback) => [feedback.from, feedback.to])).toEqual([
      ['review', 'build'],
      ['test', 'build'],
    ]);
  });

  it('nests the review bracket on the shallower lane', () => {
    const lanes = Object.fromEntries(BUILD_FEEDBACK.map((feedback) => [feedback.key, feedback.lane]));

    expect(lanes.review).toBeLessThan(lanes.lint);
  });
});

describe('loopPath', () => {
  it('draws a square bracket dropping from the source and rising into the target with an arrowhead', () => {
    const { bracket, head } = loopPath(240, 80, 1);

    expect(bracket).toBe('M 240 4 V 17 Q 240 24 233 24 H 87 Q 80 24 80 17 V 8');
    expect(head).toBe('M 74.5 8 L 80 0 L 85.5 8');
  });

  it('deepens the bracket for nested lanes', () => {
    expect(loopPath(240, 80, 2).bracket).toContain('Q 240 48 233 48');
  });

  it('never turns corners wider than the span between the nodes', () => {
    expect(loopPath(10, 9, 1).bracket).toBe('M 10 4 V 23.5 Q 10 24 9.5 24 H 9.5 Q 9 24 9 23.5 V 8');
  });
});

describe('SessionStateFlow', () => {
  it('renders the research chain with the research node active and no feedback loops', () => {
    const { container } = render(<SessionStateFlow step="research" isResearch />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Research', state: 'active' },
      { label: 'In Review', state: 'upcoming' },
    ]);
    expect(container.querySelector('.session-flow-loops')).toBeNull();
    expect(screen.queryByLabelText('Feedback from review')).not.toBeInTheDocument();
  });

  it('completes the research chain once the report moved the ticket to In Review', () => {
    const { container } = render(<SessionStateFlow step="researched" isResearch />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Research', state: 'done' },
      { label: 'In Review', state: 'done' },
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

  it('activates the github node for the wiki and push steps', () => {
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

  it('completes the github node without blinking once the session is completed', () => {
    const { container } = render(<SessionStateFlow step="completed" />);

    expect(nodeStates(container)).toEqual([
      { label: 'Linear', state: 'done' },
      { label: 'Plan', state: 'done' },
      { label: 'Build', state: 'done' },
      { label: 'Validate', state: 'done' },
      { label: 'Review', state: 'done' },
      { label: 'Lint', state: 'done' },
      { label: 'Test', state: 'done' },
      { label: 'GitHub', state: 'done' },
    ]);
    expect(container.querySelector('.session-flow-node.active')).toBeNull();
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

  it('draws both feedback brackets dashed before any loop is taken', () => {
    render(<SessionStateFlow step="build" />);

    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'pending');
    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-state', 'pending');
  });

  it('lights the review bracket while the build step follows review', () => {
    const { rerender } = render(<SessionStateFlow step="review" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'pending');

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'active');
    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-state', 'pending');
  });

  it('lights the lint bracket while the build step follows lint or test', () => {
    const { rerender } = render(<SessionStateFlow step="lint" />);
    rerender(<SessionStateFlow step="test" />);
    rerender(<SessionStateFlow step="build" />);

    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-state', 'active');
    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'pending');
  });

  it('keeps a taken bracket lit across re-renders with an unchanged step', () => {
    const { rerender } = render(<SessionStateFlow step="review" />);

    rerender(<SessionStateFlow step="build" />);
    rerender(<SessionStateFlow step="build" />);
    rerender(<SessionStateFlow step="build" />);

    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'active');
  });

  it('passes both brackets once the session is completed', () => {
    const { rerender } = render(<SessionStateFlow step="review" />);
    rerender(<SessionStateFlow step="build" />);
    rerender(<SessionStateFlow step="test" />);
    rerender(<SessionStateFlow step="build" />);
    rerender(<SessionStateFlow step="completed" />);

    expect(screen.getByLabelText('Feedback from review')).toHaveAttribute('data-state', 'passed');
    expect(screen.getByLabelText('Feedback from lint and test')).toHaveAttribute('data-state', 'passed');
  });

  it('labels a bracket only once its loop has been taken', () => {
    const { container, rerender } = render(<SessionStateFlow step="review" />);
    expect(container.querySelector('.session-flow-loop.pending text')).toBeNull();

    rerender(<SessionStateFlow step="build" />);
    expect(screen.getByLabelText('Feedback from review').querySelector('text')).not.toBeNull();
    expect(screen.getByLabelText('Feedback from lint and test').querySelector('text')).toBeNull();
  });
});

