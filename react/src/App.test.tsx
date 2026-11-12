import { describe, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import App from './App';

vi.mock('./services/api', () => ({
  getCurrentUser: vi.fn().mockResolvedValue(null),
  login: vi.fn(),
  signup: vi.fn(),
  loginWithPassword: vi.fn(),
  logout: vi.fn(),
  deleteSession: vi.fn(),
  getSessions: vi.fn().mockResolvedValue([]),
  getLiveSessionIds: vi.fn().mockResolvedValue([]),
  getChat: vi.fn(),
  rerunChat: vi.fn(),
  postChatMessage: vi.fn(),
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
  });
});
