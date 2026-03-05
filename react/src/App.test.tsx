import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App';
import * as api from './services/api';

vi.mock('./services/api', () => ({
  getCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading initially', async () => {
    vi.mocked(api.getCurrentUser).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );
    render(<App />);
    expect(screen.getByText('Loading...')).toBeDefined();
  });

  it('shows login button when not authenticated', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValue(null);
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Sign in with GitHub')).toBeDefined();
    });
  });

  it('shows Hello to Demetra when authenticated', async () => {
    vi.mocked(api.getCurrentUser).mockResolvedValue({
      id: '1',
      github_username: 'testuser',
      email: 'test@example.com',
    });
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText('Hello to Demetra')).toBeDefined();
    });
  });
});
