import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

// jsdom can't drive CodeMirror's contenteditable correctly, so we stand in a
// shim that exposes value/onChange/aria-label as plain attributes — enough
// to verify CellSourceEditor wires the props through.
vi.mock('@uiw/react-codemirror', () => ({
    __esModule: true,
    default: ({ value, onChange, 'aria-label': ariaLabel }: {
        value: string;
        onChange: (v: string) => void;
        'aria-label'?: string;
    }) => (
        <textarea
            data-testid="cm-shim"
            aria-label={ariaLabel}
            value={value}
            onChange={(e) => onChange(e.target.value)}
        />
    ),
    EditorView: { lineWrapping: {} as unknown },
}));

vi.mock('@codemirror/lang-python', () => ({ python: () => ({}) }));
vi.mock('@codemirror/lang-markdown', () => ({ markdown: () => ({}) }));
vi.mock('@codemirror/theme-one-dark', () => ({ oneDark: {} }));

import { CellSourceEditor } from './CellSourceEditor';

describe('CellSourceEditor', () => {
    it('renders the source through CodeMirror with the aria-label exposed', () => {
        const onChange = vi.fn();
        render(
            <CellSourceEditor
                value={'print(1)'}
                onChange={onChange}
                language="python"
                ariaLabel="Cell 1 source"
            />,
        );
        // The outer group exposes aria-label for accessibility tooling.
        const group = screen.getByRole('group', { name: 'Cell 1 source' });
        expect(group).toBeInTheDocument();
        // The (mocked) inner editor receives the same value.
        const inner = screen.getByTestId('cm-shim') as HTMLTextAreaElement;
        expect(inner.value).toBe('print(1)');
    });

    it('emits onChange when the editor reports a new value', () => {
        const onChange = vi.fn();
        render(
            <CellSourceEditor
                value=""
                onChange={onChange}
                language="python"
                ariaLabel="Cell 1 source"
            />,
        );
        const inner = screen.getByTestId('cm-shim');
        fireEvent.change(inner, { target: { value: 'x = 1' } });
        expect(onChange).toHaveBeenCalledWith('x = 1');
    });

    it('forwards onKeyDown so the parent can intercept Shift+Enter', () => {
        const onKey = vi.fn();
        render(
            <CellSourceEditor
                value=""
                onChange={() => {}}
                onKeyDown={onKey}
                language="markdown"
                ariaLabel="Markdown cell 1 source"
            />,
        );
        const group = screen.getByRole('group', { name: 'Markdown cell 1 source' });
        fireEvent.keyDown(group, { key: 'Enter', shiftKey: true });
        expect(onKey).toHaveBeenCalled();
    });
});
