import { useMemo } from "react";
import { marked } from "marked";
import DOMPurify from "dompurify";

interface MarkdownContentProps {
  content: string;
  className?: string;
  forbidTags?: string[];
}

export function MarkdownContent({
  content,
  className,
  forbidTags,
}: MarkdownContentProps) {
  const html = useMemo(
    () =>
      DOMPurify.sanitize(
        marked.parse(content, { async: false }) as string,
        forbidTags && forbidTags.length > 0
          ? { FORBID_TAGS: forbidTags }
          : undefined,
      ),
    [content, forbidTags],
  );
  return (
    <div className={className} dangerouslySetInnerHTML={{ __html: html }} />
  );
}

export default MarkdownContent;
