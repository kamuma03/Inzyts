import React from 'react';

interface Column {
    label: string;
    align?: 'left' | 'right';
}

interface DataTableShellProps {
    columns: (string | Column)[];
    /** ``sm`` uses ``px-3`` (denser, used by the audit log); ``md`` uses ``px-4``. */
    padding?: 'sm' | 'md';
    /** Class added to the outer wrapper — useful for dropping in ``overflow-x-auto``. */
    wrapperClass?: string;
    children: React.ReactNode;
}

/** Shared chrome for the admin tables (Users, Audit). Extracted to avoid
 *  diverging copies of the wrapper / `<table>` / `<thead>` styling. The
 *  `<tbody>` and per-row layout stay in each page so columns can render
 *  whatever interactive controls they need. */
export const DataTableShell: React.FC<DataTableShellProps> = ({
    columns, padding = 'md', wrapperClass = '', children,
}) => {
    const px = padding === 'sm' ? 'px-3' : 'px-4';
    return (
        <div className={`bg-[var(--surface-1)] rounded-lg border border-[var(--rule)] overflow-hidden ${wrapperClass}`.trim()}>
            <table className="w-full text-sm">
                <thead>
                    <tr className="border-b border-[var(--rule)] text-[var(--text-secondary)] text-left">
                        {columns.map((c, i) => {
                            const col = typeof c === 'string' ? { label: c } : c;
                            const align = col.align === 'right' ? 'text-right' : '';
                            return (
                                <th key={i} className={`${px} py-3 font-medium ${align}`.trim()}>
                                    {col.label}
                                </th>
                            );
                        })}
                    </tr>
                </thead>
                <tbody>{children}</tbody>
            </table>
        </div>
    );
};
