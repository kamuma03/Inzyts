import { useMemo, type FC, type KeyboardEventHandler } from 'react';
import CodeMirror, { EditorView } from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';

interface CellSourceEditorProps {
    value: string;
    onChange: (value: string) => void;
    onKeyDown?: KeyboardEventHandler<HTMLDivElement>;
    language: 'python' | 'markdown';
    ariaLabel: string;
    /** Approx line count from caller — used to bound the rendered height. */
    minRows?: number;
    maxRows?: number;
}

/** Source editor for a single cell — wraps CodeMirror 6 with our palette and
 *  the language extension selected by cell type. The host textarea behaviour
 *  (controlled value, key handlers, aria-label) is preserved so callers can
 *  drop this in without other changes. */
export const CellSourceEditor: FC<CellSourceEditorProps> = ({
    value,
    onChange,
    onKeyDown,
    language,
    ariaLabel,
    minRows = 2,
    maxRows = 20,
}) => {
    const extensions = useMemo(
        () => [
            language === 'python' ? python() : markdown(),
            EditorView.lineWrapping,
        ],
        [language],
    );

    // CodeMirror sizes itself by content; clamp via a min/max height so cells
    // stay roughly textarea-shaped instead of collapsing to one line or
    // ballooning to thousands of lines.
    const lineHeight = 18;
    const lines = value.split('\n').length;
    const clampedLines = Math.max(minRows, Math.min(maxRows, lines));
    const heightStyle = { minHeight: `${minRows * lineHeight}px`, maxHeight: `${maxRows * lineHeight}px`, height: `${clampedLines * lineHeight}px` };

    return (
        <div
            role="group"
            aria-label={ariaLabel}
            onKeyDown={onKeyDown}
            className="cell-source-editor border border-[var(--rule)] rounded overflow-hidden focus-within:border-[var(--accent)]"
            style={heightStyle}
        >
            <CodeMirror
                value={value}
                onChange={onChange}
                theme={oneDark}
                extensions={extensions}
                basicSetup={{
                    lineNumbers: false,
                    foldGutter: false,
                    highlightActiveLine: false,
                    highlightActiveLineGutter: false,
                    indentOnInput: true,
                    bracketMatching: true,
                    autocompletion: false,
                }}
                height="100%"
                style={{ height: '100%', fontSize: '12px' }}
                aria-label={ariaLabel}
            />
        </div>
    );
};
