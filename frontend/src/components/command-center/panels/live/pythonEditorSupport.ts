/** Editor support for the notebook code cells — autocompletion sources and an
 *  error-line decoration extension. Kept out of CellSourceEditor.tsx so the
 *  React component stays focused on layout/resize while the CodeMirror plumbing
 *  lives here. All of this is heuristic/static (no LSP) — see requirement FR-7
 *  ("static is proposed for first ship").
 */
import {
    type Completion,
    type CompletionContext,
    type CompletionResult,
    type CompletionSource,
} from '@codemirror/autocomplete';
import {
    Decoration,
    type DecorationSet,
    EditorView,
    ViewPlugin,
    type ViewUpdate,
} from '@codemirror/view';
import { StateEffect, StateField, RangeSetBuilder } from '@codemirror/state';

// -- Static vocabulary ------------------------------------------------------

const PY_KEYWORDS = [
    'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
    'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global',
    'if', 'import', 'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass',
    'raise', 'return', 'try', 'while', 'with', 'yield', 'True', 'False', 'None',
];

const PY_BUILTINS = [
    'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'getattr', 'hasattr', 'int', 'isinstance', 'len',
    'list', 'map', 'max', 'min', 'open', 'print', 'range', 'repr', 'reversed',
    'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'type', 'zip',
];

/** Member methods offered after a known receiver + ".". Trimmed to the
 *  high-traffic surface of each library; not exhaustive. */
const MEMBER_COMPLETIONS: Record<string, string[]> = {
    df: [
        'head', 'tail', 'describe', 'info', 'shape', 'columns', 'index',
        'dtypes', 'groupby', 'merge', 'join', 'sort_values', 'value_counts',
        'fillna', 'dropna', 'isna', 'apply', 'astype', 'reset_index',
        'set_index', 'loc', 'iloc', 'plot', 'to_csv', 'sample', 'copy',
        'rename', 'drop', 'mean', 'sum', 'count', 'nunique', 'pivot_table',
    ],
    pd: [
        'DataFrame', 'Series', 'read_csv', 'read_excel', 'read_sql', 'concat',
        'merge', 'to_datetime', 'date_range', 'get_dummies', 'cut', 'qcut',
        'isnull', 'notnull', 'pivot_table', 'melt', 'crosstab',
    ],
    np: [
        'array', 'arange', 'linspace', 'zeros', 'ones', 'mean', 'median',
        'std', 'sum', 'min', 'max', 'argmax', 'argmin', 'where', 'unique',
        'concatenate', 'reshape', 'random', 'dot', 'log', 'exp', 'sqrt', 'abs',
    ],
    plt: [
        'figure', 'plot', 'scatter', 'bar', 'barh', 'hist', 'boxplot', 'pie',
        'title', 'xlabel', 'ylabel', 'legend', 'show', 'savefig', 'subplots',
        'subplot', 'xticks', 'yticks', 'grid', 'tight_layout', 'colorbar',
    ],
    sns: [
        'barplot', 'boxplot', 'countplot', 'heatmap', 'histplot', 'kdeplot',
        'lineplot', 'pairplot', 'regplot', 'scatterplot', 'violinplot',
        'set_theme', 'set_palette', 'displot', 'catplot',
    ],
};

function toCompletions(labels: string[], type: string, detail?: string): Completion[] {
    return labels.map((label) => ({ label, type, detail }));
}

/**
 * Build a CodeMirror completion source. Priority (FR-7):
 *   1. kernel/session variables (live set, supplied by the caller)
 *   2. member methods on a known receiver (`df.`, `plt.`, …)
 *   3. python keywords + builtins (fallback)
 *
 * `getSessionVars` is read lazily on each keystroke so the popup always
 * reflects the latest inspector variable list without rebuilding extensions.
 */
