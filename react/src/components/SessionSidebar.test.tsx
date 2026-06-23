import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SessionSidebar } from './SessionSidebar';

vi.mock('../services/api', () => ({
  getSessions: vi.fn().mockResolvedValue([]),
}));

describe('SessionSidebar', () => {
  it('renders without crashing', () => {
    render(
      <SessionSidebar
        onSelectSession={vi.fn()}
        selectedTaskId={null}
        sessions={[]}
        setSessions={vi.fn()}
      />,
    );
    expect(screen.getByText('Sessions')).toBeInTheDocument();
  });
});
