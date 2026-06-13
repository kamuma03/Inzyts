import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    type FC,
    type KeyboardEventHandler,
    type PointerEvent as ReactPointerEvent,
} from 'react';
import CodeMirror, { type ReactCodeMirrorRef } from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { markdown } from '@codemirror/lang-markdown';
import { oneDark } from '@codemirror/theme-one-dark';
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { indentUnit } from '@codemirror/language';
import { indentWithTab } from '@codemirror/commands';
import {
    EditorView,
    keymap,
    lineNumbers,
    highlightActiveLine,
    highlightActiveLineGutter,
} from '@codemirror/view';
import {
    clearErrorOnEdit,
    errorLineField,
    makePythonCompletionSource,
    setErrorLine,
} from './pythonEditorSupport';
import { useEditorSupport } from './EditorSupportContext';

interface CellSourceEditorProps {
    value: string;
    onChange: (value: string) => void;
    onKeyDown?: KeyboardEventHandler<HTMLDivElement>;
    language: 'python' | 'markdown';
    ariaLabel: string;
    /** Min/max rows used to bound the auto-grow height. */
    minRows?: number;
    maxRows?: number;
    /** 1-based, cell-relative line to flag as an error (FR-8). null clears. */
    errorLine?: number | null;
    /** Stable cell id — combined with the job id to persist a drag-resized
     *  height for the session. */
    cellId?: string;
}

const LINE_HEIGHT = 18;

/** Brand-aligned chrome layered over oneDark's syntax colors: align the
 *  background to our surface tokens and keep the active-line tint subtle
 *  (≈3.5% white) per FR-4/FR-6. */
const brandTheme = EditorView.theme({
    '&': { backgroundColor: 'var(--surface-1)', fontSize: '12px' },
    '.cm-content': { caretColor: 'var(--accent)' },
    '.cm-gutters': {
        backgroundColor: 'var(--surface-1)',
        color: 'var(--text-dim)',
        border: 'none',
    },
    '.cm-activeLine': { backgroundColor: 'rgba(255,255,255,0.035)' },
    '.cm-activeLineGutter': {
        backgroundColor: 'rgba(255,255,255,0.04)',
        color: 'var(--text-secondary)',
    },
    '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--accent)' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground': {
        backgroundColor: 'rgba(76,201,240,0.18)',
    },
    '.cm-tooltip-autocomplete': {
        backgroundColor: 'var(--surface-2)',
        border: '1px solid var(--rule)',
        borderRadius: '6px',
    },
    '.cm-tooltip-autocomplete > ul > li[aria-selected]': {
        backgroundColor: 'var(--accent-soft)',
        color: 'var(--text-primary)',
    },
});

/** Source editor for a single cell — wraps CodeMirror 6 with line numbers,
 *  active-line highlight, Python-aware indentation, autocomplete, auto-grow
 *  with a drag-resize handle, and inline error-line marking. The controlled
 *  value / key-handler / aria-label contract is unchanged so callers (and the
 *  test textarea mock) keep working. */
