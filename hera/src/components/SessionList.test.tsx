import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { SessionList } from './SessionList';

describe('SessionList', () => {
  it('renders without crashing', () => {
    render(<SessionList onSelectSession={vi.fn()} selectedTaskId={null} />);
    expect(screen.getByText('Loading sessions...')).toBeInTheDocument();
  });
});
