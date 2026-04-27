import { type FC } from 'react';
import { AlertCircle } from 'lucide-react';
import type { ErrorOutput as ErrorOutputData } from '../types';

interface ErrorOutputProps {
    output: ErrorOutputData;
}

// ANSI escape code stripper — Jupyter tracebacks include color codes.
const ansiRegex = /\[[0-9;]*m/g;
const stripAnsi = (s: string): string => s.replace(ansiRegex, '');

/** Renders a Python traceback in red, with ANSI color codes stripped. */
export const ErrorOutput: FC<ErrorOutputProps> = ({ output }) => (
    <div className="px-3 py-2 border-l-2 border-[var(--status-bad)] bg-[rgba(248,113,113,0.05)]">
        <div className="flex items-center gap-1.5 mb-1.5 text-[12px] font-semibold text-[var(--status-bad)]">
            <AlertCircle size={12} />
            <span>{output.ename}: {output.evalue}</span>
        </div>
        <pre className="m-0 font-mono text-[11px] whitespace-pre-wrap break-words text-[var(--text-secondary)]">
            {stripAnsi(output.traceback.join('\n'))}
        </pre>
    </div>
);