export const CellSourceEditor: FC<CellSourceEditorProps> = ({
    value,
    onChange,
    onKeyDown,
    language,
    ariaLabel,
    minRows = 2,
    maxRows = 22,
    errorLine = null,
    cellId,
}) => {
    const isPython = language === 'python';

    // Completions come from a stable context ref (LivePanel keeps `.current`
    // up to date with the inferred variable list) and are read lazily by the
    // completion source — no per-keystroke prop churn that would re-render
    // sibling cells.
    const { completionsRef, jobId } = useEditorSupport();

    const editorRef = useRef<ReactCodeMirrorRef>(null);

    // -- Drag-resize: an explicit height overrides auto-grow, persisted per
    //    cell for the session (FR-5). --------------------------------------
    const heightKey = cellId ? `inzyts.cellHeight.${jobId}.${cellId}` : null;
    const [manualHeight, setManualHeight] = useState<number | null>(() => {
        if (!heightKey) return null;
        try {
            const raw = sessionStorage.getItem(heightKey);
            return raw ? Number(raw) || null : null;
        } catch {
            return null;
        }
    });
    const dragRef = useRef<{ startY: number; startH: number } | null>(null);

    const onResizePointerMove = useCallback((e: PointerEvent) => {
        const drag = dragRef.current;
        if (!drag) return;
        const next = Math.max(
            minRows * LINE_HEIGHT,
            Math.min(80 * LINE_HEIGHT, drag.startH + (e.clientY - drag.startY)),
        );
        setManualHeight(next);
    }, [minRows]);

    const endResize = useCallback(() => {
        dragRef.current = null;
        window.removeEventListener('pointermove', onResizePointerMove);
        window.removeEventListener('pointerup', endResize);
        if (heightKey) {
            try {
                const h = editorRef.current?.editor?.clientHeight;
                if (h) sessionStorage.setItem(heightKey, String(h));
            } catch {
                /* storage unavailable — height stays in-memory only */
            }
        }
    }, [onResizePointerMove, heightKey]);

    const startResize = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
        e.preventDefault();
        const startH = editorRef.current?.editor?.clientHeight ?? minRows * LINE_HEIGHT;
        dragRef.current = { startY: e.clientY, startH };
        window.addEventListener('pointermove', onResizePointerMove);
        window.addEventListener('pointerup', endResize);
    }, [minRows, onResizePointerMove, endResize]);

    useEffect(() => () => {
        window.removeEventListener('pointermove', onResizePointerMove);
        window.removeEventListener('pointerup', endResize);
    }, [onResizePointerMove, endResize]);

    const extensions = useMemo(() => {
        const base = [
            isPython ? python() : markdown(),
            EditorView.lineWrapping,
            lineNumbers(),
            highlightActiveLine(),
            highlightActiveLineGutter(),
            indentUnit.of('    '),
            keymap.of([indentWithTab, ...completionKeymap]),
            brandTheme,
        ];
        if (isPython) {
            base.push(
                autocompletion({
                    override: [makePythonCompletionSource(() => completionsRef.current)],
                    icons: false,
                }),
                errorLineField,
                clearErrorOnEdit,
            );
        }
        return base;
        // completionsRef is a stable ref; rebuild only when language changes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isPython]);

    // Push the error line into the editor whenever it changes (FR-8).
    useEffect(() => {
        if (!isPython) return;
        const view = editorRef.current?.view;
        if (!view) return;
        view.dispatch({ effects: setErrorLine.of(errorLine ?? null) });
    }, [errorLine, isPython, value]);

    const minH = `${minRows * LINE_HEIGHT}px`;
    const maxH = `${maxRows * LINE_HEIGHT}px`;

    return (
        <div
            role="group"
            aria-label={ariaLabel}
            onKeyDown={onKeyDown}
            className="cell-source-editor relative border border-[var(--rule)] rounded overflow-hidden focus-within:border-[var(--accent)]"
        >
            <CodeMirror
                ref={editorRef}
                value={value}
                onChange={onChange}
                theme={oneDark}
                extensions={extensions}
                basicSetup={{
                    lineNumbers: false, // provided by our lineNumbers() extension
                    foldGutter: false,
                    highlightActiveLine: false, // provided above
                    highlightActiveLineGutter: false,
                    indentOnInput: true,
                    bracketMatching: true,
                    autocompletion: false, // provided above (python only)
                }}
                height={manualHeight ? `${manualHeight}px` : undefined}
                minHeight={manualHeight ? undefined : minH}
                maxHeight={manualHeight ? undefined : maxH}
                style={{ fontSize: '12px' }}
                aria-label={ariaLabel}
            />
            {/* Drag handle — sets an explicit height that overrides auto-grow. */}
            <div
                role="separator"
                aria-label={`Resize ${ariaLabel}`}
                aria-orientation="horizontal"
                onPointerDown={startResize}
                onDoubleClick={() => {
                    setManualHeight(null);
                    if (heightKey) {
                        try { sessionStorage.removeItem(heightKey); } catch { /* noop */ }
                    }
                }}
                title="Drag to resize · double-click to reset"
                className="cell-resize-handle absolute left-0 right-0 bottom-0 h-1.5 cursor-ns-resize"
            />
        </div>
    );
};
