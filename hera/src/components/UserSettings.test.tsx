import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { UserSettings } from './UserSettings';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  updateUserKeys: vi.fn(),
}));

describe('UserSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does not render when isOpen is false', () => {
    render(<UserSettings isOpen={false} onClose={() => {}} />);
    expect(screen.queryByText('User Settings')).not.toBeInTheDocument();
  });

  it('renders modal when isOpen is true', () => {
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    expect(screen.getByText('User Settings')).toBeInTheDocument();
    expect(screen.getByText('Keys')).toBeInTheDocument();
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

  it('shows error when saving with duplicate keys', async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateUserKeys).mockResolvedValue();
    
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    await user.click(screen.getByText('+ Add Key'));
    
    const keyInputs = screen.getAllByPlaceholderText('Key');
    await user.type(keyInputs[0], 'duplicate');
    await user.type(keyInputs[1], 'duplicate');
    
    await user.click(screen.getByText('Save'));
    
    await waitFor(() => {
      expect(screen.getByText('Duplicate keys are not allowed')).toBeInTheDocument();
    });
  });

  it('calls updateUserKeys with correct data on save', async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateUserKeys).mockResolvedValue();
    
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    const keyInput = screen.getByPlaceholderText('Key');
    const valueInput = screen.getByPlaceholderText('Value');
    
    await user.type(keyInput, 'mykey');
    await user.type(valueInput, 'myvalue');
    await user.click(screen.getByText('Save'));
    
    await waitFor(() => {
      expect(api.updateUserKeys).toHaveBeenCalledWith({ mykey: 'myvalue' });
    });
  });

  it('shows success message after successful save', async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateUserKeys).mockResolvedValue();
    
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    const keyInput = screen.getByPlaceholderText('Key');
    await user.type(keyInput, 'key1');
    await user.click(screen.getByText('Save'));
    
    await waitFor(() => {
      expect(screen.getByText('Keys saved successfully')).toBeInTheDocument();
    });
  });

  it('shows error message when save fails', async () => {
    const user = userEvent.setup();
    vi.mocked(api.updateUserKeys).mockRejectedValue(new Error('Server error'));
    
    render(<UserSettings isOpen={true} onClose={() => {}} />);
    
    const keyInput = screen.getByPlaceholderText('Key');
    await user.type(keyInput, 'key1');
    await user.click(screen.getByText('Save'));
    
    await waitFor(() => {
      expect(screen.getByText('Server error')).toBeInTheDocument();
    });
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
