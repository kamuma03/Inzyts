import { useMemo, type FC } from 'react';
import type { ColumnProfile } from '../../api';
import { useColumnProfile } from '../../hooks/useColumnProfile';
import { roleVar, dtypeVar } from '../../utils/colorScales';
import { ColumnDetailCard } from './ColumnDetailCard';
import { MiniBars } from './primitives/MiniBars';
import { Columns } from 'lucide-react';

interface ColumnInspectorProps {
    jobId: string;
    /** Selection state lifted to the parent so other panels can react. */
    selectedColumn: string | null;
    onSelect: (name: string | null) => void;
}

/** Right-rail column inspector — list + click → instant detail card update. */
export const ColumnInspector: FC<ColumnInspectorProps> = ({ jobId, selectedColumn, onSelect }) => {
    const { columns, loading, error } = useColumnProfile(jobId);

    const selected = useMemo<ColumnProfile | null>(() => {
        if (!columns || !selectedColumn) return null;
        return columns.find((c) => c.name === selectedColumn) ?? null;
    }, [columns, selectedColumn]);

    return (
        <div className="flex flex-col gap-3 min-h-0">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                <Columns size={12} />
                <span>Columns</span>
                {columns && (
                    <span className="ml-auto text-[var(--text-dim)] font-mono">
                        {columns.length}
                    </span>
                )}
            </div>

            <ColumnDetailCard column={selected} />

            <div className="flex-1 min-h-0 overflow-y-auto border border-[var(--border-color)] rounded-lg bg-[var(--bg-surface-hi)]">
                {loading && (
                    <div className="p-3 text-[12px] text-[var(--text-dim)]">Loading columns…</div>
                )}
                {error && (
                    <div className="p-3 text-[12px] text-[var(--status-bad)]">{error}</div>
                )}
                {columns && columns.length === 0 && !loading && (
                    <div className="p-3 text-[12px] text-[var(--text-dim)]">
                        No column profile yet. Available once Phase 1 completes.
                    </div>
                )}

                {columns && columns.length > 0 && (
                    <ul role="listbox" aria-label="Columns" className="m-0 p-0 list-none">
                        {columns.map((col) => {
                            const isSelected = selectedColumn === col.name;
                            return (
                                <li key={col.name}>
                                    <button
                                        type="button"
                                        role="option"
                                        aria-selected={isSelected}
                                        onClick={() => onSelect(isSelected ? null : col.name)}
                                        className={`w-full text-left px-3 py-2 flex items-center gap-2 border-l-2 transition-colors duration-150 ${
                                            isSelected
                                                ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.08)]'
                                                : 'border-transparent hover:bg-[rgba(255,255,255,0.03)]'
                                        }`}
                                    >
                                        <span
                                            className="font-mono text-[12px] text-[var(--text-primary)] truncate flex-1 min-w-0"
                                            title={col.name}
                                        >
                                            {col.name}
                                        </span>
                                        <MiniBars
                                            values={col.histogram?.length > 0 ? col.histogram : [0.2, 0.4, 0.6, 0.4, 0.3]}
                                            width={56}
                                            height={18}
                                            color={dtypeVar(col.dtype)}
                                            ariaLabel={`${col.name} distribution`}
                                        />
                                        <span
                                            className="text-[9px] uppercase tracking-[1px] shrink-0"
                                            style={{ color: roleVar(col.role) }}
                                            title={col.role}
                                        >
                                            {col.role.slice(0, 3)}
                                        </span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </div>
        </div>
    );
};
