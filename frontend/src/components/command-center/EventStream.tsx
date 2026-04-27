import { useMemo, useRef, useState, type FC } from 'react';
import { List, type RowComponentProps } from 'react-window';
import type { AgentEvent } from '../../hooks/useSocket';
import { Filter } from 'lucide-react';

interface EventStreamProps {
    events: AgentEvent[];
    /** Optional handler called when the user navigates entries via J/K. */
    onSelect?: (index: number) => void;
}

const VIRT_THRESHOLD = 500;
const ROW_HEIGHT = 28;

const eventLabel = (e: AgentEvent): string => {
    const evt = e.event ?? '';
    const agent = e.agent ?? '';
    if (agent) return `${evt}:${agent}`;
    return evt;
};

const eventDot = (e: AgentEvent): string => {
    if (/FAIL|ERROR/i.test(e.event ?? '')) return 'var(--status-bad)';
    if (/COMPLET|DONE|GRANTED|PASSED/i.test(e.event ?? '')) return 'var(--status-good)';
    if (/INVOK|START/i.test(e.event ?? '')) return 'var(--bg-turquoise-surf)';
    return 'var(--text-dim)';
};

const eventTimestamp = (e: AgentEvent): string => {
    const ts = (e.data as Record<string, unknown> | undefined)?.timestamp;
    if (typeof ts !== 'string') return '';
    try {
        const d = new Date(ts);
        return d.toLocaleTimeString();
    } catch {
        return '';
    }
};

const eventMessage = (e: AgentEvent): string => {
    const msg = (e.data as Record<string, unknown> | undefined)?.message;
    return typeof msg === 'string' ? msg : '';
};

interface RowItemProps {
    items: AgentEvent[];
    selectedIndex: number;
    setSelectedIndex: (i: number) => void;
}

type RowProps = RowComponentProps<RowItemProps>;

const Row = (props: RowProps): JSX.Element => {
    const { index, style, items, selectedIndex, setSelectedIndex, ariaAttributes } = props;
    const e = items[index];
    if (!e) return <div style={style} />;
    const isSelected = selectedIndex === index;
    return (
        <div
            style={style}
            {...ariaAttributes}
            onClick={() => setSelectedIndex(index)}
            className={`flex items-center gap-2 px-3 text-[11px] cursor-pointer border-l-2 ${
                isSelected
                    ? 'border-[var(--bg-turquoise-surf)] bg-[rgba(76,201,240,0.06)]'
                    : 'border-transparent hover:bg-[rgba(255,255,255,0.03)]'
            }`}
        >
            <span
                className="inline-block w-1.5 h-1.5 rounded-full shrink-0"
                style={{ backgroundColor: eventDot(e) }}
            />
            <span className="font-mono text-[10px] text-[var(--text-dim)] shrink-0">
                {eventTimestamp(e)}
            </span>
            <span className="font-mono text-[var(--text-secondary)] shrink-0">
                {eventLabel(e)}
            </span>
            <span className="text-[var(--text-primary)] truncate flex-1 min-w-0">
                {eventMessage(e)}
            </span>
        </div>
    );
};

type FilterValue = 'all' | 'started' | 'completed' | 'failed';

