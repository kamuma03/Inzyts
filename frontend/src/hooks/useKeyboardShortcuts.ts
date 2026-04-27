import { useEffect, useRef } from 'react';

export type ShortcutHandler = (event: KeyboardEvent) => void;

/** Map keys to handlers. Keys are matched case-insensitively against
 *  ``event.key``. Use the prefix ``cmd+`` (Mac) or ``ctrl+`` (others)
 *  to require a modifier; bare modifiers are not supported.
 *
 *  Examples:
 *    { 'j': nextEvent, 'k': prevEvent, 'cmd+enter': rerun, 'escape': clear }
 */
export type ShortcutMap = Record<string, ShortcutHandler>;

interface Options {
    enabled?: boolean;
    /** When true (default), shortcuts ignore typing in inputs/textareas. */
    ignoreEditableTargets?: boolean;
}

const isEditable = (target: EventTarget | null): boolean => {
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
    return target.isContentEditable;
};

const normaliseKey = (key: string, e: KeyboardEvent): string => {
    const k = key.toLowerCase();
    const parts = k.split('+').map((s) => s.trim());
    const main = parts.pop() ?? '';
    if (parts.includes('cmd') || parts.includes('meta')) {
        if (!e.metaKey) return '';
    }
    if (parts.includes('ctrl')) {
        if (!e.ctrlKey) return '';
    }
    if (parts.includes('shift')) {
        if (!e.shiftKey) return '';
    }
    return main;
};

export const useKeyboardShortcuts = (
    shortcuts: ShortcutMap,
    { enabled = true, ignoreEditableTargets = true }: Options = {},
) => {
    const shortcutsRef = useRef(shortcuts);
    shortcutsRef.current = shortcuts;

    useEffect(() => {
        if (!enabled) return;

        const handler = (e: KeyboardEvent) => {
            if (ignoreEditableTargets && isEditable(e.target)) return;
            const eventKey = e.key.toLowerCase();
            for (const [combo, fn] of Object.entries(shortcutsRef.current)) {
                const targetKey = normaliseKey(combo, e);
                if (targetKey && targetKey === eventKey) {
                    fn(e);
                    return;
                }
            }
        };

        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [enabled, ignoreEditableTargets]);
};
