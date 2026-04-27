import { type FC } from 'react';
import type { StreamOutput } from '../types';

interface TextOutputProps {
    output: StreamOutput;
}

/** Renders a stdout/stderr stream output as a monospace block. */
export const TextOutput: FC<TextOutputProps> = ({ output }) => {
    const isStderr = output.name === 'stderr';
    return (
        <pre
            className={`m-0 px-3 py-1.5 font-mono text-[12px] whitespace-pre-wrap break-words ${
                isStderr ? 'text-[var(--status-warn)]' : 'text-[var(--text-primary)]'
            }`}
        >
            {output.text}
        </pre>
    );
};
