import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MarkdownContent } from './MarkdownContent';

describe('MarkdownContent', () => {
  it('renders markdown headings and emphasis as HTML', () => {
    const { container } = render(
      <MarkdownContent content={'## Plan\n\nSome **bold** text'} />,
    );

    expect(screen.getByRole('heading', { name: 'Plan' })).toBeInTheDocument();
    expect(container.querySelector('strong')).toHaveTextContent('bold');
    expect(screen.queryByText('## Plan')).not.toBeInTheDocument();
  });

  it('sanitizes raw HTML from the content', () => {
    const { container } = render(
      <MarkdownContent
        content={'<script>alert(1)</script><img src="x" onerror="alert(1)">'}
      />,
    );

    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img')?.getAttribute('onerror')).toBeNull();
  });

  it('drops forbidden tags', () => {
    const { container } = render(
      <MarkdownContent
        content={'![graph](https://example.com/graph.png)'}
        forbidTags={['img']}
      />,
    );

    expect(container.querySelector('img')).toBeNull();
  });

  it('keeps images when no tag is forbidden', () => {
    const { container } = render(
      <MarkdownContent content={'![graph](https://example.com/graph.png)'} />,
    );

    expect(container.querySelector('img')).not.toBeNull();
  });

  it('applies the provided className', () => {
    const { container } = render(
      <MarkdownContent content={'plain'} className="chat-markdown" />,
    );

    expect(container.firstChild).toHaveClass('chat-markdown');
  });
});
