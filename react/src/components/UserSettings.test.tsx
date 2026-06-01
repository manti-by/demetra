import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { UserSettings } from './UserSettings';

vi.mock('../services/api', () => ({
  updateUserKeys: vi.fn().mockResolvedValue(undefined),
}));

describe('UserSettings', () => {
  it('does not render when isOpen is false', () => {
    render(<UserSettings isOpen={false} onClose={() => {}} />);
    expect(screen.queryByText('User Settings')).not.toBeInTheDocument();
  });

  it('renders modal when isOpen is true', () => {
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    expect(screen.getByText('User Settings')).toBeInTheDocument();
    expect(screen.getAllByText('Keys').length).toBeGreaterThan(0);
  });

  it('renders one key-value row by default', () => {
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    const inputs = screen.getAllByPlaceholderText('Key');
    expect(inputs).toHaveLength(1);
  });

  it('adds a new key-value row when Add Key is clicked', async () => {
    const user = userEvent.setup();
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    await user.click(screen.getByText('+ Add Key'));
    
    const inputs = screen.getAllByPlaceholderText('Key');
    expect(inputs).toHaveLength(2);
  });

  it('removes a key-value row when remove is clicked', async () => {
    const user = userEvent.setup();
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    await user.click(screen.getByText('+ Add Key'));
    const removeButtons = screen.getAllByLabelText('Remove key');
    await user.click(removeButtons[1]);
    
    const inputs = screen.getAllByPlaceholderText('Key');
    expect(inputs).toHaveLength(1);
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    
    render(<UserSettings isOpen={true} onClose={onClose} />);
    
    await user.click(screen.getByText('Cancel'));
    
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
