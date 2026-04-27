import { type FC, useMemo } from 'react';
import DOMPurify from 'dompurify';
import type { DisplayDataOutput, ExecuteResultOutput } from '../types';

interface RichOutputProps {
    output: DisplayDataOutput | ExecuteResultOutput;
}

/** Renders an `execute_result` or `display_data` output by picking the
 *  highest-fidelity MIME type available and falling back to text/plain.
 *
 *  Priority:
 *    1. image/png  — base64 inline image
 *    2. text/html  — sanitised via DOMPurify (renders pandas DataFrame
 *                    .to_html(), seaborn captions, etc.)
 *    3. text/plain — monospace fallback
 */
export const RichOutput: FC<RichOutputProps> = ({ output }) => {
    const data = output.data ?? {};

    if ('image/png' in data) {
        const b64 = data['image/png'];
        return (
            <div className="px-3 py-2 flex items-start">
                <img
                    src={`data:image/png;base64,${b64}`}
                    alt="cell output"
                    className="max-w-full h-auto rounded border border-[var(--border-color)]"
                />
            </div>
        );
    }

    if ('text/html' in data) {
        return <HtmlOutput html={data['text/html']} />;
    }

    if ('text/plain' in data) {
        return (
            <pre className="m-0 px-3 py-1.5 font-mono text-[12px] text-[var(--text-primary)] whitespace-pre-wrap break-words">
                {data['text/plain']}
            </pre>
        );
    }

    return null;
};

const HtmlOutput: FC<{ html: string }> = ({ html }) => {
    const safe = useMemo(() => DOMPurify.sanitize(html, {
        // Allow style attributes so pandas DataFrame styling survives.
        ADD_ATTR: ['style', 'target'],
        // Block any sneaky script-loading tags or nested SVG handlers.
        FORBID_TAGS: ['script', 'iframe', 'object', 'embed'],
        FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus'],
    }), [html]);

    return (
        <div
            className="live-html-output px-3 py-2 text-[12px] text-[var(--text-primary)] overflow-x-auto"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: safe }}
        />
    );
};
