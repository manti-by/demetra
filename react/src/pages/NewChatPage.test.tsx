import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { NewChatPage } from './NewChatPage';
import { AuthProvider } from '../contexts/AuthContext';
import { getChatTemplates, getProjects, type ChatTemplate, type Project } from '../services/api';

vi.mock(new URL('../services/api.ts', import.meta.url).pathname, () => ({
  getCurrentUser: vi.fn().mockResolvedValue({ id: 'u1', email: 'user@example.com' }),
  logout: vi.fn(),
  getProjects: vi.fn(),
  createChat: vi.fn(),
  getChatTemplates: vi.fn(),
}));

const activeProject: Project = {
  id: 'p1',
  user_id: 'u1',
  linear_project_id: null,
  name: 'demetra',
  state: 'active',
  repository_url: 'https://github.com/owner/demetra',
  local_path: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

const featureTemplate: ChatTemplate = {
  name: 'feature_template',
  label: 'Feature Template',
  content: '## Description\n\nAdd a feature.',
};

function renderNewChatPage() {
  localStorage.setItem('user', JSON.stringify({ id: 'u1', email: 'user@example.com' }));
  return render(
    <MemoryRouter initialEntries={['/chats/new']}>
      <AuthProvider>
        <Routes>
          <Route path="/chats/new" element={<NewChatPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('TestNewChatPageTemplates', () => {
  it('lists the available templates in the selectbox', async () => {
    vi.mocked(getProjects).mockResolvedValue([activeProject]);
    vi.mocked(getChatTemplates).mockResolvedValue([featureTemplate]);

    renderNewChatPage();

    expect(await screen.findByRole('option', { name: 'Feature Template' })).toBeInTheDocument();
  });

  it('disables Apply until a template is selected', async () => {
    vi.mocked(getProjects).mockResolvedValue([activeProject]);
    vi.mocked(getChatTemplates).mockResolvedValue([featureTemplate]);

    renderNewChatPage();

    expect(await screen.findByRole('button', { name: 'Apply' })).toBeDisabled();
  });

  it('replaces the description with the template content on Apply', async () => {
    vi.mocked(getProjects).mockResolvedValue([activeProject]);
    vi.mocked(getChatTemplates).mockResolvedValue([featureTemplate]);

    renderNewChatPage();

    await userEvent.selectOptions(await screen.findByLabelText('Template'), 'feature_template');
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }));

    expect(screen.getByLabelText('Description')).toHaveValue(featureTemplate.content);
  });

  it('shows an error when the templates fail to load', async () => {
    vi.mocked(getProjects).mockResolvedValue([activeProject]);
    vi.mocked(getChatTemplates).mockRejectedValue(new Error('Failed to fetch chat templates'));

    renderNewChatPage();

    expect(await screen.findByText('Failed to fetch chat templates')).toBeInTheDocument();
  });
});
