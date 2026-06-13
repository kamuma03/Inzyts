import { createContext, useContext, type MutableRefObject } from 'react';

/** Shared, referentially-stable editor support passed to every CellSourceEditor
 *  without threading frequently-changing props through the memoised CellRow.
 *
 *  `completionsRef` is a stable ref object whose `.current` LivePanel updates
 *  each render with the latest inferred variable names. Cell editors read it
 *  lazily inside the autocomplete source, so the popup stays current while the
 *  context value identity never changes — CellRow's React.memo holds and
 *  typing in one cell doesn't re-render the others. */
export interface EditorSupport {
    completionsRef: MutableRefObject<string[]>;
    jobId: string;
}

const fallbackRef: MutableRefObject<string[]> = { current: [] };

export const EditorSupportContext = createContext<EditorSupport>({
    completionsRef: fallbackRef,
    jobId: '',
});

export const useEditorSupport = (): EditorSupport => useContext(EditorSupportContext);