export const EventStream: FC<EventStreamProps> = ({ events, onSelect }) => {
    const [filter, setFilter] = useState<FilterValue>('all');
    const [search, setSearch] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const containerRef = useRef<HTMLDivElement | null>(null);

    const filtered = useMemo(() => {
        const q = search.trim().toLowerCase();
        return events.filter((e) => {
            const evt = (e.event ?? '').toLowerCase();
            if (filter === 'started' && !/(invok|start)/i.test(evt)) return false;
            if (filter === 'completed' && !/(complet|done|granted|passed)/i.test(evt)) return false;
            if (filter === 'failed' && !/(fail|error)/i.test(evt)) return false;
            if (q) {
                const haystack = `${evt} ${(e.agent ?? '').toLowerCase()} ${eventMessage(e).toLowerCase()}`;
                if (!haystack.includes(q)) return false;
            }
            return true;
        });
    }, [events, filter, search]);

    const updateSelection = (i: number) => {
        const clamped = Math.max(0, Math.min(filtered.length - 1, i));
        setSelectedIndex(clamped);
        onSelect?.(clamped);
    };

    const handleKey = (e: React.KeyboardEvent) => {
        if (e.key === 'j' || e.key === 'ArrowDown') {
            e.preventDefault();
            updateSelection(selectedIndex + 1);
        } else if (e.key === 'k' || e.key === 'ArrowUp') {
            e.preventDefault();
            updateSelection(selectedIndex - 1);
        }
    };

    const useVirtual = filtered.length > VIRT_THRESHOLD;

    return (
        <section
            ref={containerRef}
            tabIndex={0}
            onKeyDown={handleKey}
            aria-label="Agent event stream"
            className="border border-[var(--border-color)] rounded-lg bg-[var(--bg-true-cobalt)] flex flex-col min-h-0"
        >
            <header className="shrink-0 flex items-center gap-2 px-3 py-2 border-b border-[var(--border-color)]">
                <Filter size={12} className="text-[var(--text-dim)]" />
                <span className="text-[10px] uppercase tracking-[1.5px] text-[var(--text-dim)]">
                    Events
                </span>
                <span className="ml-1 font-mono text-[10px] text-[var(--text-dim)]">
                    {filtered.length}
                    {filtered.length !== events.length && (
                        <> / {events.length}</>
                    )}
                </span>

                <div className="ml-auto flex items-center gap-1">
                    <FilterChip value="all" current={filter} onClick={setFilter}>All</FilterChip>
                    <FilterChip value="started" current={filter} onClick={setFilter}>Running</FilterChip>
                    <FilterChip value="completed" current={filter} onClick={setFilter}>Done</FilterChip>
                    <FilterChip value="failed" current={filter} onClick={setFilter}>Failed</FilterChip>

                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="search"
                        aria-label="Search events"
                        className="ml-2 px-2 py-0.5 text-[11px] bg-[rgba(0,0,0,0.2)] border border-[var(--border-color)] rounded text-[var(--text-primary)] w-32"
                    />
                </div>
            </header>

            <div className="flex-1 min-h-0">
                {filtered.length === 0 ? (
                    <div className="p-3 text-[12px] text-[var(--text-dim)]">No events match the current filter.</div>
                ) : useVirtual ? (
                    <List
                        rowCount={filtered.length}
                        rowHeight={ROW_HEIGHT}
                        rowComponent={Row}
                        rowProps={{ items: filtered, selectedIndex, setSelectedIndex: updateSelection }}
                    />
                ) : (
                    <div className="overflow-y-auto h-full">
                        {filtered.map((_e, i) => (
                            <Row
                                key={i}
                                index={i}
                                style={{ height: ROW_HEIGHT }}
                                items={filtered}
                                selectedIndex={selectedIndex}
                                setSelectedIndex={updateSelection}
                                ariaAttributes={{
                                    'aria-posinset': i + 1,
                                    'aria-setsize': filtered.length,
                                    role: 'listitem',
                                }}
                            />
                        ))}
                    </div>
                )}
            </div>
        </section>
    );
};

interface FilterChipProps {
    value: FilterValue;
    current: FilterValue;
    onClick: (v: FilterValue) => void;
    children: React.ReactNode;
}

const FilterChip: FC<FilterChipProps> = ({ value, current, onClick, children }) => (
    <button
        type="button"
        onClick={() => onClick(value)}
        aria-pressed={current === value}
        className={`px-2 py-0.5 text-[11px] rounded ${
            current === value
                ? 'bg-[rgba(76,201,240,0.12)] text-[var(--bg-turquoise-surf)]'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
        }`}
    >
        {children}
    </button>
);
