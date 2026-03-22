import DOMPurify from 'dompurify';

/**
 * Strict allowlist for DOMPurify — only the tags/attributes our markdown
 * converter can produce. This prevents any injected HTML (e.g. <script>,
 * <iframe>, event handlers) from surviving sanitization.
 */
const PURIFY_CONFIG = {
    ALLOWED_TAGS: [
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'strong', 'em', 'code', 'pre', 'br',
        'p', 'ul', 'ol', 'li', 'a', 'blockquote',
        'span', 'div', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
    ALLOW_DATA_ATTR: false,
};

/**
 * Convert a small subset of Markdown (headers, bold, italic, inline code,
 * newlines) to HTML, then sanitize with DOMPurify before use with
 * dangerouslySetInnerHTML.
 *
 * Only call the result with dangerouslySetInnerHTML={{ __html: ... }}.
 */
export function formatMarkdown(source: string): string {
    const html = source
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br/>');

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return DOMPurify.sanitize(html, PURIFY_CONFIG as any) as unknown as string;
}