export function makePythonCompletionSource(
    getSessionVars: () => string[],
): CompletionSource {
    return (context: CompletionContext): CompletionResult | null => {
        // Member access: `<receiver>.<partial>`
        const member = context.matchBefore(/(\w+)\.(\w*)$/);
        if (member) {
            const dot = member.text.indexOf('.');
            const receiver = member.text.slice(0, dot);
            const members = MEMBER_COMPLETIONS[receiver];
            if (members) {
                return {
                    from: member.from + dot + 1,
                    options: toCompletions(members, 'method', receiver),
                    validFor: /^\w*$/,
                };
            }
            // Unknown receiver — don't fall through to the keyword list, which
            // would suggest nonsense after a dot.
            return null;
        }

        const word = context.matchBefore(/\w+/);
        if (!word || (word.from === word.to && !context.explicit)) return null;

        const sessionVars = getSessionVars();
        const options: Completion[] = [
            ...toCompletions(sessionVars, 'variable', 'session'),
            ...toCompletions(Object.keys(MEMBER_COMPLETIONS), 'namespace'),
            ...toCompletions(PY_BUILTINS, 'function', 'builtin'),
            ...toCompletions(PY_KEYWORDS, 'keyword'),
        ];
        // Dedup by label (session var may shadow a builtin name).
        const seen = new Set<string>();
        const deduped = options.filter((o) => {
            if (seen.has(o.label)) return false;
            seen.add(o.label);
            return true;
        });

        return { from: word.from, options: deduped, validFor: /^\w*$/ };
    };
}

// -- Error-line decoration (FR-8, line-level best-effort) -------------------
//
// Token-level squiggles need a reliable cell-relative column from the
// traceback, which the sandbox doesn't always give. We mark the whole
// offending line instead: a wavy underline on the line + a gutter glyph,
// driven by a 1-based line number the caller derives from the traceback.

/** Effect carrying the 1-based error line (or null to clear). */
export const setErrorLine = StateEffect.define<number | null>();

const errorLineMark = Decoration.line({ class: 'cm-errorLine' });

export const errorLineField = StateField.define<DecorationSet>({
    create() {
        return Decoration.none;
    },
    update(deco, tr) {
        deco = deco.map(tr.changes);
        for (const e of tr.effects) {
            if (e.is(setErrorLine)) {
                if (e.value == null) {
                    deco = Decoration.none;
                } else {
                    const builder = new RangeSetBuilder<Decoration>();
                    const lineNo = Math.min(
                        Math.max(1, e.value),
                        tr.state.doc.lines,
                    );
                    const line = tr.state.doc.line(lineNo);
                    builder.add(line.from, line.from, errorLineMark);
                    deco = builder.finish();
                }
            }
        }
        return deco;
    },
    provide: (f) => EditorView.decorations.from(f),
});

/** Clear the error decoration as soon as the user edits the doc, so stale
 *  squiggles don't linger past a fix (FR-8: "clear on edit of that line"). */
export const clearErrorOnEdit = ViewPlugin.fromClass(
    class {
        update(update: ViewUpdate) {
            if (update.docChanged) {
                // Defer to avoid dispatching inside an update cycle.
                queueMicrotask(() => {
                    if (!update.view.state.field(errorLineField, false)) return;
                    if (update.view.state.field(errorLineField).size === 0) return;
                    update.view.dispatch({ effects: setErrorLine.of(null) });
                });
            }
        }
    },
);

/**
 * Best-effort: pull a 1-based, cell-relative line number out of a Python
 * traceback. The sandbox reports frames as `File "<cell>", line N` (or
 * `<ipython-input-…>`). We take the last such frame — the deepest one in the
 * user's own cell. Returns null when nothing matches.
 */
export function errorLineFromTraceback(traceback: string[] | undefined): number | null {
    if (!traceback || traceback.length === 0) return null;
    const joined = traceback.join('\n');
    const re = /(?:<cell[^>]*>|<ipython-input[^>]*>|Cell In\[[^\]]*\])[^\n]*?line (\d+)/gi;
    let match: RegExpExecArray | null;
    let last: number | null = null;
    while ((match = re.exec(joined)) !== null) {
        last = Number(match[1]);
    }
    return last;
}
