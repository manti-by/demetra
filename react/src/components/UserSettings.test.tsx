import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { UserSettings } from './UserSettings';

describe('UserSettings', () => {
  it('does not render when isOpen is false', () => {
    render(<UserSettings isOpen={false} onClose={() => {}} />);
    expect(screen.queryByText('User Settings')).not.toBeInTheDocument();
  });

  it('renders modal when isOpen is true', () => {
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    expect(screen.getByText('User Settings')).toBeInTheDocument();
  });

  it('calls onClose when Close is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<UserSettings isOpen={true} onClose={onClose} />);

    await user.click(screen.getByText('Close'));

    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();

    render(<UserSettings isOpen={true} onClose={onClose} />);

    await user.click(screen.getByLabelText('Close'));

    expect(onClose).toHaveBeenCalled();
  });
});
